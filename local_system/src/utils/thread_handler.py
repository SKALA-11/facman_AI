import threading
from abc import ABC, abstractmethod


class ThreadHandler(ABC):

    def __init__(self):
        self.thread = None
        self.running = False

    @abstractmethod
    def run(self):
        pass

    def start(self):
        if self.thread is None or not self.thread.is_alive():
            self.running = True
            self.thread = threading.Thread(target=self._run_wrapper, daemon=True)
            self.thread.start()

    def _run_wrapper(self):
        try:
            self.run()
        except Exception as e:
            print(f"Error in thread: {e}")
        finally:
            self.running = False

    def stop(self):
        if self.thread and self.thread.is_alive():
            self.running = False
            self.thread.join(timeout=1)
