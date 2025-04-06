import uvicorn
from fastapi import FastAPI
from api import router
from events import Event, EventGenerator, EventHandler


class FacmanApplication:
    def __init__(self, host="127.0.0.1", port=8001):
        self.app = FastAPI()
        self.host = host
        self.port = port

        self.event = Event()
        self.event_generator = EventGenerator(self.event)
        self.event_handler = EventHandler(self.event, self.event_generator)

        self._setup_routes()

    def _setup_routes(self):
        self.app.include_router(router)

    def start(self):
        self.event_handler.start()
        uvicorn.run(app=self.app, host=self.host, port=self.port, reload=False)
