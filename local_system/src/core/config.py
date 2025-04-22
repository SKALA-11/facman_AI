#================================================================================#
# 애플리케이션의 주요 설정 값과 경로를 정의합니다.
# .env 파일로부터 환경 변수(API 키, 이메일 정보 등)를 로드하고, 프로젝트의 기본 디렉토리, 벡터 데이터베이스 경로 등을 계산하여 상수로 제공합니다.
# 다른 모듈에서는 이 파일의 상수들을 임포트하여 사용합니다.

# [ 주요 로직 흐름 ]
# 1. load_dotenv() 함수를 호출하여 .env 파일에 정의된 환경 변수를 로딩.
# 2. 환경 변수 로딩:
#    - OPENAI_API_KEY: OpenAI 서비스 사용을 위한 API 키.
#    - EMAIL_ADDRESS: 보고서 발송 등에 사용될 이메일 계정 주소.
#    - EMAIL_PASSWORD: 해당 이메일 계정의 비밀번호 또는 앱 비밀번호.
# 3. 경로 계산 및 정의:
#    - CONFIG_PATH: 현재 설정 파일(config.py)의 절대 경로.
#    - BASE_DIR: 프로젝트의 루트 디렉토리 경로 (config.py 위치 기준 계산).
#    - VECTOR_DB_DIR: 벡터 데이터베이스 파일들이 저장될 디렉토리 경로.
#    - VECTOR_DB: 실제 ChromaDB 데이터가 저장될 최종 경로.
#================================================================================#


import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

CONFIG_PATH = os.path.abspath(__file__)
BASE_DIR = os.path.dirname(os.path.dirname(CONFIG_PATH))
VECTOR_DB_DIR = os.path.join(os.path.dirname(BASE_DIR), "vector_db")

VECTOR_DB = os.path.join(VECTOR_DB_DIR, "chroma_db")

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")