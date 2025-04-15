# routers/hq.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, File, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
import threading, queue, tempfile, os, io, time, asyncio
import numpy as np
import soundfile as sf
import ffmpeg
import base64

# 모듈 import
from modules.stt import stt_processing_thread
from modules.tts import tts_thread, generate_tts_audio
from modules.translation import translation_thread
from modules.audio import recording_active
from modules.user import get_or_create_user
from config import CLIENT  # 필요 시 사용

# 라우터 생성 및 본사 시스템용 API prefix 설정
hq_router = APIRouter(prefix="/ai/hq")

# 전역 큐들 (음성 처리 파이프라인)
audio_queue = queue.Queue()
sentence_queue = queue.Queue()
translation_queue = queue.Queue()
transcription_queue = queue.Queue()
translated_queue = queue.Queue()

# 최신 결과 저장 변수
latest_transcription = ""
latest_translation = ""

# Pydantic 모델
class AudioData(BaseModel):
    audio_data: bytes

class TTSRequest(BaseModel):
    text: str

# 백그라운드 작업들을 시작하는 startup 이벤트 핸들러
@hq_router.on_event("startup")
async def startup_event():
    # STT, 번역, TTS 처리를 위한 스레드 실행
    threading.Thread(
        target=stt_processing_thread,
        args=(audio_queue, sentence_queue, transcription_queue, recording_active, "ko"),
        daemon=True
    ).start()
    threading.Thread(
        target=translation_thread,
        args=(sentence_queue, translation_queue, translated_queue, "en"),
        daemon=True
    ).start()

    # 결과 전송 태스크를 메인 이벤트 루프에 스케줄링
    asyncio.create_task(result_sender_task())

# 1. STT 관리 함수

# ffmpeg를 이용하여 .webm 파일을 WAV(BytesIO)로 변환하는 함수
def convert_webm_to_wav_bytes(webm_path: str) -> io.BytesIO:
    try:
        out, _ = (
            ffmpeg
            .input(webm_path, format="webm", err_detect="ignore_err")
            .output("pipe:", format="wav", acodec="pcm_s16le", ac=1, ar="16000")
            .run(capture_stdout=True, capture_stderr=True)
        )
        return io.BytesIO(out)
    except Exception as e:
        print(f"[DEBUG] ffmpeg 변환 오류: {e}")
        raise RuntimeError("ffmpeg 변환 실패")

# WebSocket 클라이언트를 저장할 리스트
websocket_clients = []

# 1-1. STT websocket

# STT WebSocket 엔드포인트 (/ai/hq/ws/stt)
# @hq_router.websocket("/ws/stt")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     print("[DEBUG] WebSocket 연결됨")
#     websocket_clients.append(websocket)
#     try:
#         while True:
#             data = await websocket.receive_bytes()
            
#             # 임시 파일에 저장
#             with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_file:
#                 temp_file_path = temp_file.name
#                 temp_file.write(data)
#             print(f"[DEBUG] 임시 파일 생성됨: {temp_file_path}")
            
#             try:
#                 # ffmpeg로 .webm → .wav 변환
#                 wav_buffer = convert_webm_to_wav_bytes(temp_file_path)
#                 os.unlink(temp_file_path)  # 임시 파일 삭제
#                 if wav_buffer is None:
#                     print("[DEBUG] 변환 실패한 청크 건너뜀")
#                     continue
#                 wav_buffer.seek(0)
#                 audio_data, sample_rate = sf.read(wav_buffer, dtype='float32')
#                 print(f"[DEBUG] 수신된 오디오 데이터: shape {audio_data.shape}, sample_rate {sample_rate}")
                
#                 # 스테레오면 모노 변환
#                 if len(audio_data.shape) > 1:
#                     audio_data = audio_data.mean(axis=1).reshape(-1, 1)
#                 else:
#                     audio_data = audio_data.reshape(-1, 1)
                
#                 # audio_queue에 추가 (STT 처리 스레드로 전달)
#                 audio_queue.put(audio_data)
#                 print(f"[DEBUG] audio_queue에 데이터 추가됨. 현재 queue 크기: {audio_queue.qsize()}")
            
