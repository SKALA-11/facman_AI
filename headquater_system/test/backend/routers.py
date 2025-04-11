# routers.py

from fastapi import APIRouter, UploadFile, File
from utils import sanitize_language_code
from config import CLIENT
from modules.tts import translation_queue, recording_active
from queue import Queue
import tempfile
import threading

router = APIRouter()

# sentence_queue는 main에서 전달받는다고 가정
sentence_queue: Queue = None  # 나중에 설정할 수 있게 둠

@router.post("/trigger-stt-tts")
async def trigger_stt_tts(file: UploadFile = File(...)):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(await file.read())
            temp_path = tmp.name

        with open(temp_path, "rb") as audio_file:
            stt_response = CLIENT.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json"
            )

        detected_lang = sanitize_language_code(stt_response.language)
        text = stt_response.text.strip()

        print(f"[FastAPI STT] 감지된 언어: {detected_lang}")
        print(f"[FastAPI STT] 텍스트: {text}")

        if sentence_queue:
            sentence_queue.put((text, detected_lang))
        else:
            print("[경고] sentence_queue가 설정되지 않음")

        return {"text": text, "language": detected_lang}

    except Exception as e:
        print(f"[에러] {e}")
        return {"error": str(e)}
