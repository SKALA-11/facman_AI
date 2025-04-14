import openai
from ..core.config import OPENAI_API_KEY, VECTOR_DB
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain_openai import ChatOpenAI
from langchain.schema.output_parser import StrOutputParser
from .prompts import get_solve_event_prompt, get_report_prompt


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

        prompt = get_solve_event_prompt(image, event_explain, rag)

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

        prompt = get_report_prompt(image, event_explain, rag, answer)

        chain = prompt | self.llm | StrOutputParser()

        answer = chain.invoke(
            {"image": image, "explain": event_explain, "rag": rag, "answer": answer}
        )

        return answer


chatbot = ChatBot()
