from datetime import datetime


class Event:

    def __init__(self):
        self.type = ""
        self.value = ""
        self.time = ""
        self.occurred = False

    def check(self):
        return self.occurred

    def occur(self, type, value):
        self.type = type
        self.value = value
        self.time = datetime.now().isoformat()
        self.occurred = True

    def over(self):
        self.occurred = False

    def __str__(self):
        return f"[{self.type}] {self.time} : {self.value}"
