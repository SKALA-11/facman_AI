# routers/hq.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, File, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
import threading, queue, tempfile, os, io, time, asyncio
import numpy as np
import soundfile as sf
import base64

# 모듈 import
from modules.stt import stt_processing_thread
from modules.tts import tts_thread, generate_tts_audio
from modules.translation import translation_thread
from modules.audio import recording_active
from modules.user import get_or_create_user, users_lock, users
from config import CLIENT  # 필요 시 사용

# 라우터 생성 및 본사 시스템용 API prefix 설정
hq_router = APIRouter(prefix="/ai/hq")

# 최신 결과 저장 변수
latest_transcription = ""
latest_translation = ""

class TTSRequest(BaseModel):
    text: str

# 백그라운드 작업들을 시작하는 startup 이벤트 핸들러
@hq_router.on_event("startup")
async def startup_event():
    # 결과 전송 태스크를 메인 이벤트 루프에 스케줄링
    # asyncio.create_task(result_sender_task())
    asyncio.create_task(result_sender_transcription_task())
    asyncio.create_task(result_sender_translation_task())

# 1. STT 관리 함수

# 1-1. STT websocket

# 지피티가 짜준 base64 번역 코드 -> 테스트 필요
@hq_router.websocket("/ws/stt")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[DEBUG] WebSocket 연결됨 (Base64 모드)")

    # 최초 연결 시 클라이언트가 보내는 데이터에서 사용자 정보 추출
    initial_data = await websocket.receive_json()
    speaker_info = initial_data.get("speakerInfo", {})
    speaker_name = speaker_info.get("name", "Unknown")
    connection_id = speaker_info.get("connectionId", "N/A")
    
    # WebSocket 객체를 함께 전달해 사용자 객체 생성(또는 업데이트)
    user = get_or_create_user(speaker_name, connection_id, websocket=websocket)

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
                
                # if(audio_np.shape[0] > 0):
                #     print(f"[DEBUG] 수신된 base64 오디오 chunk shape: {audio_np.shape}, queue size: {user.audio_queue.qsize()}, sample rate: {sample_rate}, speaker info: {speaker_name}")
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