# test_chatbot.py
from chatbot.chatbot import ChatBot


# 테스트용 이벤트 객체 정의
class DummyEvent:
    def __init__(self, type, time, value):
        self.type = type
        self.time = time
        self.value = value

# 더미 이벤트 생성
event = DummyEvent(
    type="전기",
    time="2024-04-10 09:00",
    value="서버실 전력 과부하"
)

# 더미 이미지 (base64 없이 테스트)
image_base64 = ""

# 문제 설명 텍스트
event_explain = "서버실에서 전력 과부하로 인해 일부 장비가 꺼졌습니다. 원인을 분석하고 해결 방안을 제시해주세요."

# 챗봇 호출
gpt = ChatBot()
response = gpt.solve_event(event, image_base64, event_explain)

# 결과 출력
print("\n💬 GPT 응답 결과:")
print(response)
