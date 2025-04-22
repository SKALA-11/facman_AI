# routers/hq.py
from fastapi import APIRouter, HTTPException, Body, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from datetime import datetime
import threading, queue, tempfile, os, io, time, asyncio, sys
import numpy as np
import base64
import logging
from typing import Dict, List

# 모듈 import
from modules.stt import stt_processing_thread
from modules.tts import generate_tts_audio
from modules.user import get_or_create_user, users_lock, users
from modules.meeting_transcript import (
    generate_meeting_summary, 
    list_meeting_transcripts, 
    get_meeting_summary,
    update_meeting_title,
    delete_meeting_summary
)
from config import CLIENT  # 필요 시 사용

logger = logging.getLogger(__name__)

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

# 현재 활성 세션 ID (초기엔 None)
session_id: str = None
# 회의록 로그 남기기 위한 전역 저장 구조
meeting_log: List[str] = []          # 각 entry: 포맷된 텍스트 한 줄
meeting_log_lock = asyncio.Lock()    # 비동기 안전을 위한 Lock

# 1. STT 관리 함수
@hq_router.post("/stt/audio", response_model=CombinedResultsResponse)
async def stt_audio_endpoint(payload: STTPayload):
    global meeting_log
    print("[DEBUG] POST 요청")

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
    
    # final_results_queue로부터 전사 결과, 번역 결과 받아오는 객체 정의
    combined_results = []
    
    # 추가: 최대 timeout초동안 결과가 생성될 때까지 기다리는 예시 (polling)
    timeout = 120.0  # 최대 대기 시간
    poll_interval = 0.1  # 200ms 간격으로 폴링
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

    # 결과를 meeting_log에 저장
    if combined_results:
        new_lines = [
            f"{e['speaker']}: {e['transcription']} ({e['translation']})"
            for e in combined_results
        ]
        logger.info(f"[/stt/audio] Session {session_id}: Preparing to add {len(new_lines)} line(s) to meeting_log: {new_lines}")
        async with meeting_log_lock:
                meeting_log.extend(new_lines)
                logger.info(f"[/stt/audio] Session {session_id}: Lines added. Global meeting_log size: {len(meeting_log)}")

    return CombinedResultsResponse(results=combined_results)

# Update the meeting summary endpoint to use the in-memory data
@hq_router.post("/meeting/end/{session_id}")
async def end_meeting(session_id: str, title: str = None):
    """
    회의 종료 시 호출되는 엔드포인트
    전역 meeting_log 에 쌓인 대화 기록을 가져와 요약·저장하고, 로그는 초기화
    """
    try:
        # 1) 로그를 안전하게 추출 & 초기화
        # --- 로깅 추가 ---
        logger.info(f"[/meeting/end] Endpoint called for session_id: {session_id}")
        # ---------------
        async with meeting_log_lock:
            # --- 로깅 추가 ---
            logger.info(f"[/meeting/end] Session {session_id}: Inside lock. Current global meeting_log size: {len(meeting_log)}")
            if meeting_log:
                logger.debug(f"[/meeting/end] Session {session_id}: First 3 log entries: {meeting_log[:3]}")
            # ---------------
            if not meeting_log:
                # --- 로깅 추가 ---
                logger.info(f"[/meeting/end] Session {session_id}: Global meeting_log is empty. Returning 'No content'.")
                # ---------------
                return JSONResponse(
                    status_code=404,
                    content={"error": "No conversation data found for this session."}
                )
            # 대화 목록 복사
            conversation_lines = meeting_log.copy()
            # --- 로깅 추가 ---
            logger.info(f"[/meeting/end] Session {session_id}: Copied {len(conversation_lines)} lines from global meeting_log.")
            # ---------------
            # 전역 로그 비우기
            meeting_log.clear()
            # --- 로깅 추가 ---
            logger.info(f"[/meeting/end] Session {session_id}: Global meeting_log cleared.")
            # ---------------

        # 2) 포맷팅: 이미 "화자: 발화 (번역)" 형식이므로 그냥 줄바꿈으로 합칩니다.
        formatted_transcript = "\n".join(conversation_lines)

        # 3) GPT-4에 전달할 시스템 프롬프트
        system_prompt = f"""
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

        # 4) OpenAI API 호출
        response = CLIENT.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": formatted_transcript}
            ]
        )
        summary_content = response.choices[0].message.content

        # 5) DB에 요약 저장
        meeting_title = title or f"Meeting {session_id}"
        summary_data, status_code = await generate_meeting_summary(
            session_id=session_id,
            title=meeting_title,
            content=summary_content
        )

        # 6) 저장된 요약 리턴
        return JSONResponse(status_code=status_code, content=summary_data)

    except Exception as e:
        logger.error(f"Error in end_meeting: {e}", exc_info=True)
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

@hq_router.delete("/meeting/transcript/{session_id}")
async def api_delete_meeting_transcript(session_id: str):
    """지정된 세션 ID의 회의록 요약을 삭제합니다."""
    logger.info(f"[/delete] Received request to delete transcript for session_id: {session_id}")
    result, status_code = await delete_meeting_summary(session_id)
    return JSONResponse(status_code=status_code, content=result)

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
