# from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# from fastapi.responses import FileResponse
# from fastapi.middleware.cors import CORSMiddleware
# from starlette.staticfiles import StaticFiles
# import threading
# from modules.stt import stt_processing_thread
# from modules.tts import tts_thread
# from modules.translation import translation_thread
# from modules.audio import audio_collection_thread, audio_queue, recording_active
# import queue

# app = FastAPI()

# # CORS 설정 (로컬 테스트 용도)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # 실제 배포시 도메인 제한
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # 전역 큐
# sentence_queue = queue.Queue()
# translation_queue = queue.Queue()

# @app.on_event("startup")
# async def startup_event():
#     threading.Thread(target=audio_collection_thread, daemon=True).start()
#     threading.Thread(target=stt_processing_thread, args=(sentence_queue, recording_active, "en"), daemon=True).start()
#     threading.Thread(target=translation_thread, args=(sentence_queue, translation_queue, "en"), daemon=True).start()
#     threading.Thread(target=tts_thread, args=(translation_queue, recording_active), daemon=True).start()

# # STT WebSocket
# @app.websocket("/ws/stt")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     print("WebSocket 연결됨")

#     try:
#         while True:
#             data = await websocket.receive_bytes()
#             import soundfile as sf
#             import io
#             # assume 16-bit PCM mono WAV data
#             audio_data, _ = sf.read(io.BytesIO(data), dtype='float32')
#             audio_queue.put(audio_data.reshape(-1, 1))
#     except WebSocketDisconnect:
#         print("WebSocket 연결 종료됨")

# # HTML 테스트용 파일 반환
# @app.get("/")
# async def root():
#     return FileResponse("templates/index.html")

# # 정적 파일 (JS 등)
# app.mount("/templates", StaticFiles(directory="templates"), name="static")

# from pydantic import BaseModel
# from fastapi.responses import StreamingResponse
# from io import BytesIO

# class TTSRequest(BaseModel):
#     text: str

# @app.post("/api/tts")
# async def generate_tts(req: TTSRequest):
#     from modules.tts import CLIENT
#     from config import CLIENT
#     import soundfile as sf

#     with CLIENT.audio.speech.with_streaming_response.create(
#         model="gpt-4o-mini-tts",
#         voice="nova",
#         input=req.text,
#         instructions="Speak in a clear and natural tone."
#     ) as response:
#         buffer = BytesIO()
#         response.stream_to_file(buffer)
#         buffer.seek(0)
#         return StreamingResponse(buffer, media_type="audio/mpeg")


from fastapi import FastAPI, WebSocket, WebSocketDisconnect, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
import threading
import queue
import tempfile
import os
from pathlib import Path
import io
import numpy as np
import soundfile as sf
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

from modules.stt import stt_processing_thread
from modules.tts import tts_thread
from modules.translation import translation_thread
from modules.audio import audio_collection_thread, audio_queue, recording_active
from config import CLIENT

app = FastAPI()

# CORS 설정 (로컬 테스트 용도)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 배포시 도메인 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 큐
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
    threading.Thread(target=audio_collection_thread, daemon=True).start()
    threading.Thread(target=stt_processing_thread, 
                    args=(audio_queue, sentence_queue, recording_active, "ko"), 
                    daemon=True).start()
    threading.Thread(target=translation_thread, 
                    args=(sentence_queue, translation_queue, "en"), 
                    daemon=True).start()
    threading.Thread(target=tts_thread, 
                    args=(translation_queue, recording_active), 
                    daemon=True).start()

# 웹소켓 클라이언트 저장
websocket_clients = []

# STT WebSocket
@app.websocket("/ws/stt")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket 연결됨")
    websocket_clients.append(websocket)

    try:
        while True:
            data = await websocket.receive_bytes()
            
            # 임시 파일로 저장하여 처리
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_file:
                temp_file_path = temp_file.name
                temp_file.write(data)
            
            try:
                # 임시 파일에서 오디오 데이터 읽기
                audio_data, sample_rate = sf.read(temp_file_path, dtype='float32')
                os.unlink(temp_file_path)  # 임시 파일 삭제
                
                # 오디오 큐에 추가
                if len(audio_data.shape) > 1:  # 스테레오면 모노로 변환
                    audio_data = audio_data.mean(axis=1).reshape(-1, 1)
                else:
                    audio_data = audio_data.reshape(-1, 1)
                
                audio_queue.put(audio_data)
            except Exception as e:
                print(f"오디오 처리 오류: {e}")
                os.unlink(temp_file_path)  # 오류 시에도 임시 파일 삭제
                
    except WebSocketDisconnect:
        print("WebSocket 연결 종료됨")
        if websocket in websocket_clients:
            websocket_clients.remove(websocket)


