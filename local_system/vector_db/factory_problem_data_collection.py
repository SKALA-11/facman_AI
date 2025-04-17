import json
from langchain.schema import Document
from chromadb_wrapper import ChromaDBWrapper

class JSONToChromaSaver:
    def __init__(self, json_path, chroma_dir="./chroma_db_filtered"):
        self.json_path = json_path
        self.db = ChromaDBWrapper(chroma_dir)

    def load_json(self):
        with open(self.json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_to_chroma(self, data):
        # 유연한 구조 처리: list 또는 {"documents": list}
        if isinstance(data, list):
            doc_list = data
        elif "documents" in data:
            doc_list = data["documents"]
        else:
            print("⚠️ 유효한 문서 리스트를 찾을 수 없습니다.")
            return

        documents = [
            Document(
                page_content=item["text"],
                metadata={"title": item.get("title", f"doc_{idx}")}
            )
            for idx, item in enumerate(doc_list)
        ]

        self.db.add_documents(documents)
        print(f"💾 Chroma DB 저장 완료: {self.db.persist_directory}")

    def run(self):
        data = self.load_json()
        self.save_to_chroma(data)


# 실행
if __name__ == "__main__":
    processor = JSONToChromaSaver(json_path="../gen_rand_events/filtered_data.json")
    processor.run()
