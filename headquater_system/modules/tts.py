# modules/tts.py

import sys
import queue
import tempfile
import os
import sounddevice as sd
import soundfile as sf
from pathlib import Path
import openai
from config import CLIENT

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
                with CLIENT.audio.speech.with_streaming_response.create(
                    model="gpt-4o-mini-tts",
                    voice="nova",  # 선택 옵션
                    input=text_to_speak,
                    instructions="Speak in a clear and natural tone."
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
