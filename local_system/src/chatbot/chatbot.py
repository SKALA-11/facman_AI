import openai
import base64
from core.config import OPENAI_API_KEY, VECTOR_DB
from langchain.prompts import ChatPromptTemplate
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain_openai import ChatOpenAI
from langchain.schema.output_parser import StrOutputParser


class ChatBot:

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(ChatBot, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        openai.api_key = OPENAI_API_KEY

        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.2, max_tokens=2048)
        self.solve_event_db = self.load_vector_store(VECTOR_DB)

    def load_vector_store(self, dir):
        return Chroma(persist_directory=dir, embedding_function=OpenAIEmbeddings())

    def solve_event(self, event, image, event_explain):

        event = f"[{event.type}] {event.time}: {event.value}"

        rag = ""
        docs = self.solve_event_db.search(event, search_type="mmr", k=5)
        if docs:
            rag += "\n".join([doc.page_content for doc in docs])

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "당신은 전문가입니다. 참고자료, 이미지, 설명를 참고하여 분석하여 주세요.",
                ),
                (
                    "user",
                    [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image}"},
                        },
                        {
                            "type": "text",
                            "text": f"참고자료, 이미지, 설명을 바탕으로 해결법을 도출하여 주세요. 설명: {event_explain}, \n 참고자료: {rag}",
                        },
                    ],
                ),
            ]
        )

        chain = prompt | self.llm | StrOutputParser()

        answer = chain.invoke({"image": image, "explain": event_explain, "rag": rag})
        print(answer)
        return answer

    def make_report_content(self, event, image, event_explain, answer):

        event = f"[{event.type}] {event.time}: {event.value}"

        rag = ""
        docs = self.solve_event_db.search(event, search_type="mmr", k=5)
        if docs:
            rag += "\n".join([doc.page_content for doc in docs])

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "참고자료, 이미지, 설명, 응답으로 report에 사용할 내용물을 작성하여 주세요.",
                ),
                (
                    "user",
                    [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image}"},
                        },
                        {
                            "type": "text",
                            "text": f"이미지와 설명을 바탕으로 보고서를 만들어 주세요. 설명: {event_explain}, 참고자료 {rag}, 응답 {answer}",
                        },
                    ],
                ),
            ]
        )

        chain = prompt | self.llm | StrOutputParser()

        answer = chain.invoke(
            {"image": image, "explain": event_explain, "rag": rag, "answer": answer}
        )

        return answer


chatbot = ChatBot()
