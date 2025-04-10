# main.py

import threading
import time
import queue
from modules.audio import audio_collection_thread, audio_queue, recording_active
from modules.stt import stt_processing_thread, language_lock, detected_language
from modules.translation import translation_thread
from modules.tts import tts_thread
from modules.utils import update_display
from config import TARGET_LANGUAGE, DEFAULT_LANGUAGE

def main():
    sentence_queue = queue.Queue()
    translation_queue = queue.Queue()
    
    # Start audio collection thread
    t_audio = threading.Thread(target=audio_collection_thread)
    
    # Start STT thread: 전달인자로 sentence_queue, recording_active, 타겟 언어, 디스플레이 업데이트 함수 전달
    t_stt = threading.Thread(target=stt_processing_thread, args=(sentence_queue, recording_active, TARGET_LANGUAGE, lambda: update_display(detected_language, TARGET_LANGUAGE, "녹음 중" if recording_active.is_set() else "녹음 일시 중지")))
    
    # Start Translation thread
    t_trans = threading.Thread(target=translation_thread, args=(sentence_queue, translation_queue, TARGET_LANGUAGE))
    
    # Start TTS thread
    t_tts = threading.Thread(target=tts_thread, args=(translation_queue, recording_active, lambda: update_display(detected_language, TARGET_LANGUAGE, "녹음 중" if recording_active.is_set() else "녹음 일시 중지")))
    
    threads = [t_audio, t_stt, t_trans, t_tts]
    for t in threads:
        t.daemon = True
        t.start()
    
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("프로그램 종료 중...")

if __name__ == "__main__":
    main()
