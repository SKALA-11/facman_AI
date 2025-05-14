import os
import json
# import fitz # PDF 처리 라이브러리 이제 필요 없음
import re
from langchain_core.documents import Document # langchain.schema 대신 langchain_core.documents 사용
from .chromadb_wrapper import ChromaDBWrapper # chromadb_wrapper는 그대로 사용
import logging

# 로거 설정
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO) # INFO 레벨 이상의 로그를 출력

class JsonDataProcessor: # 클래스 이름을 좀 더 명확하게 변경
    def __init__(
        self,
        json_data_path: str, # 입력 JSON 파일의 전체 경로
        chroma_dir: str = "./chroma_db_filtered", # ChromaDB 저장 디렉토리
        # output_json_path: str = "filtered_data_output.json" # 필터링된 결과를 저장할 경로 (선택적)
    ):
        self.json_data_path = json_data_path
        # self.output_json_path = output_json_path # 이 예제에서는 필터링 후 별도 저장 안 함
        self.db = ChromaDBWrapper(persist_directory=chroma_dir) # ChromaDBWrapper 사용
        self.data_for_chroma = [] # ChromaDB에 저장할 Document 객체 리스트
        self.keywords = ["안전", "보안", "위험", "준수", "조치"] # 키워드 필터링은 유지 (선택 사항)

    def clean_text(self, text: str) -> str:
        # 줄바꿈과 연속 공백 정리
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def filter_by_keywords(self, text: str) -> str:
        # 문장 단위로 나누어 키워드 포함 문장만 추출 (기존 로직 유지)
        # 더 정교한 필터링이 필요하면 이 부분을 수정하거나, 키워드 리스트를 확장/변경
        sentences = re.split(r"(?<=[.?!])\s+", text) # 문장 분리
        filtered_sentences = [
            sentence
            for sentence in sentences
            if any(keyword in sentence for keyword in self.keywords)
        ]
        # 필터링된 문장이 없으면 원본 텍스트의 일부라도 반환하거나, 빈 문자열 반환 결정 필요
        # 여기서는 필터링된 문장이 있으면 합치고, 없으면 원본 텍스트의 앞 500자 정도를 사용 (예시)
        if filtered_sentences:
            return " ".join(filtered_sentences)
        # elif text: # 키워드가 없더라도 일부 내용을 포함시키고 싶다면 주석 해제
        #     logger.warning(f"키워드가 없어 원본 텍스트 일부를 사용합니다 (첫 500자).")
        #     return text[:500] + "..." # 원본 텍스트의 일부라도 사용 (너무 길면 자르기)
        return "" # 키워드 필터링 결과가 없으면 빈 문자열 반환 (저장 안 함)


    def process_json_file(self):
        logger.info(f"'{self.json_data_path}' 파일 처리 시작...")
        try:
            with open(self.json_data_path, "r", encoding="utf-8") as f:
                loaded_json_data = json.load(f)
            
            if not isinstance(loaded_json_data, list):
                logger.error(f"'{self.json_data_path}' 파일은 리스트 형태의 JSON이어야 합니다.")
                return

            for item in loaded_json_data:
                if not isinstance(item, dict) or "file_name" not in item or "text" not in item:
                    logger.warning(f"JSON 항목 형식이 올바르지 않아 건너<0xEB><0x8F><0xED><0x9E><0x88>니다: {item}")
                    continue

                file_name = item["file_name"]
                raw_text = item["text"]

                if raw_text:
                    # cleaned_text = self.clean_text(raw_text) # JSON 텍스트는 이미 어느 정도 정제되었을 수 있음 (필요시 사용)
                    # filtered_text = self.filter_by_keywords(cleaned_text) # 키워드 기반 필터링 적용
                    
                    # 데모용 모의 데이터는 이미 잘 정제되었고 특정 목적을 가지므로,
                    # 키워드 필터링을 생략하고 모든 텍스트를 사용하는 것을 고려해볼 수 있습니다.
                    # 만약 키워드 필터링을 원치 않으면 다음 라인을 사용:
                    processed_text = self.clean_text(raw_text) # 간단한 클리닝만 적용
                    # 또는 키워드 필터링을 계속 사용하려면:
                    # processed_text = self.filter_by_keywords(self.clean_text(raw_text))

                    if processed_text:
                        # Langchain Document 객체로 변환
                        document = Document(
                            page_content=processed_text,
                            metadata={"file_name": file_name, "source": self.json_data_path} # 메타데이터에 출처 추가
                        )
                        self.data_for_chroma.append(document)
                        logger.info(f"문서 처리 완료 (ChromaDB 추가 예정): {file_name}")
                    else:
                        logger.info(f"내용이 없거나 필터링되어 제외된 항목: {file_name}")
                else:
                    logger.warning(f"'text' 필드가 비어있는 항목: {file_name}")

        except FileNotFoundError:
            logger.error(f"🚫 JSON 데이터 파일 '{self.json_data_path}'를 찾을 수 없습니다.")
        except json.JSONDecodeError:
            logger.error(f"🚫 JSON 데이터 파일 '{self.json_data_path}' 파싱 오류.")
        except Exception as e:
            logger.exception(f"JSON 데이터 처리 중 예기치 않은 오류 발생: {e}")

    # def save_filtered_json(self): # 필터링된 결과를 별도 파일로 저장할 경우 사용
    #     if not self.data_for_chroma:
    #         logger.info("저장할 필터링된 데이터가 없습니다.")
    #         return
    #     # Document 객체 리스트를 다시 JSON 직렬화 가능한 dict 리스트로 변환
    #     output_data = [{"file_name": doc.metadata.get("file_name"), "text": doc.page_content} for doc in self.data_for_chroma]
    #     with open(self.output_json_path, "w", encoding="utf-8") as f:
    #         json.dump(output_data, f, ensure_ascii=False, indent=4)
    #     logger.info(f"💾 필터링된 JSON 저장 완료: {self.output_json_path}")

    def save_to_chroma(self):
        if not self.data_for_chroma:
            logger.warning("ChromaDB에 저장할 데이터가 없습니다.")
            return
        
        logger.info(f"{len(self.data_for_chroma)}개의 문서를 ChromaDB에 추가합니다...")
        try:
            self.db.add_documents(self.data_for_chroma) # ChromaDBWrapper의 add_documents 호출
            logger.info(f"💾 Chroma DB 저장 완료. 총 {len(self.data_for_chroma)}개 문서 추가됨. 위치: {self.db.persist_directory}")
        except Exception as e:
            logger.exception(f"ChromaDB에 문서 저장 중 오류 발생: {e}")


    def run(self):
        logger.info("JsonDataProcessor 실행 시작...")
        self.process_json_file() # JSON 파일 처리

        if self.data_for_chroma:
            # self.save_filtered_json() # 필터링된 결과를 별도 JSON으로 저장할 필요 없다면 주석 처리
            self.save_to_chroma() # ChromaDB에 저장
        else:
            logger.info("처리된 데이터가 없어 ChromaDB에 저장하지 않았습니다.")
        logger.info("JsonDataProcessor 실행 완료.")


