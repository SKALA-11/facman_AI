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
import io 

from modules.stt import stt_processing_thread
from modules.tts import tts_thread, generate_tts_audio
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
transcription_queue = queue.Queue()
translated_queue = queue.Queue()


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
        args=(audio_queue, sentence_queue, transcription_queue, recording_active, "ko"),
        daemon=True
    ).start()
    threading.Thread(
        target=translation_thread,
        args=(sentence_queue, translation_queue, translated_queue, "en"),
        daemon=True
    ).start()

    # 디버그: 주기적으로 각 큐의 상태를 로깅하는 별도 스레드를 시작합니다.
    threading.Thread(target=debug_queues, daemon=True).start()

    # 결과 전송 태스크를 메인 이벤트 루프에 스케줄링합니다.
    asyncio.create_task(result_sender_task())
    # asyncio.run(result_sender_task())


# HTML 파일 제공 (템플릿 경로가 올바른지 확인)
# @app.get("/")
# async def root():
#     return FileResponse("templates/index.html")


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
 /ai/hq/
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
            print(f"[DEBUG] 임시 파일 생성됨: {temp_file_path}")
            
            try:
                # ffmpeg로 .webm → .wav 변환 (BytesIO 형태)
                wav_buffer = convert_webm_to_wav_bytes(temp_file_path)
                os.unlink(temp_file_path)  # 임시 파일 삭제

                if wav_buffer is None:
                    print("[DEBUG] 변환 실패한 청크 건너뜀")
                    continue

                # BytesIO 버퍼에서 오디오 데이터 읽기
                wav_buffer.seek(0)
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

# 결과 전송 함수 - 받은 결과를 웹소켓 클라이언트에 보내줍니다.
async def send_to_clients(message):
    for client in list(websocket_clients):
        try:
            await client.send_json(message)
            print(f"[DEBUG] send_to_clients 완료됨")

        except Exception as ex:
            print(f"[DEBUG] send_to_clients 오류: {ex}")
            if client in websocket_clients:
                websocket_clients.remove(client)

# 결과 전송 태스크: STT, 번역 결과를 웹소켓 클라이언트에 주기적으로 전송
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

# 최신 변환 결과 API
@app.get("/api/transcription")
async def get_transcription():
    global latest_transcription
    if not latest_transcription:
        print("[DEBUG] 최신 변환 결과가 없습니다.")
        return JSONResponse({"text": "No transcription available yet."})
    print(f"[DEBUG] 최신 변환 결과 반환: {latest_transcription}")
    return JSONResponse({"text": latest_transcription}) 

# 최신 번역 결과 API
@app.get("/api/translation")
async def get_translation():
    return JSONResponse({"text": latest_translation})

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
    """주어진 텍스트를 MP3 오디오로 변환하여 반환합니다."""
    try:
        if not request.text:
            return JSONResponse(status_code=400, content={"error": "텍스트가 비어 있습니다."})

        # 현재 실행 중인 이벤트 루프 가져오기
        loop = asyncio.get_running_loop()

        print(f"[API /api/tts] 요청 수신: '{request.text}'")

        # generate_tts_audio 함수는 동기 함수이고 API 호출 등 블로킹 작업이 있을 수 있으므로,
        # run_in_executor를 사용하여 FastAPI의 메인 이벤트 루프를 차단하지 않도록 합니다.
        audio_bytes = await loop.run_in_executor(
            None,  # 기본 스레드 풀 사용
            generate_tts_audio, # 실행할 동기 함수
            request.text  # 함수에 전달할 인자
        )

        print(f"[API /api/tts] 오디오 스트림 응답 생성")
        # 생성된 오디오 바이트를 StreamingResponse로 반환합니다.
        # io.BytesIO로 감싸서 스트리밍 가능한 파일 형식으로 만듭니다.
        return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/mpeg") # MP3의 MIME 타입

    except ValueError as ve: # generate_tts_audio에서 빈 텍스트 입력 시 발생
         print(f"[API Error] TTS 요청 오류: {ve}")
         return JSONResponse(status_code=400, content={"error": str(ve)})
    except RuntimeError as re: # generate_tts_audio 내 API 호출 등에서 오류 발생 시
        print(f"[API Error] TTS 생성 중 오류: {re}")
        return JSONResponse(status_code=500, content={"error": str(re)})
    except Exception as e:
        # 예상치 못한 다른 오류 처리
        print(f"[API Error] TTS 엔드포인트에서 예상치 못한 오류: {e}")
        return JSONResponse(status_code=500, content={"error": f"서버 내부 오류 발생: {str(e)}"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)