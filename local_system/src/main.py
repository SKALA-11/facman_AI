from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.router import router
# db_migration.py 모듈 가져오기
from .db_migration import main as db_main

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.include_router(router)

if __name__ == "__main__":
    db_main()
    
