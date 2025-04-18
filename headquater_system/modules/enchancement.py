# modules/enhancement.py

import asyncio
import aiomysql
from datetime import datetime

from config import DB_URL
# 전역 큐
enhancement_queue: asyncio.Queue = asyncio.Queue()

async def enqueue_enhancement(session_id: str, speaker: str, transcription: str, translation: str, timestamp: str):
    """
    RAG + DB 적재용 큐에 데이터를 넣는 헬퍼 함수
    """
    await enhancement_queue.put({
        "session_id": session_id,
        "speaker": speaker,
        "transcription": transcription,
        "translation": translation,
        "timestamp": timestamp,
    })

# async def rag_enhancement_worker():
#     """
#     enhancement_queue에서 아이템을 꺼내
#      1. transcription/translation 로 RAG(vector search + LLM)
#      2. 결과를 MariaDB에 비동기로 INSERT
#     """
#     # MariaDB 풀 생성 (config 값으로 바꿔주세요)
#     pool = await aiomysql.create_pool(
#         host="DB_HOST", port=3306,
#         user="DB_USER", password="DB_PASS",
#         db="DB_NAME", autocommit=True,
#     )
#     llm_chain = LLMChain(...)  # RAG용 LLM 설정

#     while True:
#         item = await enhancement_queue.get()
#         try:
#             # 1) 벡터 DB에서 유사 문서 검색
#             query_text = item["translation"] or item["transcription"]
#             docs = await vector_search(query_text, top_k=5)

#             # 2) LLM에 컨텍스트와 질문을 주고 보강된 답변 생성
#             context = "\n\n".join(doc.page_content for doc in docs)
#             answer = await llm_chain.run(
#                 question=query_text,
#                 context=context
#             )

#             # 3) MariaDB에 INSERT
#             async with pool.acquire() as conn:
#                 async with conn.cursor() as cur:
#                     await cur.execute(
#                         """
#                         INSERT INTO solution_table
#                             (session_id, speaker, question, answer, created_at)
#                         VALUES
#                             (%s, %s, %s, %s, %s)
#                         """,
#                         (
#                             item["session_id"],
#                             item["speaker"],
#                             query_text,
#                             answer,
#                             datetime.fromisoformat(item["timestamp"])
#                         )
#                     )
#         except Exception as e:
#             logger.error(f"RAG 적재 중 오류: {e}", exc_info=True)
#         finally:
#             enhancement_queue.task_done()
