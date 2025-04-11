import threading
import queue
import tempfile
import os
import io
import numpy as np
import soundfile as sf
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import time
import ffmpeg

from modules.stt import stt_processing_thread
from modules.tts import tts_thread
from modules.translation import translation_thread
from modules.audio import audio_collection_thread, audio_queue, recording_active
from config import CLIENT  # CLIENT를 STT API 호출 등에서 사용하는 것으로 가정

app = FastAPI()

# CORS 설정 (테스트용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 배포시 도메인 제한 필요
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 큐들 (음성 처리 파이프라인)
sentence_queue = queue.Queue()
translation_queue = queue.Queue()

# 최신 변환 결과 저장
latest_transcription = ""
latest_translation = ""

class AudioData(BaseModel):
    audio_data: bytes

class TTSRequest(BaseModel):
    text: str

@app.on_event("startup")
async def startup_event():
    # stt, 번역, tts 스레드를 시작합니다.
    threading.Thread(
        target=stt_processing_thread,
        args=(audio_queue, sentence_queue, recording_active, "ko"),
        daemon=True
    ).start()
    threading.Thread(
        target=translation_thread,
        args=(sentence_queue, translation_queue, "en"),
        daemon=True
    ).start()
    threading.Thread(
        target=tts_thread,
        args=(translation_queue, recording_active),
        daemon=True
    ).start()

    # 디버그: 주기적으로 각 큐의 상태를 로깅하는 별도 스레드를 시작합니다.
    threading.Thread(target=debug_queues, daemon=True).start()

    # 결과 전송 태스크를 메인 이벤트 루프에 스케줄링합니다.
    asyncio.create_task(result_sender_task())

# 디버그 함수: 각 큐의 크기를 주기적으로 콘솔에 출력합니다.
def debug_queues():
    while True:
        print(f"[DEBUG] audio_queue: {audio_queue.qsize()} | sentence_queue: {sentence_queue.qsize()} | translation_queue: {translation_queue.qsize()}")
        time.sleep(5)

# ffmpeg를 이용하여 .webm 파일을 WAV (BytesIO)로 변환하는 함수
def convert_webm_to_wav_bytes(webm_path: str) -> io.BytesIO:
    try:
        out, _ = (
            ffmpeg
            .input(webm_path)
            .output("pipe:", format="wav", acodec="pcm_s16le", ac=1, ar="16000")
            .run(capture_stdout=True, capture_stderr=True)
        )
        return io.BytesIO(out)
    except Exception as e:
        print(f"[DEBUG] ffmpeg 변환 오류: {e}")
        raise RuntimeError("ffmpeg 변환 실패")


# 웹소켓 클라이언트 저장 (결과 전송용)
websocket_clients = []

# STT WebSocket 엔드포인트
@app.websocket("/ws/stt")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[DEBUG] WebSocket 연결됨")
    websocket_clients.append(websocket)

    try:
        while True:
            data = await websocket.receive_bytes()
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_file:
                temp_file_path = temp_file.name
                temp_file.write(data)
            
            try:
                # ffmpeg로 .webm → .wav 변환 (BytesIO 형태)
                wav_buffer = convert_webm_to_wav_bytes(temp_file_path)
                os.unlink(temp_file_path)  # 임시 파일 삭제

                # BytesIO 버퍼에서 오디오 데이터 읽기
                wav_buffer.seek(0)  # 버퍼 포인터 초기화
                audio_data, sample_rate = sf.read(wav_buffer, dtype='float32')
                print(f"[DEBUG] 수신된 오디오 데이터: shape {audio_data.shape}, sample_rate {sample_rate}")

                # 스테레오면 모노로 변환
                if len(audio_data.shape) > 1:
                    audio_data = audio_data.mean(axis=1).reshape(-1, 1)
                else:
                    audio_data = audio_data.reshape(-1, 1)

                # audio_queue에 추가 (STT 처리 스레드로 전달)
                audio_queue.put(audio_data)
                print(f"[DEBUG] audio_queue에 데이터 추가됨. 현재 queue 크기: {audio_queue.qsize()}")
            except Exception as e:
                print(f"[DEBUG] 오디오 처리 오류: {e}")
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
    except WebSocketDisconnect:
        print("[DEBUG] WebSocket 연결 종료됨")
        if websocket in websocket_clients:
            websocket_clients.remove(websocket)

