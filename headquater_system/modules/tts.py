# modules/tts.py
import os
import io
import sys
import queue
import tempfile
import base64
import sounddevice as sd
import soundfile as sf
from pathlib import Path
from config import CLIENT
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- API 엔드포인트용 함수 ---
def generate_tts_audio(text_to_speak: str, voice: str = "nova", model: str = "tts-1") -> bytes:
    """
    주어진 텍스트에 대한 TTS 오디오(MP3)를 생성하고 바이트 데이터를 반환합니다.

    Args:
        text_to_speak: 음성으로 변환할 텍스트.
        voice: 사용할 음성 (OpenAI에서 지원하는 'alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer' 등).
        model: 사용할 TTS 모델 ('tts-1', 'tts-1-hd').

    Returns:
        MP3 오디오 데이터 바이트.

    Raises:
        ValueError: 텍스트 입력이 비어있을 경우.
        RuntimeError: OpenAI API 호출 또는 오디오 생성 중 오류 발생 시.
    """
    if not text_to_speak:
        logger.error("TTS 오류: 입력 텍스트가 비어 있습니다.")
        raise ValueError("TTS를 위한 텍스트 입력이 비어있습니다.")

    try:
        logger.info(f"[TTS API] 텍스트 음성 변환 요청: '{text_to_speak[:50]}...' (Voice: {voice}, Model: {model})")
        audio_buffer = io.BytesIO() # 메모리 내 오디오 버퍼

        # OpenAI TTS API 호출 (스트리밍 방식)
        with CLIENT.audio.speech.with_streaming_response.create(
            model=model,
            voice=voice,
            input=text_to_speak,
            response_format="mp3" # 출력 포맷 지정
        ) as response:
            # 스트리밍 데이터를 메모리 버퍼에 기록
            for chunk in response.iter_bytes(chunk_size=4096):
                audio_buffer.write(chunk)

        audio_buffer.seek(0) # 버퍼의 시작점으로 포인터 이동
        audio_bytes = audio_buffer.getvalue() # 전체 오디오 바이트 데이터 가져오기
        logger.info(f"[TTS API] 오디오 생성 완료 (크기: {len(audio_bytes)} 바이트)")
        return audio_bytes

    except Exception as e:
        logger.exception(f"TTS API 오류: 텍스트 '{text_to_speak[:50]}...' 변환 중 오류 발생. 오류: {e}")
        # 발생한 예외를 상위 호출자(API 엔드포인트)에게 전달
        raise RuntimeError(f"TTS 오디오 생성 실패: {e}") from e


def tts_thread(translation_queue, recording_active):
    while True:
        try:
            text_to_speak = translation_queue.get(timeout=1)
            print(f"[TTS] 합성할 텍스트: {text_to_speak}")
            try:
                recording_active.clear()
                print("[시스템] TTS 출력 중 - 녹음 일시 중지됨")
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                    temp_audio_path = Path(temp_file.name)
                    print(f"[DEBUG] TTS 임시 파일 경로: {temp_audio_path}")
                with CLIENT.audio.speech.with_streaming_response.create(
                    model="gpt-4o-mini-tts",
                    voice="nova",  # 선택 옵션
                    input=text_to_speak,
                    # instructions="Speak in a clear and natural tone."
                ) as response:
                    response.stream_to_file(temp_audio_path)
                data, fs = sf.read(str(temp_audio_path), dtype='float32')
                sd.play(data, fs)
                sd.wait()
                os.unlink(str(temp_audio_path))
            except Exception as e:
                print(f"TTS 오류: {e}", file=sys.stderr)
            finally:
                recording_active.set()

            print("[시스템] TTS 출력 완료 - 녹음 재개됨")
            translation_queue.task_done()
            
        except queue.Empty:
            continue

def tts_process(translation):
    print(f"[TTS] 합성할 텍스트: {translation}")
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_audio_path = Path(temp_file.name)
            print(f"[DEBUG] TTS 임시 파일 경로: {temp_audio_path}")

       # TTS API 호출 (model="tts-1") – CLIENT.audio.speech.with_streaming_response.create 사용
        with CLIENT.audio.speech.with_streaming_response.create(
            model="tts-1",      # TTS 처리 모델: tts-1
            voice="nova",       # 선택 옵션 (원하는 목소리로 설정)
            input=translation,
            # instructions="Optional additional instructions"  # 필요 시 추가 지침
        ) as response:
            response.stream_to_file(temp_audio_path)
        
        # 생성된 음성 파일을 binary 모드로 읽은 후 base64로 인코딩
        with open(str(temp_audio_path), "rb") as audio_file:
            audio_bytes = audio_file.read()
        base64_audio = base64.b64encode(audio_bytes).decode('utf-8')
        print(f"[DEBUG] TTS 음성이 base64로 인코딩됨 (길이: {len(base64_audio)} 문자)")
        
        # 임시 파일 삭제
        os.unlink(str(temp_audio_path))
        
        # tts_result_queue에 base64 인코딩 음성 데이터를 저장
        return base64_audio
    except Exception as e:
        print(f"TTS 오류: {e}", file=sys.stderr)
        return ""