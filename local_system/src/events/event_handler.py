from utils import ThreadHandler


class EventHandler(ThreadHandler):
    def __init__(self, event, event_generator):
        super().__init__()
        self.event = event
        self.event_generator = event_generator

    def run(self):
        self.event_generator.start()

        try:
            while self.running:
                if self.event.check():
                    self.event_generator.stop()
                    """
                    TODO: add event transmission
                    """
                    self.event.over()
                    self.event_generator.start()
        except KeyboardInterrupt:
            self.event_generator.stop()
