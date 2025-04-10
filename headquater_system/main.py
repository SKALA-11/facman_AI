# main.py
import threading
import time
import queue
from fastapi import FastAPI
import uvicorn

from modules.audio import audio_collection_thread, audio_queue, recording_active
from modules.stt import stt_processing_thread, detected_language
from modules.translation import translation_thread
from modules.tts import tts_thread
from modules.utils import update_display
from config import TARGET_LANGUAGE  # 필요에 따라 DEFAULT_LANGUAGE도 import

# FastAPI 애플리케이션 인스턴스 직접 생성
app = FastAPI()

@app.get("/")
async def read_root():
    return {"message": "FastAPI 서버와 백그라운드 스레드가 실행 중입니다."}

def start_background_threads():
    # STT 및 번역, TTS 처리를 위한 큐 생성
    sentence_queue = queue.Queue()
    translation_queue = queue.Queue()

    # 오디오 캡처 스레드 생성
    t_audio = threading.Thread(target=audio_collection_thread)

    # STT 처리 스레드 생성 (백그라운드에서 음성 인식을 수행)
    t_stt = threading.Thread(
        target=stt_processing_thread,
        args=(
            sentence_queue,
            recording_active,
            TARGET_LANGUAGE
        )
    )

    # 번역 스레드 생성
    t_trans = threading.Thread(
        target=translation_thread,
        args=(sentence_queue, translation_queue, TARGET_LANGUAGE)
    )

    # TTS 스레드 생성
    t_tts = threading.Thread(
        target=tts_thread,
        args=(
            translation_queue,
            recording_active
        )
    )

    # 모든 스레드를 데몬 모드로 설정 (메인 프로세스 종료 시 스레드도 종료)
    threads = [t_audio, t_stt, t_trans, t_tts]
    for t in threads:
        t.daemon = True
        t.start()

    print("백그라운드 스레드가 시작되었습니다.")

def main():
    # 백그라운드 스레드를 먼저 실행
    start_background_threads()
    
    # uvicorn으로 FastAPI 서버 실행 (포트 번호는 필요에 따라 변경)
    uvicorn.run(app, host="0.0.0.0", port=8002)

if __name__ == "__main__":
    main()
