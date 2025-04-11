import time
import random
import requests
import json
import os

url = "http://127.0.0.1:8001"

base_dir = os.path.dirname(os.path.abspath(__file__))
filtered_data_path = os.path.join(base_dir, "filtered_data.json")

with open(filtered_data_path, "r", encoding="utf-8") as f:
    filtered = json.load(f)

data = [
    {"type": item["file_name"], "value": item["text"]}
    for item in filtered
]


def send_event(type, value):
    try:
        endpoint = f"{url}/create_event"
        params = {"type": type, "value": value}
        response = requests.post(endpoint, params=params)

        if response.status_code == 200:
            print(f"Event created successfully: {response.json()}")
            return True
        else:
            print(f"Failed to create event: {response.status_code}")
            return False
    except Exception as e:
        print(f"Error sending event: {e}")
        return False


def main():
    while True:
        random_value = random.random()
        if random_value < 0.1:
            random_data = data[random.randrange(0, len(data))]
            print(f"Sending event: {random_data['type']}")
            send_event(random_data["type"], random_data["value"])

        time.sleep(1)


if __name__ == "__main__":
    main()
