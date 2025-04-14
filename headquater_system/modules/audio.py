# modules/audio.py

import sys
import sounddevice as sd
import numpy as np
import time
import queue
from config import SAMPLE_RATE, BLOCK_SIZE

# 오디오 데이터와 녹음 제어를 위한 전역 변수
audio_queue = queue.Queue()
import threading
recording_active = threading.Event()
recording_active.set()

def audio_callback(indata, frames, time_info, status):
    if status:
        print(f"상태: {status}", file=sys.stderr)
    if recording_active.is_set():
        audio_queue.put(indata.copy())

def audio_collection_thread():
    pass
    # try:
    #     with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
    #                         callback=audio_callback, blocksize=BLOCK_SIZE):
    #         print("🎙️ 음성 수집 시작...")
    #         while True:
    #             time.sleep(0.1)
    # except Exception as e:
    #     print(f"오디오 스트림 오류: {e}", file=sys.stderr)
