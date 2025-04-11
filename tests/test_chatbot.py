import base64
import os
import sys

# sys.path로 src 경로 등록
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../local_system/src')))

from chatbot.chatbot import ChatBot

def load_image_as_base64(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")

def test_solve_event():
    chatbot = ChatBot()

    event = type("Event", (object,), {
        "type": "전력 과부하",
        "time": "2024-04-10 14:22",
        "value": "서버실 장비 일부 꺼짐"
    })()

    image_base64 = load_image_as_base64("tests/problem.png")
    event_explain = "서버실 내 과도한 전력 사용으로 인해 일부 장비가 꺼진 상황입니다."

    result = chatbot.solve_event(event, image_base64, event_explain)
    print("solve_event 응답:\n")
    print(result)

def test_make_report_content():
    chatbot = ChatBot()

    event = type("Event", (object,), {
        "type": "전력 과부하",
        "time": "2024-04-10 14:22",
        "value": "서버실 장비 일부 꺼짐"
    })()

    image_base64 = load_image_as_base64("tests/problem.png")
    event_explain = "서버실 내 과도한 전력 사용으로 인해 일부 장비가 꺼진 상황입니다."
    dummy_answer = "전력 분석과 회로 부하 분산 조치가 필요합니다."

    report = chatbot.make_report_content(event, image_base64, event_explain, dummy_answer)
    print("\nmake_report_content 응답:\n")
    print(report)

if __name__ == "__main__":
    test_solve_event()
    test_make_report_content()
