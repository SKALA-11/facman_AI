# modules/final_message.py

from dataclasses import dataclass, field
import time, uuid

@dataclass
class FinalMessage:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    stt: str = ""              # 전사 결과 텍스트
    translation: str = ""      # 번역 결과 텍스트
    translation_tts: str = ""  # 번역 TTS 음성 (예: Base64 인코딩 문자열 또는 파일 경로)