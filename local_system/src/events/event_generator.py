import time
import random
from utils import ThreadHandler

"""
TODO
1. Add sample data for random event 
"""


class EventGenerator(ThreadHandler):

    def __init__(self, event):
        super().__init__()
        self.data = [
            {"type": "type1", "value": "value1"},
            {"type": "type2", "value": "value2"},
            {"type": "type3", "value": "value3"},
            {"type": "type4", "value": "value4"},
            {"type": "type5", "value": "value5"},
        ]
        self.event = event

    def run(self):
        while self.running:
            random_value = random.random()
            if random_value < 0.1:
                random_data = self.data[random.randrange(0, len(self.data))]
                self.event.occur(random_data["type"], random_data["value"])

            time.sleep(1)
