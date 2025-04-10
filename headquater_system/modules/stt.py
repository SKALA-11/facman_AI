# modules/stt.py

import sys
import numpy as np
import time
import os
import tempfile
import soundfile as sf
import queue
import webrtcvad
import threading
from config import SAMPLE_RATE, DEFAULT_LANGUAGE, CLIENT
from modules.audio import audio_queue
from modules.utils import sanitize_language_code, get_log_filenames

# 전역 변수 (메인에서 관리하도록 할 수도 있음)
detected_language = None
language_lock = threading.Lock()

vad = webrtcvad.Vad(2)  # 공격성 수준: 0~3 (숫자가 높을수록 민감)

def is_speech(buffer, sample_rate=16000, frame_duration_ms=30, speech_threshold=0.3):
    audio_int16 = np.int16(buffer * 32767)
    audio_bytes = audio_int16.tobytes()
    frame_size = int(sample_rate * (frame_duration_ms / 1000.0))
    num_frames = len(audio_int16) // frame_size
    if num_frames == 0:
        return False
    speech_frames = 0
    for i in range(num_frames):
        start = i * frame_size * 2  # 2바이트 per 샘플
        frame = audio_bytes[start: start + frame_size * 2]
        if len(frame) < frame_size * 2:
            break
        if vad.is_speech(frame, sample_rate):
            speech_frames += 1
    fraction = speech_frames / num_frames
    return fraction >= speech_threshold

def detect_language(audio_path):
    try:
        with open(audio_path, "rb") as audio_file:
            response = CLIENT.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json"
            )
        detected_lang = response.language
        sanitized = sanitize_language_code(detected_lang)
        print(f"[DEBUG] 감지된 언어 (보정됨): {sanitized}")
        return sanitized
    except Exception as e:
        print(f"언어 감지 오류: {e}", file=sys.stderr)
        return DEFAULT_LANGUAGE

def stt_processing_thread(sentence_queue, recording_active, target_language):
    global detected_language
    buffer = np.zeros((0, 1), dtype=np.float32)
    silence_threshold = 0.02
    silence_duration_threshold = 1.0
    silence_start = None
    language_detected_once = False

    while True:
        try:
            data = audio_queue.get(timeout=1)
            buffer = np.concatenate((buffer, data), axis=0)
            current_time = time.time()
            amplitude = np.mean(np.abs(data))
            if amplitude < silence_threshold:
                if silence_start is None:
                    silence_start = current_time
                elif current_time - silence_start >= silence_duration_threshold:
                    if len(buffer) > int(SAMPLE_RATE * 0.5):
                        if not is_speech(buffer):
                            buffer = np.zeros((0, 1), dtype=np.float32)
                            silence_start = None
                            audio_queue.task_done()
                            continue
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                            sf.write(f.name, buffer, SAMPLE_RATE)
                            if not language_detected_once:
                                lang_code = detect_language(f.name)
                                if lang_code:
                                    with language_lock:
                                        detected_language = lang_code
                                    language_detected_once = True

                            with language_lock:
                                current_lang = detected_language if detected_language is not None else DEFAULT_LANGUAGE
                            with open(f.name, "rb") as audio_file:
                                response = CLIENT.audio.transcriptions.create(
                                    model="whisper-1",
                                    file=audio_file,
                                    language=current_lang,
                                    prompt="We're now on meeting. Please transcribe exactly what you hear."
                                )
                            os.unlink(f.name)
                        text = response.text.strip()
                        if text:
                            print(f"[DEBUG] STT 결과: {text}")
                            source_log, _ = get_log_filenames(detected_language, target_language)
                            with open(source_log, "a", encoding="utf-8") as f:
                                f.write(text + "\n")
                            with language_lock:
                                src_lang = detected_language if detected_language is not None else DEFAULT_LANGUAGE
                            sentence_queue.put((text, src_lang))
                    buffer = np.zeros((0, 1), dtype=np.float32)
                    silence_start = None
            else:
                silence_start = None
            audio_queue.task_done()
        except queue.Empty:
            continue
