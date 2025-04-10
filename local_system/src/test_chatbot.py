import base64
from chatbot.chatbot import ChatBot

def load_image_as_base64(path="problem.png"):
    with open(path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def test_solve_event():
    gpt = ChatBot()

    event = type("Event", (object,), {
        "type": "전력 과부하",
        "time": "2024-04-10 14:22",
        "value": "서버실 장비 일부 꺼짐"
    })()

    image_base64 = load_image_as_base64("problem.png")
    event_explain = "서버실 내 과도한 전력 사용으로 인해 일부 장비가 꺼진 상황입니다."

    result = gpt.solve_event(event, image_base64, event_explain)
    print("\n📌 solve_event 결과:\n")
    print(result)

def test_make_report_content():
    gpt = ChatBot()

    event = type("Event", (object,), {
        "type": "전력 과부하",
        "time": "2024-04-10 14:22",
        "value": "서버실 장비 일부 꺼짐"
    })()

    image_base64 = load_image_as_base64("problem.png")
    event_explain = "서버실 내 과도한 전력 사용으로 인해 일부 장비가 꺼진 상황입니다."
    answer = "전력 분석과 회로 부하 분산 조치가 필요합니다."

    report = gpt.make_report_content(event, image_base64, event_explain, answer)
    print("\n📝 make_report_content 결과:\n")
    print(report)

if __name__ == "__main__":
    test_solve_event()
    test_make_report_content()
