import time
import random
import requests
import json

url = "http://127.0.0.1:8001"

# filtered_data.json에서 데이터 불러오기
with open("../vector_db/filtered_data.json", "r", encoding="utf-8") as f:
    filtered = json.load(f)

# file_name과 text를 이용해 type/value로 구성
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
            print(f"Sending event: {random_data['type']}")
            send_event(random_data["type"], random_data["value"])

        time.sleep(1)


if __name__ == "__main__":
    main()
