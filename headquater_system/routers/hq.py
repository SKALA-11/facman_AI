# routers/hq.py
from fastapi import APIRouter, HTTPException, Body, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from datetime import datetime
import threading, queue, tempfile, os, io, time, asyncio, sys
import numpy as np
import base64
import ffmpeg
import logging
from typing import Dict, List

# 모듈 import
from modules.stt import stt_processing_thread
from modules.tts import tts_thread, generate_tts_audio
from modules.translation import translation_thread
from modules.user import get_or_create_user, users_lock, users
from modules.meeting_transcript import (
    generate_meeting_summary, 
    list_meeting_transcripts, 
    get_meeting_summary,
    update_meeting_title
)
from config import CLIENT  # 필요 시 사용

logger = logging.getLogger(__name__)

# Global storage for meeting data
meeting_data: Dict[str, List[Dict]] = {}  # session_id -> list of messages

# 라우터 생성 및 본사 시스템용 API prefix 설정
hq_router = APIRouter(prefix="/ai/hq")

### Pydantic 모델 정의 ###
# Update the STTPayload model to include sessionId in speakerInfo
class STTPayload(BaseModel):
    type: str
    speakerInfo: dict  # This will contain sessionId
    audioData: str
    sampleRate: int
    timestamp: int = None

class CombinedResult(BaseModel):
    speaker: str
    transcription: str
    translation: str
    tts_voice: str

class CombinedResultsResponse(BaseModel):
    results: list[CombinedResult]
    
class TTSRequest(BaseModel):
    text: str = Field(..., description="음성으로 변환할 텍스트", example="안녕하세요, FacMan 시스템입니다.")
    voice: str = Field("nova", description="사용할 음성 (예: 'alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer')", example="nova")
    model: str = Field("tts-1", description="사용할 TTS 모델 (예: 'tts-1', 'tts-1-hd')", example="tts-1")

class UpdateTranscriptTitle(BaseModel):
    title: str

# 최신 결과 저장 변수
latest_transcription = ""
latest_translation = ""
date_log = ""

# 백그라운드 작업들을 시작하는 startup 이벤트 핸들러
@hq_router.on_event("startup")
async def startup_event():
    # 결과 전송 태스크를 메인 이벤트 루프에 스케줄링
    asyncio.create_task(result_sender_combined_task())
    # asyncio.create_task(result_sender_transcription_task())
    # asyncio.create_task(result_sender_translation_task())

# 1. STT 관리 함수
@hq_router.post("/stt/audio", response_model=CombinedResultsResponse)
async def stt_audio_endpoint(payload: STTPayload):
    print("[DEBUG] POST 요청")
    global date_log

    # payload의 type 확인
    if payload.type != "live_audio_chunk":
        raise HTTPException(status_code=400, detail="Invalid payload type")

    # 사용자 정보 추출
    speaker_info = payload.speakerInfo
    speaker_name = speaker_info.get("name", "Unknown")
    source_lang = speaker_info.get("speakerLang", "ko")
    target_lang = speaker_info.get("targetLang", "en")
    session_id = speaker_info.get("sessionId", None)  # Extract sessionId
    
    print(f"{speaker_name}: src {source_lang}, tar {target_lang}, sessionId: {session_id}")
    # 타임스탬프 처리
    timestamp = payload.timestamp if payload.timestamp is not None else int(time.time() * 1000)
    if not date_log:
        dt = datetime.fromtimestamp(timestamp / 1000)
        date_log = dt.strftime("%Y%m%d_%H%M%S")
    
    # REST 방식이므로 websocket은 None 처리
    user = get_or_create_user(speaker_name, source_lang, target_lang, websocket=None)

    # 사용자별로 STT/번역 처리 스레드 실행 (최초 연결 후 처음 데이터를 수신할 때 실행)
    if not user.processing_started:
        threading.Thread(
            target=stt_processing_thread,
            args=(user,),  # user 내부의 audio_queue 등 사용
            daemon=True
        ).start()

        user.processing_started = True
    
    # audioData 디코딩 및 PCM 데이터 변환 (Int16 -> float32, 정규화, 모노 재배열)
    try:
        raw_bytes = base64.b64decode(payload.audioData)
        print(f"raw_bytes: {len(raw_bytes)}")
        audio_np = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        audio_np = audio_np.reshape(-1, 1)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Audio data decoding error: {e}")
    
    # 사용자 객체의 음성 큐에 데이터를 넣음
    user.audio_queue.put((audio_np, payload.sampleRate))
    
    # 백그라운드 STT 및 번역 처리 스레드가 실행 중이라고 가정하고,
    # 결과가 준비되어 있다면 transcription_queue와 translated_queue에서 꺼내 결합 메시지로 생성
    combined_results = []
    
    # 추가: 최대 timeout초동안 결과가 생성될 때까지 기다리는 예시 (polling)
    timeout = 120.0  # 최대 대기 시간
    poll_interval = 0.2  # 200ms 간격으로 폴링
    waited = 0.0

    while timeout > waited:
        try:
            # (stt 결과, 번역 결과, tts 음성(mp3 -> base64로 인코딩))
            transcription, translation, tts_voice = user.final_results_queue.get_nowait()
 
            print(f"전사결과: {transcription}\n번역결과:{translation}")
            combined_results.append({
                "speaker": speaker_name,
                "transcription": transcription,
                "translation": translation,
                "tts_voice": tts_voice
            })
            user.final_results_queue.task_done()

            break  # 결과를 받았으므로 종료
        except queue.Empty:
            # 결과가 아직 없다면 잠시 대기
            await asyncio.sleep(poll_interval)
            waited += poll_interval

    # 결과를 meeting_data에 저장
    if session_id:
        if session_id not in meeting_data:
            meeting_data[session_id] = []
        meeting_data[session_id].extend(combined_results)

    return CombinedResultsResponse(results=combined_results)

