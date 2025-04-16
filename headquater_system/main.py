# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import uvicorn

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 본사(HQ) 시스템 API 라우터 import
from routers.hq import hq_router

app = FastAPI(
    title="FacMan AI HQ System",
    description="STT, 번역, TTS 기능을 제공하는 API 시스템",
    version="1.0.0"
)

# CORS 설정: 실제 배포 환경에 맞게 Vue.js 도메인 지정 필요
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5002", "https://facman.duckdns.org"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HQ API 라우터 포함 (프리픽스: /ai/hq/api)
app.include_router(hq_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="https://facman.duckdns.org", port=8002)
    # uvicorn.run(app, host="0.0.0.0", port=8002)