@app.post("/api/process-audio")
async def process_audio(audio: UploadFile = File(...)):
    try:
        # 업로드된 파일 내용을 읽음
        contents = await audio.read()
        
        # 임시 파일에 저장
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_file:
            temp_file.write(contents)
            temp_file_path = temp_file.name
        print(f"[DEBUG] 업로드된 파일 임시 저장됨: {temp_file_path}")
        
        try:
            # ffmpeg로 .webm → .wav 변환
            wav_buffer = convert_webm_to_wav_bytes(temp_file_path)
            os.unlink(temp_file_path)  # 임시 파일 삭제

            # BytesIO 버퍼의 위치 초기화 및 오디오 데이터 읽기
            wav_buffer.seek(0)
            audio_np, sample_rate = sf.read(wav_buffer, dtype='float32')
            print(f"[DEBUG] 직접 업로드: audio_np shape: {audio_np.shape}, sample_rate: {sample_rate}")

            # 스테레오면 모노로 변환
            if len(audio_np.shape) > 1:
                audio_np = audio_np.mean(axis=1).reshape(-1, 1)
            else:
                audio_np = audio_np.reshape(-1, 1)
            
            # audio_queue에 추가
            audio_queue.put(audio_np)
            print(f"[DEBUG] audio_queue에 데이터 추가됨. 현재 queue 크기: {audio_queue.qsize()}")
            return JSONResponse({"status": "처리 중", "queue_size": audio_queue.qsize()})
        except Exception as e:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            print(f"[DEBUG] 오디오 처리 중 예외 발생: {e}")
            raise e
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# 결과 전송 함수 - 받은 결과를 웹소켓 클라이언트에 보내줍니다.
async def send_to_clients(message):
    for client in list(websocket_clients):
        try:
            await client.send_json(message)
        except Exception as ex:
            print(f"[DEBUG] send_to_clients 오류: {ex}")
            if client in websocket_clients:
                websocket_clients.remove(client)

# 결과 전송 태스크: STT, 번역 결과를 웹소켓 클라이언트에 주기적으로 전송
async def result_sender_task():
    global latest_transcription, latest_translation
    while True:
        try:
            if not sentence_queue.empty():
                result = sentence_queue.get_nowait()
                if isinstance(result, tuple):
                    text, lang = result
                    latest_transcription = text
                else:
                    latest_transcription = result

                print(f"[DEBUG] STT 결과: {latest_transcription}")
                asyncio.create_task(send_to_clients({"type": "transcription", "text": latest_transcription}))
                sentence_queue.task_done()
            if not translation_queue.empty():
                translation = translation_queue.get_nowait()
                latest_translation = translation

                print(f"[DEBUG] 번역 결과: {latest_translation}")
                asyncio.create_task(send_to_clients({"type": "translation", "text": latest_translation}))
                translation_queue.task_done()
        except Exception as e:
            print(f"[DEBUG] 결과 전송 중 오류: {e}")
        await asyncio.sleep(0.1)

# 최신 변환 결과 API
@app.get("/api/transcription")
async def get_transcription():
    return JSONResponse({"text": latest_transcription})

# 최신 번역 결과 API
@app.get("/api/translation")
async def get_translation():
    return JSONResponse({"text": latest_translation})

# HTML 파일 제공 (템플릿 경로가 올바른지 확인)
@app.get("/")
async def root():
    return FileResponse("templates/index.html")

# 음성 데이터 직접 업로드 API (디버깅용)
@app.post("/api/audio")
async def process_audio(audio_data: AudioData):
    try:
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(audio_data.audio_data)
        try:
            wav_buffer = convert_webm_to_wav_bytes(temp_file_path)
            os.unlink(temp_file_path)
            
            wav_buffer.seek(0)
            audio_np, sample_rate = sf.read(wav_buffer, dtype='float32')
            print(f"[DEBUG] 직접 업로드: audio_np shape: {audio_np.shape}, sample_rate: {sample_rate}")
            
            if len(audio_np.shape) > 1:
                audio_np = audio_np.mean(axis=1).reshape(-1, 1)
            else:
                audio_np = audio_np.reshape(-1, 1)
            audio_queue.put(audio_np)
            return JSONResponse({"status": "처리 중"})
        except Exception as e:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            raise e
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# TTS API
@app.post("/api/tts")
async def tts_api(request: TTSRequest):
    try:
        if hasattr(tts_thread, 'single_tts'):
            if asyncio.iscoroutinefunction(tts_thread.single_tts):
                audio_bytes = await tts_thread.single_tts(request.text)
            else:
                loop = asyncio.get_event_loop()
                audio_bytes = await loop.run_in_executor(None, tts_thread.single_tts, request.text)
            return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/mpeg")
        else:
            return JSONResponse(status_code=500, content={"error": "TTS 기능을 사용할 수 없습니다."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
