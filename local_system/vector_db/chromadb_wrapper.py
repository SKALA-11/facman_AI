# ChromaDB Wrapper for Managing Factory Problem Data

import os
import json
# from langchain_community.vectorstores import Chroma # 이전 방식
# from langchain_community.embeddings import HuggingFaceEmbeddings # 이전 방식
from langchain_chroma import Chroma # 새 방식 (langchain-chroma 패키지)
from langchain_huggingface import HuggingFaceEmbeddings # 새 방식 (langchain-huggingface 패키지)
from langchain_core.documents import Document
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)


class ChromaDBWrapper:
    def __init__(self, persist_directory="./chroma_db", model_name="snunlp/KR-SBERT-V40K-klueNLI-augSTS"):
        load_dotenv() # OPENAI_API_KEY는 이제 필요 없지만, 다른 환경변수를 위해 남겨둘 수 있음
        self.persist_directory = persist_directory
        self.model_name = model_name
        
        logger.info(f"ChromaDBWrapper 초기화 시작. 모델: {self.model_name}")

        try:
            # HuggingFaceEmbeddings 초기화
            # GPU 사용 가능 시 device='cuda', 아니면 device='cpu' (기본값)
            # 멀티프로세싱 관련 경고를 피하기 위해 일부 환경 변수 설정 (필요시)
            # os.environ["TOKENIZERS_PARALLELISM"] = "false"
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.model_name,
                model_kwargs={'device': 'cpu'}, # CPU 사용 명시, GPU 사용 시 'cuda'
                encode_kwargs={'normalize_embeddings': True} # 임베딩 정규화 (일반적으로 성능 향상)
            )
            logger.info(f"임베딩 모델 로드 완료: {self.model_name}")
        except Exception as e:
            logger.exception(f"HuggingFace 임베딩 모델 로드 중 오류 발생: {e}")
            self.embeddings = None # 오류 발생 시 None으로 설정
            # 또는 여기서 예외를 다시 발생시켜 프로그램 중단 고려
            raise

        try:
            self.db = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings,
            )
            logger.info(f"✅ 기존 Chroma DB 불러오기 완료 (디렉토리: {self.persist_directory})")
        except Exception as e:
            logger.exception(f"🚫 Chroma DB 초기화 오류: {e}")
            self.db = None
            # 또는 여기서 예외를 다시 발생시켜 프로그램 중단 고려
            raise

    def add_documents(self, documents: list[Document]): # 타입 힌트 명시
        try:
            if not documents:
                logger.warning("⚠️ 추가할 문서가 없습니다.")
                return
            if not self.db:
                logger.error("🚫 Chroma DB가 초기화되지 않아 문서를 추가할 수 없습니다.")
                return

            # 중복 제거 로직은 기존 문서의 내용을 가져와야 하므로, get() 메서드 사용
            # 다만, get() 메서드가 현재 모든 document object를 반환하는지, 아니면 텍스트만 반환하는지 확인 필요
            # 현재 get()은 raw dict를 반환하므로, 여기서 직접 사용하기보다는
            # ChromaDB의 id를 활용한 중복 방지나, 추가 전에 내용을 비교하는 방식이 더 적합할 수 있음
            # 단순화를 위해 여기서는 중복 제거 로직을 임시로 주석 처리하거나,
            # ChromaDB에서 id를 기반으로 한 중복 삽입 방지 기능 활용 (ChromaDB 자체에서 중복 ID 삽입 시 업데이트)
            
            # # 중복 제거를 위해 기존 데이터 확인 (텍스트 기반, 비효율적일 수 있음)
            # existing_docs_texts = set()
            # try:
            #     # get() 메서드가 Document 객체의 리스트를 반환한다고 가정.
            #     # 실제 Chroma.get()은 Document가 아닌 dict의 list를 반환할 수 있음.
            #     # 이 부분은 ChromaDB의 get() 반환값에 따라 수정 필요.
            #     # 여기서는 간단히 모든 문서를 추가하는 것으로 가정.
            #     # existing_data = self.db.get(include=["documents"]) # "documents" 필드 포함
            #     # if existing_data and existing_data.get("documents"):
            #     #     existing_docs_texts = {doc_content for doc_content in existing_data["documents"]}
            #     pass
            # except Exception as e:
            #     logger.warning(f"기존 문서 내용을 가져오는 중 오류: {e}. 중복 검사 없이 진행합니다.")

            # new_documents = [
            #     doc for doc in documents if doc.page_content not in existing_docs_texts
            # ]
            
            # Langchain의 Chroma는 기본적으로 ID가 같으면 업데이트, 다르면 추가.
            # ID를 명시적으로 관리하지 않으면 자동으로 생성하므로 중복될 수 있음.
            # 여기서는 Document에 ID를 부여하지 않고 추가합니다.
            # 필요시, 문서 내용의 해시값을 ID로 사용하는 등의 전략을 고려할 수 있습니다.
            new_documents = documents # 임시로 중복 검사 없이 모든 문서를 대상으로 함

            if new_documents:
                # ids = [f"doc_{i}" for i in range(len(new_documents))] # 간단한 ID 생성 예시
                self.db.add_documents(documents=new_documents) # ids 파라미터는 선택 사항
                logger.info(f"✅ ChromaDB에 {len(new_documents)}개의 문서 추가 완료")
            else:
                logger.info("ℹ️ 추가할 새 문서가 없습니다 (모두 중복).")
        except Exception as e:
            logger.exception(f"🚫 문서 추가 오류: {e}")

    def get(self, include: list[str] = ["metadatas", "documents"]): # include 파라미터 기본값 명시
        try:
            if not self.db:
                logger.error("🚫 Chroma DB가 초기화되지 않아 데이터를 가져올 수 없습니다.")
                return {"ids": [], "embeddings": None, "metadatas": [], "documents": [], "uris": None, "data": None} # 빈 결과 반환 형태 일치
            # Chroma의 get() 메서드는 기본적으로 Document 객체가 아닌 dict를 반환합니다.
            # ids, embeddings, metadatas, documents, uris, data 등의 키를 가집니다.
            return self.db.get(include=include)
        except Exception as e:
            logger.exception(f"🚫 데이터 가져오기 오류: {e}")
            return {"ids": [], "embeddings": None, "metadatas": [], "documents": [], "uris": None, "data": None}


    def delete(self, ids: list[str]): # 단일 ID 대신 ID 리스트를 받도록 수정 (Chroma API에 맞게)
        try:
            if not self.db:
                logger.error("🚫 Chroma DB가 초기화되지 않아 문서를 삭제할 수 없습니다.")
                return
            if not ids:
                logger.warning("⚠️ 삭제할 문서 ID가 제공되지 않았습니다.")
                return
            self.db.delete(ids=ids)
            logger.info(f"✅ 문서 ID {ids} 삭제 완료")
        except Exception as e:
            logger.exception(f"🚫 문서 삭제 오류: {e}")

    def clear_db(self):
        # ChromaDB 자체에는 전체 데이터를 'clear'하는 직접적인 API가 없을 수 있습니다.
        # persist_directory를 삭제하고 다시 만드는 방식이 일반적입니다.
        # 또는 모든 ID를 가져와서 delete 하는 방법도 있지만, 매우 비효율적입니다.
        # 여기서는 단순히 디렉토리 내 파일을 삭제하는 방식을 유지하되, Chroma 인스턴스도 재설정 필요.
        try:
            if os.path.exists(self.persist_directory):
                # 현재 로드된 self.db 인스턴스를 먼저 정리하거나,
                # 파일 삭제 후 self.db = None으로 설정하고, 필요시 재초기화.
                # 가장 확실한 방법은 디렉토리 삭제 후, 다시 __init__ 로직을 통해 객체를 생성하는 것입니다.
                # 여기서는 파일만 삭제하고, 다음 실행 시 새로 생성되도록 유도합니다.
                # self.db._client.reset() # 내부 API 사용 (권장되지 않음, 버전 따라 다름)
                # 또는
                # collection = self.db._collection # 내부 API
                # if collection.count() > 0:
                #     all_ids = self.db.get(include=[])['ids']
                #     if all_ids:
                #         self.db.delete(ids=all_ids)
                # logger.info("✅ 모든 문서 삭제 완료 (DB API 사용)")

                # 파일 시스템 기반 삭제 (더 확실하지만, DB 객체 상태와 불일치 가능성)
                import shutil
                shutil.rmtree(self.persist_directory)
                os.makedirs(self.persist_directory, exist_ok=True)
                logger.info(f"✅ {self.persist_directory} 디렉토리 초기화 완료. DB 재연결 필요.")
                # DB 객체를 재초기화
                self.__init__(self.persist_directory, self.model_name)

            else:
                logger.info("ℹ️ 삭제할 데이터가 없습니다 (디렉토리 없음).")
        except Exception as e:
            logger.exception(f"🚫 데이터 초기화 오류: {e}")