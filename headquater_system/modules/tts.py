# modules/tts.py
import tempfile, os, io, sys
import uuid
import base64

from pathlib import Path
from config import CLIENT
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TTS_DIR = Path("/tmp/tts")
TTS_DIR.mkdir(parents=True, exist_ok=True)

def tts_process(translation):
    print(f"[TTS] 합성할 텍스트: {translation}")
    try:
        file_id = uuid.uuid4().hex
        temp_audio_path = TTS_DIR / f"{file_id}.mp3"

       # TTS API 호출 (model="tts-1") – CLIENT.audio.speech.with_streaming_response.create 사용
        with CLIENT.audio.speech.with_streaming_response.create(
            model="tts-1",      # TTS 처리 모델: tts-1
            voice="nova",       # 선택 옵션 (원하는 목소리로 설정)
            input=translation,
            # response_format="opus"
            # instructions="Optional additional instructions"  # 필요 시 추가 지침
        ) as response:
            response.stream_to_file(temp_audio_path)

        # tts_result_queue에 base64 인코딩 음성 데이터를 저장
        return file_id
    
    except Exception as e:
        print(f"TTS 오류: {e}", file=sys.stderr)
        return ""