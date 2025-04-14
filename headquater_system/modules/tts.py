# modules/tts.py

import sys
import queue
import tempfile
import os
import sounddevice as sd
import soundfile as sf
from pathlib import Path
from config import CLIENT
import io

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

# --- API 엔드포인트용 새 함수 ---
def generate_tts_audio(text_to_speak: str) -> bytes:
    """
    주어진 텍스트에 대한 TTS 오디오를 생성하고 MP3 바이트를 반환합니다.
    API 요청 처리에 사용됩니다.
    """
    if not text_to_speak:
        raise ValueError("TTS를 위한 텍스트 입력이 비어있습니다.")

    try:
        print(f"[TTS API] 요청 텍스트: '{text_to_speak}'")
        audio_buffer = io.BytesIO() # 오디오 데이터를 메모리에 저장할 버퍼

        # OpenAI TTS API 호출 (스트리밍)
        with CLIENT.audio.speech.with_streaming_response.create(
            model="tts-1", # 사용하는 모델 확인
            voice="nova",
            input=text_to_speak,
            response_format="mp3" # 오디오 포맷 지정
        ) as response:
            # 스트리밍된 데이터를 메모리 버퍼에 씁니다.
            for chunk in response.iter_bytes(chunk_size=4096):
                audio_buffer.write(chunk)

        audio_buffer.seek(0) # 버퍼 포인터를 처음으로 이동
        audio_bytes = audio_buffer.getvalue() # 버퍼의 전체 바이트 데이터 가져오기
        print(f"[TTS API] 오디오 생성 완료 (크기: {len(audio_bytes)} bytes)")
        return audio_bytes

    except Exception as e:
        print(f"TTS API 생성 오류: {e}", file=sys.stderr)
        # 오류를 다시 발생시켜 API 엔드포인트에서 처리하도록 함
        raise RuntimeError(f"TTS 오디오 생성 실패: {e}") from e