# 실행 예시
if __name__ == "__main__":
    # 이 스크립트(factory_problem_data_collection.py)는 local_system/vector_db/ 에 위치합니다.
    # filtered_data.json은 local_system/gen_rand_events/ 에 있습니다.
    # 경로를 정확히 계산합니다.
    
    # 현재 스크립트 파일의 절대 경로를 기준으로 경로 설정
    current_script_path = os.path.abspath(__file__) # factory_problem_data_collection.py의 절대 경로
    vector_db_dir = os.path.dirname(current_script_path) # local_system/vector_db/
    local_system_root_dir = os.path.dirname(vector_db_dir) # local_system/
    project_root_dir = os.path.dirname(local_system_root_dir) # facman_AI/ (가정)

    # 입력 JSON 파일 경로 설정
    json_input_file_path = os.path.join(local_system_root_dir, "gen_rand_events", "filtered_data.json")

    # ChromaDB 저장 디렉토리 설정 (vector_db 폴더 내에 생성)
    chroma_database_dir = os.path.join(vector_db_dir, "chroma_db_from_json") # 새 이름으로 변경 (기존 DB와 구분)
    
    # --- 중요: 이전 ChromaDB 디렉토리 삭제 ---
    # 임베딩 모델이나 데이터 소스가 변경될 때는 이전 DB를 삭제하는 것이 좋습니다.
    # 여기서는 chroma_database_dir을 사용하므로, 만약 이전에 이 이름으로 DB가 있었다면 삭제.
    if os.path.exists(chroma_database_dir):
        import shutil
        logger.info(f"기존 ChromaDB 디렉토리 '{chroma_database_dir}'를 삭제합니다.")
        try:
            shutil.rmtree(chroma_database_dir)
        except Exception as e:
            logger.error(f"디렉토리 삭제 중 오류 발생 '{chroma_database_dir}': {e}. 수동으로 삭제 후 다시 시도해주세요.")
            exit() # 심각한 오류 시 종료
    os.makedirs(chroma_database_dir, exist_ok=True) # 삭제 후 다시 생성 (빈 디렉토리)
    # --- 중요: 이전 ChromaDB 디렉토리 삭제 끝 ---


    logger.info(f"입력 JSON 파일 경로: {json_input_file_path}")
    logger.info(f"ChromaDB 저장 경로: {chroma_database_dir}")

    processor = JsonDataProcessor(
        json_data_path=json_input_file_path,
        chroma_dir=chroma_database_dir
    )
    processor.run()