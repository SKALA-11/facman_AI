# modules/user.py

import threading
import time

# 사용자 정보를 담는 클래스 정의
class User:
    def __init__(self, name: str, connection_id: str, source_lang: str = "ko", target_lang: str = "en"):
        self.name = name
        self.connection_id = connection_id
        self.source_lang = source_lang  # 사용자가 말하는 언어
        self.target_lang = target_lang  # 번역할 대상 언어
        self.last_update = time.time()  # 마지막 업데이트 시간 등 추가 정보 기록 가능

    def update(self, name: str = None, source_lang: str = None, target_lang: str = None):
        if name:
            self.name = name
        if source_lang:
            self.source_lang = source_lang
        if target_lang:
            self.target_lang = target_lang
        self.last_update = time.time()

# 전역 사용자 저장소 (동시 접근을 위해 lock 사용)
users_lock = threading.Lock()
# connection_id를 key로 사용하면 빠르게 조회할 수 있습니다.
users = {}

def get_or_create_user(name: str, connection_id: str, default_source: str = "ko", default_target: str = "en") -> User:
    with users_lock:
        if connection_id in users:
            user = users[connection_id]
            # 필요에 따라 이름이나 언어 정보를 업데이트 할 수 있음
            user.update(name=name)
            return user
        else:
            user = User(name, connection_id, default_source, default_target)
            users[connection_id] = user
            print(f"[DEBUG] 새로운 사용자가 추가되었습니다: {user.name} ({user.connection_id})")
            return user

def get_user_by_connection(connection_id: str) -> User:
    with users_lock:
        return users.get(connection_id)
