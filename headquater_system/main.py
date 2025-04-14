# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 본사(HQ) 시스템 API 라우터 import
from .routers.hq import hq_router

app = FastAPI()

# CORS 설정: 실제 배포 환경에 맞게 Vue.js 도메인 지정 필요
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5002", "https://facman.duckdnc.org"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HQ API 라우터 포함 (프리픽스: /ai/hq/api)
app.include_router(hq_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="https://facman.duckdnc.org", port=8002)
    # uvicorn.run(app, host="0.0.0.0", port=8002)