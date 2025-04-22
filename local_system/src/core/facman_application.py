#======================================================================================#
# [ 파일 개요 ]
# FastAPI 애플리케이션을 캡슐화하는 FacmanApplication 클래스를 정의합니다.
# 클래스는 FastAPI 인스턴스 생성, Uvicorn ASGI 서버를 사용하여 애플리케이션을 시작합니다.

# [ 주요 로직 흐름 ]
# 1. 라이브러리 임포트 (uvicorn, FastAPI).
# 2. FacmanApplication 클래스 정의:
#    a. __init__(self, host, port):
#       - FastAPI() 인스턴스를 생성하여 self.app에 저장.
#       - 호스트(host)와 포트(port) 번호를 인스턴스 변수에 저장 (기본값 제공).
#       - 라우트 설정을 위한 내부 메서드 _setup_routes() 호출.
#    b. start(self):
#       - uvicorn.run() 함수를 호출하여 self.app (FastAPI 인스턴스)을 저장된 호스트와 포트로 실행시킵니다.
# 3. 외부에서 FacmanApplication 인스턴스를 생성하고 start() 메서드를 호출하여 웹 서버를 구동할 수 있습니다.
#======================================================================================#



import uvicorn
from fastapi import FastAPI

class FacmanApplication:
    def __init__(self, host="0.0.0.0", port=8001):
        self.app = FastAPI()
        self.host = host
        self.port = port

        self._setup_routes()

    def start(self):
        uvicorn.run(app=self.app, host=self.host, port=self.port)
