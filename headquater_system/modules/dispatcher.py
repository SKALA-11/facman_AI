import logging
from typing import Dict, Any
from modules.user import users_lock, users

def dispatch_transcription(speaker_info, text):
    """
    스피커의 전사 결과를 받아서, 스피커를 제외한 모든 사용자에게 전달합니다.
    각 사용자에게 (text, source_lang, speaker_name) 등의 정보를 담은 튜플을 보냅니다.
    """
    with users_lock:
        for user in users.values():
            # 스피커 본인은 화면에 표시하지 않을 수 있음.
            if user.connection_id == speaker_info["connection_id"]:
                continue
            # 각 사용자에게 스피커의 발화 텍스트와 원본 언어 정보를 보냅니다.
            message = {
                "speaker": speaker_info["name"],
                "text": text,
                "source_lang": speaker_info["language"]
            }
            user.sentence_queue.put(message)