# 1-1. STT websocket
    
# STT WebSocket 엔드포인트 (/ai/hq/ws/stt)
@hq_router.websocket("/ws/stt")
async def websocket_endpoint(websocket: WebSocket):
    global date_log
    await websocket.accept()
    print("[DEBUG] WebSocket 연결됨 (Base64 모드)")

    # 최초 연결 시 클라이언트가 보내는 데이터에서 사용자 정보 추출
    initial_data = await websocket.receive_json()
    speaker_info = initial_data.get("speakerInfo", {})
    speaker_name = speaker_info.get("name", "Unknown")
    source_lang = speaker_info.get("speakerLang", "ko")
    target_lang = speaker_info.get("targetLang", "en")
    session_id = speaker_info.get("sessionId", None)  # Extract sessionId
    
    # 최초 접속 정보만 저장
    time_stamp = initial_data.get("timestamp", time.time_ns() // 1_000_000)
    
    if not date_log:
        time_stamp = datetime.fromtimestamp(time_stamp / 1000)
        date_log = time_stamp.strftime("%Y%m%d_%H%M%S")
    
    # WebSocket 객체를 함께 전달해 사용자 객체 생성(또는 업데이트)
    user = get_or_create_user(speaker_name, source_lang, target_lang, websocket=websocket)

    # 사용자별로 STT/번역 처리 스레드 실행 (최초 연결 후 처음 데이터를 수신할 때 실행)
    if not user.processing_started:
        threading.Thread(
            target=stt_processing_thread,
            args=(user,),  # user 내부의 audio_queue 등 사용
            daemon=True
        ).start()
        threading.Thread(
            target=translation_thread,
            args=(user,),  # 사용자별 처리 로직으로 수정
            daemon=True
        ).start()
        user.processing_started = True

    try:
        # 이후 반복하면서 오디오 데이터 수신
        while True:
            data = await websocket.receive_json()
            
            # 수신 데이터의 메시지 타입이 live_audio_chunk 인 경우만 처리
            msg_type = data.get("type")
            if msg_type != "live_audio_chunk":
                continue

            # 여기서는 이미 사용자 정보가 있으므로 추가 획득이 필요없음
            audio_base64 = data.get("audioData")
            sample_rate = int(data.get("sampleRate", "16000"))  # 기본 샘플레이트 지정 가능
            print(f"audiobase size:{audio_base64.size()}, sample rate: {sample_rate}")
            try:
                # Base64 디코딩 후, Int16 배열을 float32로 변환 및 모노 채널로 재배열
                raw_bytes = base64.b64decode(audio_base64)
                
                audio_np = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0

                audio_np = audio_np.reshape(-1, 1)

                # 전역 큐 대신 해당 사용자 객체의 audio_queue에 데이터와 sample_rate 튜플로 넣음
                user.audio_queue.put((audio_np, sample_rate))
                
            except Exception as e:
                print(f"[DEBUG] 오디오 데이터 디코딩 오류: {e}")
                continue
        
    except WebSocketDisconnect:
        print("[DEBUG] WebSocket 연결 종료됨")
        # 연결 종료 시 사용자 객체의 websocket 필드를 None 처리(필요에 따라 추가 정리)
        user.websocket = None


# 결과 전송 함수: WebSocket 클라이언트로 결과 전송
# async def send_to_clients(message):
#     for client in list(websocket_clients):
#         try:
#             await client.send_json(message)
#             print(f"[DEBUG] send_to_clients 완료됨")
#         except Exception as ex:
#             print(f"[DEBUG] send_to_clients 오류: {ex}")
#             if client in websocket_clients:
#                 websocket_clients.remove(client)

# 결과 전송 태스크: STT, 번역 결과를 주기적으로 WebSocket 클라이언트에 전송
# async def result_sender_task():
#     while True:
#         # 전역 users 딕셔너리를 순회하면서 각 사용자 객체의 번역 큐에 메시지가 있다면 전송
#         with users_lock:
#             for user in users.values():
#                 if user.websocket is None:
#                     continue  # 연결이 없는 사용자 건너뛰기
#                 while not user.transcription_queue.empty():
#                     message = user.transcription_queue.get()
#                     try:
#                         await user.websocket.send_json(message)
#                         print(f"[DEBUG] {user.name}전사 전송 완료: {message}")
#                     except Exception as ex:
#                         print(f"[DEBUG] {user.name}전사 전송 오류: {ex}")
#                     user.transcription_queue.task_done()
#                 while not user.translated_queue.empty():
#                     message = user.translated_queue.get()
#                     try:
#                         await user.websocket.send_json(message)
#                         print(f"[DEBUG] {user.name}에게 메시지 전송 완료: {message}")
#                     except Exception as ex:
#                         print(f"[DEBUG] {user.name}에게 메시지 전송 오류: {ex}")
#                     user.translated_queue.task_done()
#         await asyncio.sleep(0.2)

# 결과 전송 태스크: 각 사용자 객체의 transcription_queue와 translated_queue에 쌓인 메시지를 결합하여 해당 사용자의 웹소켓으로 전송하며,
# 동시에 결과를 텍스트 파일로 기록합니다.
@hq_router.get("/result")
async def result_sender_combined_task(sessionId: str = None):
    while True:
        # Lock을 최소화하기 위해 사용자 리스트를 먼저 복사합니다.
        with users_lock:
            if sessionId:
                # Filter users by sessionId if provided
                current_users = [user for user in users.values() if user.session_id == sessionId]
            else:
                current_users = list(users.values())
                
        for user in current_users:
            # 두 큐에 모두 결과가 있는지 확인합니다.
            if not user.transcription_queue.empty() and not user.translated_queue.empty():
                # transcription_queue에서 원문 결과를 translated_queue에서 번역 결과를 꺼냅니다.
                transcription_tuple = user.transcription_queue.get_nowait()
                translation_tuple = user.translated_queue.get_nowait()
                
                # 튜플이면 첫 번째 요소만 추출
                transcription = transcription_tuple[0] if isinstance(transcription_tuple, tuple) else transcription_tuple
                translation = translation_tuple[0] if isinstance(translation_tuple, tuple) else translation_tuple
                
                # 현재 시간 정보 추가
                timestamp = datetime.now().isoformat()
                
                # 결합된 메시지 구성
                combined_message = {
                    "speaker": user.name,
                    "transcription": transcription,
                    "translation": translation,
                    "timestamp": timestamp
                }
                
                try:
                    await user.websocket.send_json(combined_message)
                    print(f"[DEBUG] {user.name} 결합 메시지 전송 완료: {combined_message}")
                except Exception as ex:
                    print(f"[DEBUG] {user.name} 결합 메시지 전송 오류: {ex}")
                
                user.transcription_queue.task_done()
                user.translated_queue.task_done()
                
        await asyncio.sleep(1)

# Update the meeting summary endpoint to use the in-memory data
@hq_router.post("/meeting/end/{session_id}")
async def end_meeting(session_id: str, title: str = None):
    """
    회의 종료 시 호출되는 엔드포인트
    해당 session_id의 모든 대화 내용을 가져와 회의록을 생성하고 저장
    """
    try:
        # 1. Gather conversation data for the session
        conversation = meeting_data.get(session_id, [])
        if not conversation:
            return JSONResponse(
                status_code=404,
                content={"error": "No conversation data found for this session."}
            )

        # 2. Format the transcript for summary generation
        formatted_transcript = "\n".join(
            f"{entry['speaker']}: {entry['transcription']} ({entry['translation']})"
            for entry in conversation
        )

        # 3. Generate summary using GPT-4
        system_prompt = """
        당신은 전문 회의록 요약 AI입니다.
        당신의 목표는 회의 내용을 분석하고 실무에 도움이 되도록 아래의 형식을 갖춘 요약을 생성하는 것입니다.
        결과는 간결하면서도 중요한 정보가 빠짐없이 담겨야 합니다.
        대화 내용을 바탕으로 구조화된 회의록을 작성해주세요.
        형식:
        1. 회의 요약 (3~5문장으로 전체 흐름을 설명)
        2. 핵심 논의 주제 (항목별 나열)
        3. 주요 결정 사항 (항목별 나열, 결정된 내용 중심)
        4. Action Items (항목별로 '담당자 - 할 일 - 기한' 형식)

        회의 내용:
        {formatted_transcript}
        """

        try:
            response = await CLIENT.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": formatted_transcript}
                ]
            )
            summary_content = response.choices[0].message.content

            # 4. Save the summary to the DB
            meeting_title = title or f"Meeting {session_id}"
            summary_data, status_code = await generate_meeting_summary(
                session_id=session_id,
                title=meeting_title,
                content=summary_content
            )

            # 5. Clear the session data
            if session_id in meeting_data:
                del meeting_data[session_id]

            # 6. Return the saved summary
            return JSONResponse(status_code=status_code, content=summary_data)

        except Exception as api_error:
            logger.error(f"OpenAI API error: {api_error}")
            return JSONResponse(
                status_code=500,
                content={"error": f"OpenAI API error: {str(api_error)}"}
            )

    except Exception as e:
        logger.error(f"Error in end_meeting: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Internal server error: {str(e)}"}
        )

