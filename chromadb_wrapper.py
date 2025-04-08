# ChromaDB Wrapper for Managing Factory Problem Data

import os
import json
from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings
from langchain.schema import Document
from dotenv import load_dotenv

class ChromaDBWrapper:
    def __init__(self, persist_directory='./chroma_db'):
        load_dotenv()
        self.persist_directory = persist_directory
        self.embeddings = OpenAIEmbeddings()
        try:
            self.db = Chroma(persist_directory=self.persist_directory, embedding_function=self.embeddings)
            print(f'✅ 기존 Chroma DB 불러오기 완료 (디렉토리: {self.persist_directory})')
        except Exception as e:
            print(f'🚫 Chroma DB 초기화 오류: {e}')
            self.db = None

    def add_documents(self, documents):
        try:
            if not documents:
                print("⚠️ 추가할 문서가 없습니다.")
                return

            # 중복 제거를 위해 기존 데이터 확인
            existing_docs = {d['text'] for d in self.get()} if self.get() else set()
            new_documents = [doc for doc in documents if doc.page_content not in existing_docs]

            if new_documents:
                self.db.add_documents(new_documents)
                print(f'✅ ChromaDB에 {len(new_documents)}개의 문서 추가 완료')
            else:
                print("ℹ️ 중복된 문서로 인해 추가하지 않았습니다.")
        except Exception as e:
            print(f'🚫 문서 추가 오류: {e}')

    def get(self):
        try:
            documents = self.db.get()
            if isinstance(documents, str):
                print("Warning: Unexpected string format in ChromaDB data.")
                documents = json.loads(documents)
            if not isinstance(documents, list):
                print("Error: ChromaDB returned non-list data.")
                return []
            return documents
        except Exception as e:
            print(f'🚫 데이터 가져오기 오류: {e}')
            return []

    def delete(self, doc_id):
        try:
            self.db.delete(doc_id)
            print(f'✅ 문서 ID {doc_id} 삭제 완료')
        except Exception as e:
            print(f'🚫 문서 삭제 오류: {e}')

    def clear_db(self):
        try:
            if os.path.exists(self.persist_directory):
                for file in os.listdir(self.persist_directory):
                    file_path = os.path.join(self.persist_directory, file)
                    os.remove(file_path)
                print("✅ 모든 문서 삭제 완료")
            else:
                print("ℹ️ 삭제할 데이터가 없습니다.")
        except Exception as e:
            print(f'🚫 데이터 초기화 오류: {e}')
