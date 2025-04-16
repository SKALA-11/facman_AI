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

from config import DEFAULT_LANGUAGE, CLIENT
from modules.utils import sanitize_language_code, get_log_filenames

from modules.translation import translation_process
from modules.tts import tts_process

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


def stt_processing(user, data, sample_rate):
    """
    사용자 객체의 audio_queue에서 오디오 데이터를 읽어 STT 처리를 수행하고,
    STT된 text를 반환합니다.
    """
    try:
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
                    
        text = response.text.strip()

        return text
        
    except Exception as e:
        print(f"STT 처리 중 오류 발생: {e}", file=sys.stderr)
        return ""
    finally:
        # 예외 발생 여부와 상관없이 임시 파일이 있다면 삭제합니다.
        if f.name and os.path.exists(f.name):
            try:
                os.unlink(f.name)
            except Exception as del_e:
                print(f"임시 파일 삭제 오류: {del_e}", file=sys.stderr)

def stt_processing_thread(user):
    """
    사용자 객체의 audio_queue에서 오디오 데이터를 읽어 STT 처리를 수행하고,
    결과를 user.sentence_queue와 user.transcription_queue에 넣습니다.
    """

    while True:
        try:
            # user.audio_queue에 (audio_np, sample_rate) 형태의 데이터를 넣었다고 가정
            data_tuple = user.audio_queue.get(timeout=1)
            try:
                if isinstance(data_tuple, tuple):
                    data, sample_rate = data_tuple
                else:
                    data = data_tuple
                    sample_rate = 16000 # 기본값은 16000

                # Optional: 음성 체크 (is_speech) – 파일 전체에 대해서 음성의 유무를 판단
                if len(data) < int(sample_rate * 0.5) or not is_speech(data):
                    print(f"[DEBUG] {user.name} - 음성 없음 또는 너무 짧은 발화")
                    continue
                    
                text = stt_processing(user, data, sample_rate)
                if not text:
                    print(f"[DEBUG] {user.name} - STT 결과 없음")
                    continue
            
                print(f"[DEBUG] STT 결과: {text}")

                # 전사 결과를 tuple로 묶음
                # user.sentence_queue.put((text, src_lang))
                # user.transcription_queue.put((text, src_lang))
                # transcription_result = (speaker_info, text)
                
                try:
                    translation = translation_process(user, text)
                except Exception as te:
                    print(f"[DEBUG] {user.name} 번역 호출 중 오류: {te}", file=sys.stderr)
                    translation = ""
                
                try:
                    tts_voice = tts_process(translation)
                except Exception as te:
                    print(f"[DEBUG] {user.name} tts 호출 중 오류: {te}", file=sys.stderr)
                    tts_voice = ""

                user.final_results_queue.put((text, translation, tts_voice))
            finally:
                user.audio_queue.task_done()
            
        except queue.Empty:
                continue
        except Exception as e:
            print(f"STT 처리 중 오류 발생: {e}", file=sys.stderr)
