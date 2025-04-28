#-------------------------------------------------------------------------------------------------#
# [ 스크립트 개요 ]
# 이 스크립트는 'filtered_data.json' 파일에서 데이터를 읽어와,
# 주기적으로 10%의 확률로 해당 데이터 중 하나를 선택하여 지정된 로컬 API 엔드포인트(http://127.0.0.1:8001/create_event)로 POST 요청을 보내는 역할을 합니다.

# [ 주요 로직 흐름 ]
# 1. 데이터 로딩: 'filtered_data.json' 파일을 열어 JSON 데이터를 읽고 파싱합니다.
#    - 파일이 없거나 JSON 형식이 잘못된 경우 오류를 처리하고 종료합니다.
#    - 읽어온 데이터를 API 요청에 적합한 {'type': ..., 'value': ...} 형태의 딕셔너리 리스트로 변환합니다 ('data' 변수).
# 2. 이벤트 전송 함수 (send_event):
#    - 이벤트 타입과 값을 받아 API로 POST 요청을 보냅니다.
# 3. 메인 실행 함수 (main):
#      a. 0.0 ~ 1.0 사이의 난수를 생성합니다.
#      b. 난수가 0.1 미만일 경우 (10% 확률):
#         - 'data' 리스트에서 무작위로 항목을 하나 선택합니다.
#         - send_event 함수를 호출하여 선택된 데이터를 API로 전송 시도합니다.
#      c. 사용자가 Ctrl+C를 눌러 중단을 요청하면 루프를 종료합니다.
# 4. 스크립트 실행: 스크립트가 직접 실행될 때 (__name__ == "__main__") main 함수를 호출하여 전체 프로세스를 시작합니다.
#-------------------------------------------------------------------------------------------------#


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
