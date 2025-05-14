#-------------------------------------------------------------------------------------#
# [ 파일 개요 ]
# Langchain과 모델을 사용하여 AI 챗봇 로직을 처리하는 ChatBot 클래스를 정의합니다.
# (LLM은 OpenAI, Embedding은 HuggingFace 모델 사용)
# ChatBot 클래스는 싱글톤 패턴으로 구현되어 애플리케이션 내에서 단일 인스턴스로 관리됩니다.
# 주요 기능은 RAG를 활용하여 이벤트 해결 방안 제안(solve_event) 및 보고서 내용 생성(make_report_content)을 합니다.

# [ 주요 로직 흐름 ]
# 1. 초기화 (싱글톤):
#    - ChatBot 클래스의 첫 인스턴스 생성 시(__new__, __init__):
#      - 로깅 기본 설정 적용.
#      - OpenAI LLM (gpt-4o) 초기화.
#      - HuggingFace 임베딩 모델 로드 및 Chroma 벡터 저장소 로드 시도 (_load_vector_store).
#      - 벡터 저장소 로드 성공/실패 로깅.
#      - 초기화 완료 상태 저장.
#    - 이후 인스턴스 요청 시 기존 인스턴스 반환.
# 2. 벡터 저장소 로드 (_load_vector_store):
#    - 지정된 경로에서 HuggingFace 임베딩을 사용하여 Chroma 벡터 DB 로드.
#    - 성공 시 Chroma 객체 반환, 실패 시 로깅 후 None 반환.
# 3. RAG 검색 (_perform_rag_search):
#    - (기존과 동일)
# 4. 이벤트 해결 방안 생성 (solve_event):
#    - (기존과 동일)
# 5. 보고서 내용 생성 (make_report_content):
#    - (기존과 동일)
#-------------------------------------------------------------------------------------#

import logging
from typing import List, TYPE_CHECKING

from langchain_openai import ChatOpenAI # LLM은 OpenAI 모델 그대로 사용
from langchain_huggingface import HuggingFaceEmbeddings # 새 방식
from langchain_chroma import Chroma # 새 방식
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document # langchain.schema 대신 langchain_core.documents 사용 권장

from ..core.config import VECTOR_DB
from .prompts import get_solve_event_prompt, get_report_prompt

if TYPE_CHECKING:
    from ..db.models import EventModel

# 로거 설정
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO) # 애플리케이션 최상단에서 한 번만 설정하는 것을 권장 (예: main.py)

