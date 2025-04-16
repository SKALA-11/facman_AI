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

    while True:
        try:
            # user.audio_queue에 (audio_np, sample_rate) 형태의 데이터를 넣었다고 가정
            data_tuple = user.audio_queue.get(timeout=1)
            if isinstance(data_tuple, tuple):
                data, sample_rate = data_tuple
            else:
                data = data_tuple

            # Optional: 음성 체크 (is_speech) – 파일 전체에 대해서 음성의 유무를 판단
            if len(data) < int(sample_rate * 0.5) or not is_speech(data):
                print(f"[DEBUG] {user.name} - 음성 없음 또는 너무 짧은 발화")
                user.audio_queue.task_done()
                continue
                
            # 임시 파일에 저장하여 STT 처리 (Whisper API 호출)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                sf.write(f.name, data, sample_rate, format='WAV', subtype='PCM_16')
                # 최초 한 번 언어 감지 (필요 시)
                # if user.detected_language is None:
                #     lang_code = detect_language(f.name)
                #     if lang_code:
                #         with language_lock:
                #             user.detected_language = lang_code
                # with language_lock:
                #     current_lang = user.detected_language if user.detected_language is not None else DEFAULT_LANGUAGE
                # Whisper API 호출
                with open(f.name, "rb") as audio_file:
                    response = CLIENT.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language=user.source_lang,
                        prompt="We're now on meeting. Please transcribe exactly what you hear."
                    )
                os.unlink(f.name)
            
            text = response.text.strip()

            if text:
                print(f"[DEBUG] STT 결과: {text}")
                source_log, _ = get_log_filenames(user.source_lang, user.target_lang)
                with open(source_log, "a", encoding="utf-8") as f:
                    f.write(text + "\n")
                with language_lock:
                    src_lang = user.source_lang if user.source_lang is not None else DEFAULT_LANGUAGE
                # 전사 결과를 사용자 전용 큐에 저장
                # 전사 텍스트가 만들어진 후 (예, text 변수에 있음)
                if text:
                    print(f"[DEBUG] STT 결과: {text}")

                    # 발화자 정보를 포함하는 dictionary 생성
                    speaker_info = {
                        "name": user.name,
                        "language": user.source_lang
                    }
                    
                    # 전사 결과를 tuple로 묶음
                    user.sentence_queue.put((text, src_lang))
                    user.transcription_queue.put((text, src_lang))
                    # transcription_result = (speaker_info, text)
                    
                    # 전역 디스패처 함수(예: dispatch_transcription)를 호출하여 결과를 모든 사용자에게 분배
                    # dispatch_transcription(speaker_info, text)

            user.audio_queue.task_done()
            
        except queue.Empty:
                continue
        except Exception as e:
            print(f"STT 처리 중 오류 발생: {e}", file=sys.stderr)
