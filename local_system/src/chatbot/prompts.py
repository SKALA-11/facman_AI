from langchain.prompts import ChatPromptTemplate

def get_solve_event_prompt(image: str, event_explain: str, rag: str) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", 
         "당신은 산업 현장의 사고를 분석하고 해결책을 제시하는 전문가입니다. "
         "아래의 설명과 참고자료를 바탕으로 사고의 원인을 분석하고, "
         "구체적인 해결방안을 제시해 주세요. "
         "해결방안은 실현 가능하고, 단계별로 명확하게 작성해 주세요."),
        ("user", f"문제 설명: {event_explain}\n\n참고자료: {rag}")
    ])


def get_report_prompt(image: str, event_explain: str, rag: str, answer: str) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", 
         "당신은 산업 안전 분석 보고서를 작성하는 전문가입니다. "
         "아래의 문제 설명, 과거 사례 요약, GPT 응답을 바탕으로 보고서를 작성해 주세요. "
         "다음 항목은 반드시 모두 포함되어야 합니다:\n"
         "1. 사건 개요\n"
         "2. 원인 분석\n"
         "3. 해결 방안 제시\n"
         "4. 참고 사례 요약\n"
         "5. 향후 예방을 위한 제언"),
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
                    f"위의 정보를 바탕으로 아래 형식에 따라 보고서를 작성해 주세요.\n\n"
                    f"1. 사건 개요\n"
                    f"2. 원인 분석\n"
                    f"3. 해결 방안 제시\n"
                    f"4. 참고 사례 요약\n"
                    f"5. 향후 예방을 위한 제언"
                )
            }
        ])
    ])