# 결과 전송 스레드
def result_sender():
    global latest_transcription, latest_translation
    while True:
        try:
            # STT 결과 가져오기
            result = sentence_queue.get(block=False)
            if isinstance(result, tuple):
                text, lang = result
                latest_transcription = text
            else:
                latest_transcription = result
            
            # 클라이언트에 전송
            for client in websocket_clients:
                asyncio.run(client.send_json({"type": "transcription", "text": latest_transcription}))
            
            sentence_queue.task_done()
        except queue.Empty:
            pass
        
        try:
            # 번역 결과 가져오기
            translation = translation_queue.get(block=False)
            latest_translation = translation
            
            # 클라이언트에 전송
            for client in websocket_clients:
                asyncio.run(client.send_json({"type": "translation", "text": latest_translation}))
            
            translation_queue.task_done()
        except queue.Empty:
            pass
        
        time.sleep(0.1)

# 최신 변환 결과 API
@app.get("/api/transcription")
async def get_transcription():
    return JSONResponse({"text": latest_transcription})

# 최신 번역 결과 API
@app.get("/api/translation")
async def get_translation():
    return JSONResponse({"text": latest_translation})

# HTML 파일 제공
@app.get("/")
async def root():
    return FileResponse("templates/index.html")

# TTS API
@app.websocket("/ws/stt")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket 연결됨")
    websocket_clients.append(websocket)

    try:
        while True:
            data = await websocket.receive_bytes()
            
            # 임시 파일로 저장하여 처리
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_file:
                temp_file_path = temp_file.name
                temp_file.write(data)

            try:
                # ffmpeg로 .webm → .wav 변환 (BytesIO 형태)
                wav_bytes = convert_webm_to_wav_bytes(temp_file_path)
                os.unlink(temp_file_path)

                # BytesIO에서 오디오 데이터 로딩
                audio_data, sample_rate = sf.read(wav_bytes, dtype='float32')

                if len(audio_data.shape) > 1:  # 스테레오 → 모노
                    audio_data = audio_data.mean(axis=1).reshape(-1, 1)
                else:
                    audio_data = audio_data.reshape(-1, 1)

                audio_queue.put(audio_data)
            except Exception as e:
                print(f"오디오 처리 오류: {e}")
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                
    except WebSocketDisconnect:
        print("WebSocket 연결 종료됨")
        if websocket in websocket_clients:
            websocket_clients.remove(websocket)
# ffmpeg로 .webm → .wav 변환 (BytesIO 형태)

def convert_webm_to_wav_bytes(webm_path: str) -> bytes:
    try:
        out, _ = (
            ffmpeg
            .input(webm_path)
            .output("pipe:", format="wav")
            .run(capture_stdout=True, capture_stderr=True)
        )
        return out
    except ffmpeg.Error as e:
        print(f"ffmpeg 변환 오류: {e.stderr.decode()}")
        raise RuntimeError("ffmpeg 변환 실패")


# 음성 데이터 직접 업로드 API
@app.post("/api/audio")
async def process_audio(audio_data: AudioData):
    try:
        # 바이너리 데이터를 numpy 배열로 변환
        audio_np, _ = sf.read(io.BytesIO(audio_data.audio_data), dtype='float32')
        audio_queue.put(audio_np.reshape(-1, 1))
        return JSONResponse({"status": "처리 중"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/tts")
async def tts_api(request: TTSRequest):
    try:
        audio_bytes = await tts_thread.single_tts(request.text)
        return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/mpeg")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# 필요한 모듈 임포트
import asyncio
import time

# 비동기 이벤트 루프에서 결과 전송 스레드 시작
@app.on_event("startup")
async def start_result_sender():
    threading.Thread(target=result_sender, daemon=True).start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