#             except Exception as e:
#                 print(f"[DEBUG] 오디오 처리 오류: {e}")
#                 if os.path.exists(temp_file_path):
#                     os.unlink(temp_file_path)
    
#     except WebSocketDisconnect:
#         print("[DEBUG] WebSocket 연결 종료됨")
#         if websocket in websocket_clients:
#             websocket_clients.remove(websocket)

# 지피티가 짜준 base64 번역 코드 -> 테스트 필요
@hq_router.websocket("/ws/stt")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[DEBUG] WebSocket 연결됨 (Base64 모드)")
    websocket_clients.append(websocket)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            # data: 'type', 'speakerInfo', 'audioData', 'sampleRate', 'encoding', 'timeStamp'
            msg_type = data.get("type")
            if msg_type != "live_audio_chunk":
                continue  # 다른 메시지 타입은 무시
            
            speaker_info = data["speakerInfo"]
            speaker_name = speaker_info.get("name", "Unknown")
            connection_id = speaker_info.get("connectionId", "N/A")
            
            user = get_or_create_user(speaker_name, connection_id)

            audio_base64 = data["audioData"]
            sample_rate = int(data["sampleRate"])

            # channels = int(data["channels"])

            # Base64 디코딩
            try:
                raw_bytes = base64.b64decode(audio_base64)
                # Int16으로 변환 후 정규화 (float32 범위 [-1, 1])
                audio_np = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                # 모노 또는 다중 채널 여부에 따라 재배열
                audio_np = audio_np.reshape(-1, 1)

                audio_queue.put(audio_np)
                # 앞으로 이 코드로 바꿔야됨
                # audio_queue.put((audio_np, sample_rate, user))
                # if(audio_np.shape[0] > 0):
                #     print(f"[DEBUG] 수신된 base64 오디오 chunk shape: {audio_np.shape}, queue size: {audio_queue.qsize()}, sample rate: {sample_rate}, speaker info: {speaker_name}")
            except Exception as e:
                print(f"[DEBUG] 오디오 데이터 디코딩 오류: {e}")
                continue
        
            # raw_bytes = base64.b64decode(audio_base64)
            # audio_np = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            
            # if channels == 2: # stereo to mono
            #     audio_np = audio_np.reshape(-1, 2).mean(axis=1)
            # else:
            #     audio_np = audio_np.reshape(-1)
            
            # audio_np = audio_np.reshape(-1, 1)
    
    except WebSocketDisconnect:
        print("[DEBUG] WebSocket 연결 종료됨")
        if websocket in websocket_clients:
            websocket_clients.remove(websocket)

# 결과 전송 함수: WebSocket 클라이언트로 결과 전송
async def send_to_clients(message):
    for client in list(websocket_clients):
        try:
            await client.send_json(message)
            print(f"[DEBUG] send_to_clients 완료됨")
        except Exception as ex:
            print(f"[DEBUG] send_to_clients 오류: {ex}")
            if client in websocket_clients:
                websocket_clients.remove(client)

# 결과 전송 태스크: STT, 번역 결과를 주기적으로 WebSocket 클라이언트에 전송
async def result_sender_task():
    global latest_transcription, latest_translation
    print("[DEBUG] result_sender_task 실행됨")
    while True:
        try:
            if not transcription_queue.empty():
                result = transcription_queue.get_nowait()
                if isinstance(result, tuple):
                    text, lang = result
                    latest_transcription = text
                else:
                    latest_transcription = result
                print(f"[DEBUG] STT 결과: {latest_transcription}")
                asyncio.create_task(send_to_clients({"type": "transcription", "text": latest_transcription}))
                transcription_queue.task_done()

            if not translated_queue.empty():
                translation = translated_queue.get_nowait()
                latest_translation = translation
                print(f"[DEBUG] 번역 결과 업데이트: {latest_translation}")
                asyncio.create_task(send_to_clients({"type": "translation", "text": latest_translation}))
                translated_queue.task_done()
        except Exception as e:
            print(f"[DEBUG] 결과 전송 중 오류: {e}")
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