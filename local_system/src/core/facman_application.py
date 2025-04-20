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
