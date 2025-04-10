import time
import random
import requests

url = "http://127.0.0.1:8001"

data = [
    {"type": "type1", "value": "value1"},
    {"type": "type2", "value": "value2"},
    {"type": "type3", "value": "value3"},
    {"type": "type4", "value": "value4"},
    {"type": "type5", "value": "value5"},
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
            print(f"Failed to create event: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"Error sending event: {e}")
        return False


def main():
    while True:
        random_value = random.random()
        if random_value < 0.1:
            random_data = data[random.randrange(0, len(data))]
            print(random_data)
            send_event(random_data["type"], random_data["value"])

        time.sleep(1)


if __name__ == "__main__":
    main()
