# modules/user.py

import threading
import time
import queue

# 사용자 정보를 담는 클래스 정의
class User:
    def __init__(self, name: str, source_lang: str = "ko", target_lang: str = "en", session_id: str = None):
        self.name = name
        self.source_lang = source_lang  # 사용자가 말하는 언어
        self.target_lang = target_lang  # 번역할 대상 언어
        self.last_update = time.time()  # 마지막 업데이트 시간 등 추가 정보 기록 가능
        self.session_id = session_id    # 세션 ID 추가
        
        self.detected_language = source_lang  # 개별 감지 언어
        self.processing_started = False  # 처리 스레드 실행 여부

        # 사용자 전용 큐들
        self.audio_queue = queue.Queue()
        self.sentence_queue = queue.Queue()
        self.transcription_queue = queue.Queue()
        self.translation_queue = queue.Queue()
        self.translated_queue = queue.Queue()
        
        self.final_results_queue = queue.Queue()

        self.websocket = None

    def update(self, name: str = None, source_lang: str = None, target_lang: str = None, websocket=None, session_id: str = None):
        if name:
            self.name = name
        if source_lang:
            self.source_lang = source_lang
        if target_lang:
            self.target_lang = target_lang
        if session_id:
            self.session_id = session_id
        # 새 WebSocket 객체가 제공되면 업데이트
        if websocket is not None:
            self.websocket = websocket
        self.last_update = time.time()

# 전역 사용자 저장소 (동시 접근을 위해 lock 사용)
users_lock = threading.Lock()
# connection_id를 key로 사용하면 빠르게 조회할 수 있습니다.
users = {}

def get_or_create_user(name: str, default_source: str = "ko", default_target: str = "en", websocket=None, session_id: str = None) -> User:
    with users_lock:
        if name in users:
            user = users[name]
            # 사용자 정보 업데이트 (WebSocket도 함께 업데이트)
            user.update(name=name, source_lang=default_source, target_lang=default_target, websocket=websocket, session_id=session_id)
            return user
        else:
            user = User(name, default_source, default_target, session_id)
            user.websocket = websocket
            users[name] = user
            print(f"[DEBUG] 새로운 사용자가 추가되었습니다: {user.name}, 세션 ID: {session_id}")
            return user

def get_user_by_connection(connection_id: str) -> User:
    with users_lock:
        return users.get(connection_id)