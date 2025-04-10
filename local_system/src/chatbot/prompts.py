from langchain.prompts import ChatPromptTemplate

def get_solve_event_prompt(image: str, event_explain: str, rag: str) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", 
         "당신은 산업 현장의 문제를 해결하는 전문가입니다. 설명과 참고자료를 바탕으로 해결방안을 작성해 주세요."),
        ("user", f"설명: {event_explain}\n참고자료: {rag}")
    ])


def get_report_prompt(image: str, event_explain: str, rag: str, answer: str) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", 
         "당신은 산업 안전 분석 보고서를 작성하는 전문가입니다. "
         "아래의 문제 설명, 과거 사례 요약, 분석 결과를 바탕으로 보고서를 정리해 주세요."),
        ("user", [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image}"}
            },
            {
                "type": "text",
                "text": (
                    f"[문제 설명]: {event_explain}\n"
                    f"[과거 사례 요약]: {rag}\n"
                    f"[GPT 분석 응답]: {answer}\n\n"
                    f"다음 형식을 참고하여 보고서를 구성해 주세요:\n\n"
                    f"1. 사건 개요\n"
                    f"2. 원인 분석\n"
                    f"3. 해결 방안 제시\n"
                    f"4. 참고 사례 요약\n"
                    f"5. 향후 예방을 위한 제언"
                )
            }
        ])
    ])