# Update the list transcripts endpoint to use the new module
@hq_router.get("/meeting/transcripts")
async def api_list_meeting_transcripts():
    transcripts_data, status_code = await list_meeting_transcripts()
    return JSONResponse(status_code=status_code, content=transcripts_data)

# Update the get transcript endpoint to use the new module
@hq_router.get("/meeting/transcript/{session_id}")
async def api_get_meeting_transcript(session_id: str):
    transcript_data, status_code = await get_meeting_summary(session_id)
    return JSONResponse(status_code=status_code, content=transcript_data)

# Add new endpoint for updating meeting title
@hq_router.put("/meeting/transcript/{session_id}/title")
async def update_meeting_title_endpoint(session_id: str, title: UpdateTranscriptTitle):
    result, status_code = await update_meeting_title(session_id, title.title)
    return JSONResponse(status_code=status_code, content=result)

# 2. STT 전사 결과 반환
@hq_router.get("/transcription")
async def get_transcription():
    global latest_transcription
    if not latest_transcription:
        print("[DEBUG] 최신 변환 결과가 없습니다.")
        return JSONResponse({"text": "No transcription available yet."})
    print(f"[DEBUG] 최신 변환 결과 반환: {latest_transcription}")
    return JSONResponse({"text": latest_transcription})

