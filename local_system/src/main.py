from fastapi import FastAPI
from .api.router import router
# db_migration.py 모듈 가져오기
from .db_migration import main as db_main

app = FastAPI()
app.include_router(router)
    
