import os
import json
import fitz
import re
from langchain.schema import Document
from chromadb_wrapper import ChromaDBWrapper

class KeywordFilteredPDFExtractor:
    def __init__(self, pdf_folder, json_path="filtered_data.json", chroma_dir="./chroma_db_filtered"):
        self.pdf_folder = pdf_folder
        self.json_path = json_path
        self.db = ChromaDBWrapper(chroma_dir)
        self.data = []
        self.keywords = ["안전", "보안", "위험", "준수", "조치"]

    def clean_text(self, text):
        # 줄바꿈과 공백 정리
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def filter_by_keywords(self, text):
        sentences = re.split(r'(?<=[.?!])\s+', text)
        filtered_sentences = [sentence for sentence in sentences if any(keyword in sentence for keyword in self.keywords)]
        return ' '.join(filtered_sentences)

    def extract_text_from_pdf(self, pdf_path):
        try:
            with fitz.open(pdf_path) as doc:
                text = ''.join(page.get_text() for page in doc)
            return text
        except Exception as e:
            print(f"❌ PDF 추출 실패 ({pdf_path}): {e}")
            return ""

    def process_pdfs(self):
        for pdf_name in os.listdir(self.pdf_folder):
            if pdf_name.lower().endswith(".pdf"):
                pdf_path = os.path.join(self.pdf_folder, pdf_name)
                raw_text = self.extract_text_from_pdf(pdf_path)
                if raw_text:
                    cleaned_text = self.clean_text(raw_text)
                    filtered_text = self.filter_by_keywords(cleaned_text)
                    if filtered_text:  # 키워드가 포함된 내용만 저장
                        self.data.append({"file_name": pdf_name, "text": filtered_text})
                        print(f"✅ 키워드 추출 성공: {pdf_name}")
                    else:
                        print(f"⚠️ 키워드 미포함으로 제외: {pdf_name}")

    def save_json(self):
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)
        print(f"💾 JSON 저장 완료: {self.json_path}")

    def save_to_chroma(self):
        documents = [
            Document(page_content=item["text"], metadata={"file_name": item["file_name"]})
            for item in self.data
        ]
        self.db.add_documents(documents)
        print(f"💾 Chroma DB 저장 완료: {self.db.persist_directory}")

    def run(self):
        self.process_pdfs()
        self.save_json()
        self.save_to_chroma()

# 실행 예시
if __name__ == "__main__":
    extractor = KeywordFilteredPDFExtractor(pdf_folder="safety_pdfs")
    extractor.run()