class ChatBot:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            logger.info("Creating new ChatBot instance")
            cls._instance = super(ChatBot, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        logger.info("Initializing ChatBot components...")

        # LLM은 그대로 gpt-4o 사용
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.2, max_tokens=2048)
        
        # Vector Store 로드 (HuggingFaceEmbeddings 사용하도록 수정)
        self.embedding_model_name = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"
        self.vector_store = self._load_vector_store(VECTOR_DB, self.embedding_model_name)
        
        if self.vector_store:
             logger.info(f"Vector store loaded successfully from {VECTOR_DB} using {self.embedding_model_name}")
        else:
             logger.error(f"Failed to load vector store from {VECTOR_DB}. RAG search will not be available.")

        self._initialized = True

    def _load_vector_store(self, persist_directory: str, model_name: str) -> Chroma | None:
        """
        지정된 디렉토리에서 Chroma Vector Store를 로드합니다. (HuggingFaceEmbeddings 사용)
        Args:
            persist_directory: Vector Store가 저장된 디렉토리 경로.
            model_name: 사용할 HuggingFace 모델 이름.
        Returns:
            Chroma 인스턴스 또는 로드 실패 시 None.
        """
        try:
            logger.info(f"Loading HuggingFace embeddings model: {model_name}")
            # HuggingFaceEmbeddings 초기화
            embedding_function = HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs={'device': 'cpu'}, # CPU 사용 명시, GPU 사용 시 'cuda'
                encode_kwargs={'normalize_embeddings': True} # 임베딩 정규화
            )
            logger.info(f"HuggingFace embeddings model '{model_name}' loaded successfully.")
            
            logger.info(f"Attempting to load Chroma DB from: {persist_directory}")
            db = Chroma(
                persist_directory=persist_directory, 
                embedding_function=embedding_function
            )
            logger.info(f"Chroma DB loaded successfully from {persist_directory}.")
            return db
        except Exception as e:
            # persist_directory가 존재하지 않거나, 내부 파일 손상, 권한 문제 등 다양한 원인 가능
            logger.exception(f"Error loading vector store from {persist_directory} with model {model_name}: {e}")
            logger.error(f"Ensure the directory '{persist_directory}' exists and contains valid ChromaDB files for the specified embedding model.")
            logger.error("If this is the first run or after changing the embedding model, you might need to (re)build the vector DB using 'factory_problem_data_collection.py'.")
            return None

    def _perform_rag_search(self, query: str, k: int = 5) -> str:
        rag_context = ""
        if not self.vector_store:
            logger.warning("Vector store not available for RAG search. Returning empty context.")
            return rag_context

        try:
            logger.info(f"Performing RAG search for query (first 50 chars): '{query[:50]}...' with k={k}")
            # MMR(Maximal Marginal Relevance) 검색 수행
            # Chroma 클래스의 search 메서드가 아니라 retriever의 get_relevant_documents를 사용하는 것이 일반적
            # 또는 유사도 검색인 similarity_search 사용
            # docs: List[Document] = self.vector_store.search(query, search_type="mmr", k=k) # search 메서드는 Chroma의 기본 메서드가 아닐 수 있음
            
            # Langchain Chroma 객체의 표준 검색 메서드 사용
            docs: List[Document] = self.vector_store.similarity_search(query, k=k)
            # 또는 MMR 검색을 사용하고 싶다면 retriever를 생성해야 함:
            # retriever = self.vector_store.as_retriever(search_type="mmr", search_kwargs={"k": k})
            # docs = retriever.get_relevant_documents(query)

            if docs:
                rag_context = "\n\n---\n\n".join([f"참고문서 출처: {doc.metadata.get('file_name', 'N/A')}\n{doc.page_content}" for doc in docs])
                logger.info(f"RAG search completed. Found {len(docs)} documents.")
            else:
                logger.info(f"No relevant documents found for query '{query[:50]}...'.")
        except Exception as e:
            logger.exception(f"Error during RAG search for query '{query[:50]}...': {e}")

        return rag_context

    def solve_event(self, event: 'EventModel', image_base64: str, event_explain: str) -> str:
        query = f"[{event.type}] {event.time}: {event.value}"
        rag_context = self._perform_rag_search(query)

        prompt = get_solve_event_prompt(image_base64, event_explain, rag_context)
        chain = prompt | self.llm | StrOutputParser()

        try:
            answer = chain.invoke({
                # "image": image_base64, # 프롬프트에 이미지가 직접 사용되지 않음 (get_solve_event_prompt 내부에서 처리)
                # "event_explain": event_explain,
                # "rag": rag_context
                # invoke 시에는 프롬프트 템플릿에서 사용된 변수명이 아닌, 실제 값을 직접 전달
                # 하지만 현재 get_solve_event_prompt는 이미 값들을 포함하여 ChatPromptTemplate 객체를 반환하므로
                # 추가적인 변수 전달 없이 invoke({}) 또는 invoke(None)으로 호출 가능
                # 만약 프롬프트 템플릿에 input_variables가 정의되어 있다면 해당 변수를 채워줘야 함
                # 현재 get_solve_event_prompt는 image, event_explain, rag를 내부적으로 사용하므로
                # invoke({})로 호출하거나, 해당 키로 값을 전달해도 Langchain이 처리함.
                # 명확성을 위해 키-값 쌍으로 전달하는 것이 좋음 (프롬프트 함수 내부 변수명과 일치하지 않아도 됨, 위치 기반으로 들어감)
            }) # ChatPromptTemplate.from_messages로 생성된 경우, invoke의 입력은 보통 dict이며, 마지막 user 메시지에 사용될 변수를 전달
            logger.info(f"Successfully generated solution for event ID: {event.id}")
            return answer
        except Exception as e:
            logger.exception(f"Error invoking LLM chain for solving event ID {event.id}: {e}")
            return "AI 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."

    def make_report_content(self, event: 'EventModel', image_base64: str, event_explain: str, previous_answer: str) -> str:
        logger.info(f"Generating report content for event ID: {event.id}")

        query = f"[{event.type}] {event.time}: {event.value}"
        rag_context = self._perform_rag_search(query)

        prompt = get_report_prompt(image_base64, event_explain, rag_context, previous_answer)
        chain = prompt | self.llm | StrOutputParser()

        try:
            report_content = chain.invoke({}) # 위와 동일한 이유로 {} 또는 None 전달 가능
            logger.info(f"Successfully generated report content for event ID: {event.id}")
            return report_content
        except Exception as e:
            logger.exception(f"Error invoking LLM chain for generating report for event ID {event.id}: {e}")
            return "보고서 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."