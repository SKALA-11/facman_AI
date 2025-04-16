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
from modules.dispatcher import dispatch_transcription

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
    start_time = None
    process_threshold_seconds = 3.0
    language_detected_once = False

    while True:
        try:
            # user.audio_queue에 (audio_np, sample_rate) 형태의 데이터를 넣었다고 가정
            data_tuple = user.audio_queue.get(timeout=1)
            if isinstance(data_tuple, tuple):
                data, sample_rate = data_tuple
            else:
                data = data_tuple
            # 버퍼가 비어있으면 시작 시간을 기록
            if start_time is None:
                start_time = time.time()
            
            # 버퍼가 비어있으면 시작 시간을 기록
            buffer = np.concatenate((buffer, data), axis=0)
            current_time = time.time()
            # print(f"[DEBUG] 사용자 {user.name} - 버퍼 크기: {buffer.shape[0]} (목표: {SAMPLE_RATE})")
            if current_time - start_time >= process_threshold_seconds or len(buffer) >= SAMPLE_RATE:
                # Optional: 침묵 체크 (발화가 충분한지 확인)
                if len(buffer) > int(SAMPLE_RATE * 0.5):
                    if not is_speech(buffer):
                        # print(f"[DEBUG] 사용자 {user.name} - 음성 없음, 버퍼 초기화")
                        buffer = np.zeros((0, 1), dtype=np.float32)
                        start_time = None
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
                        # 전사 텍스트가 만들어진 후 (예, text 변수에 있음)
                        if text:
                            print(f"[DEBUG] STT 결과: {text}")
                            # 로그 저장 등 기존 작업 생략 가능...

                            # 발화자 정보를 포함하는 dictionary 생성
                            speaker_info = {
                                "connection_id": user.connection_id, 
                                "name": user.name,
                                "language": user.detected_language if user.detected_language else user.source_lang
                            }

                            # 전사 결과를 tuple로 묶음
                            transcription_result = (speaker_info, text)
                            
                            # 전역 디스패처 함수(예: dispatch_transcription)를 호출하여 결과를 모든 사용자에게 분배
                            dispatch_transcription(speaker_info, text)
                buffer = np.zeros((0, 1), dtype=np.float32)
                start_time = None
            user.audio_queue.task_done()
        except queue.Empty:
                continue
        except Exception as e:
            print(f"STT 처리 중 오류 발생: {e}", file=sys.stderr)
