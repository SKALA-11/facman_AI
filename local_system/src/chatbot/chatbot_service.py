import openai
import os
import json
from ..core.config import OPENAI_API_KEY, VECTOR_DB
from pathlib import Path
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain.schema.output_parser import StrOutputParser
from langchain_core.messages import HumanMessage
from .prompts import get_solve_event_prompt, get_report_prompt

class ChatBot:
    def __init__(self):
        openai.api_key = OPENAI_API_KEY
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.2, max_tokens=2048)
        self.solve_event_db = self.load_vector_store(VECTOR_DB)

    def load_vector_store(self, dir):
        return Chroma(persist_directory=dir, embedding_function=OpenAIEmbeddings())

    def solve_event(self, event, image, event_explain):
        try:
            print("\u2705 solve_event 호출됨")
            print("event:", event)
            print("image 길이:", len(image) if image else "없음")
            print("event_explain:", event_explain)

            event_summary = f"[{event.type}] {event.time}: {event.value}"

            # Vector DB 검색
            rag = ""
            docs = self.solve_event_db.max_marginal_relevance_search(event_summary, k=5)
            if docs:
                rag += "\n".join([doc.page_content for doc in docs])

            # JSON 참고자료 기반 RAG 보강
            try:
                base_path = Path(__file__).resolve().parent
                data_path = base_path.parent.parent / 'public' / 'src' / 'assets' / 'filtered_data.json'
                print("\ud83d\udcc4 json 경로:", data_path)
                
                if not os.path.exists(data_path):
                    raise FileNotFoundError("filtered_data.json 경로에 파일 없음")

                # 인코딩 오류 방지를 위해 latin-1 사용
                with open(data_path, "r", encoding="latin-1") as f:
                    data = json.load(f)

                content = data["documents"][0]["text"]
                user_words = event_explain.split()
                sentences = content.split(". ")
                matched = [s for s in sentences if any(word in s for word in user_words)]
                if matched:
                    rag += "\n" + "\n".join([f"- {s.strip()}" for s in matched[:5]])
            except Exception as json_err:
                print("⚠️ JSON 분석 중 오류:", json_err)

            # 이미지 처리 완전히 분리
            if image and len(image) > 0:
                print("✅ 이미지 있는 경우 처리")
                # 직접 메시지 구성
                messages = [
                    {"role": "user", "content": [
                        {"type": "text", "text": f"다음 이벤트에 대해 분석해주세요:\n{event_explain}\n\n참고자료: {rag}"},
                        {"type": "image_url", "image_url": {"url": image}}
                    ]}
                ]
                
                # OpenAI API 직접 호출
                try:
                    response = openai.chat.completions.create(
                        model="gpt-4o",
                        messages=messages,
                        temperature=0.2,
                        max_tokens=2048
                    )
                    answer = response.choices[0].message.content
                except Exception as img_err:
                    print(f"⚠️ 이미지 처리 API 오류: {img_err}")
                    # 이미지 오류 시 텍스트만 처리
                    text_only_prompt = f"다음 이벤트에 대해 분석해주세요:\n{event_explain}\n\n참고자료: {rag}"
                    text_messages = [{"role": "user", "content": text_only_prompt}]
                    response = openai.chat.completions.create(
                        model="gpt-4o",
                        messages=text_messages,
                        temperature=0.2,
                        max_tokens=2048
                    )
                    answer = response.choices[0].message.content
            else:
                print("✅ 이미지 없이 텍스트만 처리")
                # 텍스트만 처리
                text_only_prompt = f"다음 이벤트에 대해 분석해주세요:\n{event_explain}\n\n참고자료: {rag}"
                text_messages = [{"role": "user", "content": text_only_prompt}]
                response = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=text_messages,
                    temperature=0.2,
                    max_tokens=2048
                )
                answer = response.choices[0].message.content

            print("🧠 GPT 응답:", answer)
            return answer

        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"[ERROR] solve_event 내부 오류: {str(e)}"

    def make_report_content(self, event, image, event_explain, answer):
        try:
            event_summary = f"[{event.type}] {event.time}: {event.value}"
            rag = ""
            docs = self.solve_event_db.max_marginal_relevance_search(event_summary, k=5)
            if docs:
                rag += "\n".join([doc.page_content for doc in docs])

            prompt = get_report_prompt(image, event_explain, rag, answer)
            chain = prompt | self.llm | StrOutputParser()

            report = chain.invoke({
                "image": image,
                "explain": event_explain,
                "rag": rag,
                "answer": answer
            })
            return report

        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"[ERROR] make_report_content 오류: {str(e)}"


# ✅ 외부에서 import 가능하도록 인스턴스화
chatbot = ChatBot()
