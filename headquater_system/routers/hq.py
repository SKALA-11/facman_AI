# routers/hq.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, File, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from datetime import datetime
import threading, queue, tempfile, os, io, time, asyncio, sys
import numpy as np
import soundfile as sf
import base64
import ffmpeg

# 모듈 import
from modules.stt import stt_processing_thread
from modules.tts import tts_thread, generate_tts_audio
from modules.translation import translation_thread
from modules.audio import recording_active
from modules.user import get_or_create_user, users_lock, users
from config import CLIENT  # 필요 시 사용

# 라우터 생성 및 본사 시스템용 API prefix 설정
hq_router = APIRouter(prefix="/ai/hq")

### Pydantic 모델 정의 ###
class STTPayload(BaseModel):
    type: str
    speakerInfo: dict
    audioData: str
    sampleRate: int
    timestamp: int = None

class CombinedResult(BaseModel):
    speaker: str
    transcription: str
    translation: str

class CombinedResultsResponse(BaseModel):
    results: list[CombinedResult]

# 최신 결과 저장 변수
latest_transcription = ""
latest_translation = ""
date_log = ""

class TTSRequest(BaseModel):
    text: str

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
    global date_log

    # payload의 type 확인
    if payload.type != "live_audio_chunk":
        raise HTTPException(status_code=400, detail="Invalid payload type")

    # 사용자 정보 추출
    speaker_info = payload.speakerInfo
    speaker_name = speaker_info.get("name", "Unknown")
    source_lang = speaker_info.get("speakerLang", "ko")
    target_lang = speaker_info.get("targetLang", "en")
    
    # 타임스탬프 처리
    timestamp = payload.timestamp if payload.timestamp is not None else int(time.time() * 1000)
    if not date_log:
        dt = datetime.fromtimestamp(timestamp / 1000)
        date_log = dt.strftime("%Y%m%d_%H%M%S")
    
    # REST 방식이므로 websocket은 None 처리
    user = get_or_create_user(speaker_name, source_lang, target_lang, websocket=None)
    
    # audioData 디코딩 및 PCM 데이터 변환 (Int16 -> float32, 정규화, 모노 재배열)
    try:
        raw_bytes = base64.b64decode(payload.audioData)
        audio_np = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        audio_np = audio_np.reshape(-1, 1)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Audio data decoding error: {e}")
    
    # 사용자 객체의 음성 큐에 데이터를 넣음
    user.audio_queue.put((audio_np, payload.sampleRate))
    
    # 백그라운드 STT 및 번역 처리 스레드가 실행 중이라고 가정하고,
    # 결과가 준비되어 있다면 transcription_queue와 translated_queue에서 꺼내 결합 메시지로 생성
    combined_results = []
    
    # 추가: 최대 5초동안 결과가 생성될 때까지 기다리는 예시 (polling)
    timeout = 30.0  # 최대 대기 시간 5초
    poll_interval = 0.2  # 200ms 간격으로 폴링
    waited = 0.0

    while waited < timeout:
        try:
            # 두 큐 모두에서 결과를 꺼낼 수 있으면 결합
            transcription = user.transcription_queue.get_nowait()
            translation = user.translated_queue.get_nowait()
            combined_results.append({
                "speaker": speaker_name,
                "transcription": transcription,
                "translation": translation
            })
            user.transcription_queue.task_done()
            user.translated_queue.task_done()
            break  # 결과를 받았으므로 종료
        except queue.Empty:
            # 결과가 아직 없다면 잠시 대기
            await asyncio.sleep(poll_interval)
            waited += poll_interval

    return CombinedResultsResponse(results=combined_results)

# 1-1. STT websocket
# def convert_webm_to_wav_bytes(raw_bytes: bytes) -> io.BytesIO:
#     try:
#         # ffmpeg의 입력을 'pipe:0'로 지정하여 표준 입력에서 raw_bytes를 읽도록 함.
#         # 출력은 'pipe:1'로 지정해 결과 WAV 데이터를 표준 출력으로 보냄.
#         process = (
#             ffmpeg
#             .input('pipe:0', format='webm', err_detect='ignore_err')
#             .output('pipe:1', format='wav', acodec='pcm_s16le', ac=1, ar='16000')
#             .run_async(pipe_stdin=True, pipe_stdout=True, pipe_stderr=True)
#         )
#         out, err = process.communicate(input=raw_bytes)
#         if process.returncode:
#             raise RuntimeError(f"ffmpeg 오류: {err.decode()}")
#         return io.BytesIO(out)
#     except Exception as e:
#         print(f"[DEBUG] ffmpeg 변환 오류: {e}")
#         raise RuntimeError("ffmpeg 변환 실패")
    
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
async def result_sender_task():
    while True:
        # 전역 users 딕셔너리를 순회하면서 각 사용자 객체의 번역 큐에 메시지가 있다면 전송
        with users_lock:
            for user in users.values():
                if user.websocket is None:
                    continue  # 연결이 없는 사용자 건너뛰기
                while not user.transcription_queue.empty():
                    message = user.transcription_queue.get()
                    try:
                        await user.websocket.send_json(message)
                        print(f"[DEBUG] {user.name}전사 전송 완료: {message}")
                    except Exception as ex:
                        print(f"[DEBUG] {user.name}전사 전송 오류: {ex}")
                    user.transcription_queue.task_done()
                while not user.translated_queue.empty():
                    message = user.translated_queue.get()
                    try:
                        await user.websocket.send_json(message)
                        print(f"[DEBUG] {user.name}에게 메시지 전송 완료: {message}")
                    except Exception as ex:
                        print(f"[DEBUG] {user.name}에게 메시지 전송 오류: {ex}")
                    user.translated_queue.task_done()
        await asyncio.sleep(0.2)


