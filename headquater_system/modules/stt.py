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

# def stt_processing_thread(audio_queue, sentence_queue, transcription_queue, recording_active, target_language):
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
from modules.utils import sanitize_language_code, get_log_filenames

# 전역 변수 (필요 시 메인에서 관리)
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

def stt_processing_thread(user):
    """
    사용자 객체의 audio_queue에서 오디오 데이터를 읽어 STT 처리를 수행하고,
    결과를 user.sentence_queue와 user.transcription_queue에 넣습니다.
    """
    buffer = np.zeros((0, 1), dtype=np.float32)
    silence_threshold = 0.02
    silence_duration_threshold = 0.5  # 실시간성 고려
    silence_start = None
    language_detected_once = False

    queue_threshold = 10   # 10개 이상의 오디오 청크가 쌓였을 때 처리
    max_wait_time = 2        # 최대 2초 이상 기다리면 강제로 처리
    last_process_time = time.time()
    audio_chunk_count = 0

    while True:
        try:
            # user.audio_queue에 (audio_np, sample_rate) 형태의 데이터를 넣었다고 가정
            data_tuple = user.audio_queue.get(timeout=1)
            if isinstance(data_tuple, tuple):
                data, sample_rate = data_tuple
            else:
                data = data_tuple
            buffer = np.concatenate((buffer, data), axis=0)
            current_time = time.time()
            amplitude = np.mean(np.abs(data))
            audio_chunk_count += 1

            process_buffer = False

            # 침묵 감지
            if amplitude < silence_threshold:
                if silence_start is None:
                    silence_start = current_time
                elif current_time - silence_start >= silence_duration_threshold:
                    process_buffer = True
            else:
                silence_start = None

            # 큐 임계값 도달
            if audio_chunk_count >= queue_threshold:
                process_buffer = True

            # 최대 대기 시간 초과
            if current_time - last_process_time >= max_wait_time:
                process_buffer = True

            if process_buffer:
                if len(buffer) > int(SAMPLE_RATE * 0.5):
                    if not is_speech(buffer):
                        buffer = np.zeros((0, 1), dtype=np.float32)
                        silence_start = None
                        user.audio_queue.task_done()
                        continue
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                        sf.write(f.name, buffer, SAMPLE_RATE, format='WAV', subtype='PCM_16')
                        if not language_detected_once:
                            lang_code = detect_language(f.name)
                            if lang_code:
                                with language_lock:
                                    user.detected_language = lang_code
                                language_detected_once = True
                        with language_lock:
                            current_lang = user.detected_language if user.detected_language is not None else DEFAULT_LANGUAGE
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
                        source_log, _ = get_log_filenames(user.detected_language, user.target_lang)
                        with open(source_log, "a", encoding="utf-8") as f:
                            f.write(text + "\n")
                        with language_lock:
                            src_lang = user.detected_language if user.detected_language is not None else DEFAULT_LANGUAGE
                        # 전사 결과를 사용자 전용 큐에 저장
                        user.sentence_queue.put((text, src_lang))
                        user.transcription_queue.put((text, src_lang))
                buffer = np.zeros((0, 1), dtype=np.float32)
                audio_chunk_count = 0
                last_process_time = current_time
            user.audio_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            print(f"STT 처리 중 오류 발생: {e}", file=sys.stderr)
