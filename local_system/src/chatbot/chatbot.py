import logging
from typing import List, TYPE_CHECKING

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

from ..core.config import VECTOR_DB
from .prompts import get_solve_event_prompt, get_report_prompt

if TYPE_CHECKING:
    from ..db.models import EventModel

# 로거 설정
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class ChatBot:
    """
    AI 챗봇 로직을 처리하는 클래스.
    이벤트 해결 방안 생성 및 보고서 내용 생성을 담당합니다.
    싱글톤 패턴을 사용하여 인스턴스를 관리합니다.
    """
    _instance = None

    def __new__(cls):
        # 싱글톤 패턴 구현
        if cls._instance is None:
            logger.info("Creating new ChatBot instance")
            cls._instance = super(ChatBot, cls).__new__(cls)
            # 초기화는 __new__에서 한 번만 수행
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """
        ChatBot 인스턴스를 초기화합니다.
        LLM, Vector Store 등을 로드합니다.
        싱글톤 패턴에 의해 실제 초기화는 첫 인스턴스 생성 시 한 번만 실행됩니다.
        """
        if self._initialized:
            return
        logger.info("Initializing ChatBot components...")

        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.2, max_tokens=2048)
        # Vector Store 로드
        self.vector_store = self._load_vector_store(VECTOR_DB)
        if self.vector_store:
             logger.info(f"Vector store loaded successfully from {VECTOR_DB}")
        else:
             logger.error(f"Failed to load vector store from {VECTOR_DB}")

        self._initialized = True

    def _load_vector_store(self, persist_directory: str) -> Chroma | None:
        """
        지정된 디렉토리에서 Chroma Vector Store를 로드합니다.
        Args:
            persist_directory: Vector Store가 저장된 디렉토리 경로.
        Returns:
            Chroma 인스턴스 또는 로드 실패 시 None.
        """
        try:
            embedding_function = OpenAIEmbeddings()
            db = Chroma(persist_directory=persist_directory, embedding_function=embedding_function)
            return db
        except Exception as e:
            logger.exception(f"Error loading vector store from {persist_directory}: {e}")
            return None

    def _perform_rag_search(self, query: str, k: int = 5) -> str:
        """
        주어진 쿼리로 Vector Store에서 관련 문서를 검색하고 RAG 컨텍스트 문자열을 생성합니다.
        Args:
            query: 검색할 쿼리 문자열.
            k: 검색할 문서의 수.
        Returns:
            검색된 문서 내용을 결합한 RAG 컨텍스트 문자열. 없으면 빈 문자열.
        """
        rag_context = ""
        if not self.vector_store:
            logger.warning("Vector store not available for RAG search.")
            return rag_context

        try:
            # MMR(Maximal Marginal Relevance) 검색 수행
            docs: List[Document] = self.vector_store.search(query, search_type="mmr", k=k)
            if docs:
                # 검색된 문서들의 page_content를 결합
                rag_context = "\n".join([doc.page_content for doc in docs])
                logger.info(f"RAG search completed for query '{query[:50]}...'. Found {len(docs)} documents.")
            else:
                logger.info(f"No relevant documents found for query '{query[:50]}...'.")
        except Exception as e:
            logger.exception(f"Error during RAG search for query '{query[:50]}...': {e}")

        return rag_context

    def solve_event(self, event: 'EventModel', image_base64: str, event_explain: str) -> str:
        """
        주어진 이벤트 정보와 이미지를 바탕으로 AI 분석 및 해결 방안을 생성합니다.
        Args:
            event: 이벤트 정보 (EventModel 객체).
            image_base64: Base64로 인코딩된 이미지 문자열.
            event_explain: 사용자가 입력한 이벤트 설명.
        Returns:
            AI가 생성한 분석 및 해결 방안 텍스트.
        """
        # RAG 검색을 위한 쿼리 생성
        query = f"[{event.type}] {event.time}: {event.value}"
        rag_context = self._perform_rag_search(query)

        prompt = get_solve_event_prompt(image_base64, event_explain, rag_context)

        # Langchain 체인 구성 및 실행
        chain = prompt | self.llm | StrOutputParser()

        try:
            answer = chain.invoke({
                "image": image_base64,
                "event_explain": event_explain,
                "rag": rag_context
            })
            logger.info(f"Successfully generated solution for event ID: {event.id}")
            return answer
        except Exception as e:
            logger.exception(f"Error invoking LLM chain for solving event ID {event.id}: {e}")
            return "AI 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."

    def make_report_content(self, event: 'EventModel', image_base64: str, event_explain: str, previous_answer: str) -> str:
        """
        이벤트 정보, 이미지, 설명, 이전 AI 분석 결과를 바탕으로 보고서 내용을 생성합니다.

        Args:
            event: 이벤트 정보 (EventModel 객체).
            image_base64: Base64로 인코딩된 이미지 문자열.
            event_explain: 사용자가 입력한 이벤트 설명.
            previous_answer: solve_event 메서드에서 생성된 AI 분석 결과.

        Returns:
            AI가 생성한 보고서 내용 텍스트.
        """
        logger.info(f"Generating report content for event ID: {event.id}")

        query = f"[{event.type}] {event.time}: {event.value}"
        rag_context = self._perform_rag_search(query)

        prompt = get_report_prompt(image_base64, event_explain, rag_context, previous_answer)

        chain = prompt | self.llm | StrOutputParser()

        try:
            report_content = chain.invoke({
                "image": image_base64,
                "explain": event_explain,
                "rag": rag_context,
                "answer": previous_answer
            })
            logger.info(f"Successfully generated report content for event ID: {event.id}")
            return report_content
        except Exception as e:
            logger.exception(f"Error invoking LLM chain for generating report for event ID {event.id}: {e}")
            return "보고서 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