# 전사 결과 전송 태스크: 각 사용자 객체의 transcription_queue에 쌓인 메시지를 해당 사용자의 웹소켓으로 전송
async def result_sender_transcription_task():
    while True:
        # Lock을 최소화하기 위해 사용자 리스트를 먼저 복사합니다.
        with users_lock:
            current_users = list(users.values())
        for user in current_users:
            if user.websocket is None:
                continue  # 연결이 없는 사용자는 건너뛰기
            while not user.transcription_queue.empty():
                # 예: 메시지 형식은 문자열이거나 (text, lang) 튜플 등으로 보내도 됩니다.
                message = user.transcription_queue.get()
                try:
                    # 여기서 메시지 형식을 클라이언트와 합의한 포맷("type": "transcription", "text": ... )으로 만들 수 있습니다.
                    await user.websocket.send_json({"type": "transcription", "text": message})
                    print(f"[DEBUG] {user.name} 전사 메시지 전송 완료: {message}")
                except Exception as ex:
                    print(f"[DEBUG] {user.name} 전사 메시지 전송 오류: {ex}")
                user.transcription_queue.task_done()
        await asyncio.sleep(1)

# 번역 결과 전송 태스크: 각 사용자 객체의 translated_queue에 쌓인 메시지를 해당 사용자의 웹소켓으로 전송
async def result_sender_translation_task():
    while True:
        with users_lock:
            current_users = list(users.values())
        for user in current_users:
            if user.websocket is None:
                continue
            while not user.translated_queue.empty():
                message = user.translated_queue.get()
                try:
                    await user.websocket.send_json({"type": "translation", "text": message})
                    print(f"[DEBUG] {user.name} 번역 메시지 전송 완료: {message}")
                except Exception as ex:
                    print(f"[DEBUG] {user.name} 번역 메시지 전송 오류: {ex}")
                user.translated_queue.task_done()
        await asyncio.sleep(1)

# 결과 전송 태스크: 각 사용자 객체의 transcription_queue와 translated_queue에 쌓인 메시지를 결합하여 해당 사용자의 웹소켓으로 전송하며,
# 동시에 결과를 텍스트 파일로 기록합니다.
async def result_sender_combined_task():
    while True:
        # Lock을 최소화하기 위해 사용자 리스트를 먼저 복사합니다.
        with users_lock:
            current_users = list(users.values())
        for user in current_users:
            if user.websocket is None:
                continue  # 연결이 없는 사용자 건너뛰기
            
            # 두 큐에 모두 결과가 있는지 확인합니다.
            if not user.transcription_queue.empty() and not user.translated_queue.empty():
                # transcription_queue에서 원문 결과를 translated_queue에서 번역 결과를 꺼냅니다.
                transcription = user.transcription_queue.get()
                translation = user.translated_queue.get()
                
                # 결합된 메시지 구성
                combined_message = {
                    "speaker": user.name,
                    "transcription": transcription,
                    "translation": translation
                }
                try:
                    await user.websocket.send_json(combined_message)
                    print(f"[DEBUG] {user.name} 결합 메시지 전송 완료: {combined_message}")
                except Exception as ex:
                    print(f"[DEBUG] {user.name} 결합 메시지 전송 오류: {ex}")
                
                user.transcription_queue.task_done()
                user.translated_queue.task_done()
                
                # 결과를 텍스트 파일로 기록합니다.
                # 아래 내용은 고정 형식의 메시지입니다.
                try:
                    with open(f"result_log_{date_log}.txt", "a", encoding="utf-8") as log_file:
                        log_file.write(f"{user.name}\n"
                                       f"{transcription}\n"
                                       f"{translation}\n")
                    print(f"[DEBUG] {user.name} 텍스트 로그 기록 완료")
                except Exception as log_ex:
                    print(f"[DEBUG] {user.name} 텍스트 로그 기록 오류: {log_ex}", file=sys.stderr)
        await asyncio.sleep(1)

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
@hq_router.post("/tts")
async def tts_api(request: TTSRequest):
    try:
        if not request.text:
            return JSONResponse(status_code=400, content={"error": "텍스트가 비어 있습니다."})
        loop = asyncio.get_running_loop()
        print(f"[HQ /api/tts] 요청 수신: '{request.text}'")
        audio_bytes = await loop.run_in_executor(None, generate_tts_audio, request.text)
        print(f"[HQ /api/tts] 오디오 스트림 응답 생성")
        return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/mpeg")
    except Exception as e:
        print(f"[HQ Error] TTS 엔드포인트에서 오류: {e}")
        return JSONResponse(status_code=500, content={"error": f"서버 내부 오류 발생: {str(e)}"})