# 3. 번역 결과 반환 API
@hq_router.get("/translation")
async def get_translation():
    return JSONResponse({"text": latest_translation})

# 4. TTS 결과 반환 API
@hq_router.post(
    "/tts",
    response_class=StreamingResponse, # 응답 타입을 StreamingResponse로 명시
    summary="텍스트 음성 변환 (MP3)",
    description="입력된 텍스트를 지정된 목소리와 모델을 사용하여 MP3 오디오 스트림으로 변환하여 반환합니다.",
    responses={
        200: {"content": {"audio/mpeg": {}}, "description": "성공적으로 MP3 오디오 스트림 반환"},
        400: {"description": "잘못된 요청 (예: 텍스트 누락)"},
        500: {"description": "서버 내부 오류 (TTS 생성 실패 등)"}
    }
)
async def tts_api(request: TTSRequest = Body(...)):
    """
    FastAPI 엔드포인트: 텍스트를 받아 MP3 오디오 스트림을 생성합니다.
    """
    try:
        logger.info(f"/ai/hq/tts 요청 수신: Text='{request.text[:50]}...', Voice={request.voice}, Model={request.model}")
        audio_bytes = generate_tts_audio(request.text, request.voice, request.model)
        logger.info(f"오디오 데이터 생성 완료 ({len(audio_bytes)} bytes)")

        # 생성된 오디오 바이트를 스트리밍 응답으로 반환
        return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/mpeg")

    except ValueError as ve:
        logger.warning(f"TTS 요청 오류 (400): {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        logger.error(f"TTS 생성 서버 오류 (500): {re}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS 오디오 생성 실패: {str(re)}")
    except Exception as e:
        logger.exception(f"/ai/hq/tts 엔드포인트 처리 중 예외 발생: {e}")
        raise HTTPException(status_code=500, detail=f"서버 내부 오류 발생: {str(e)}")
