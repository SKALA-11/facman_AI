import os
from dotenv import load_dotenv
import openai
import logging

logger = logging.getLogger(__name__)
load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
DB_URL = os.getenv("DB_URL")

if not API_KEY:
    logger.error("환경 변수에서 OPENAI_API_KEY를 찾을 수 없습니다. .env 파일을 확인하세요.")
    raise ValueError("OPENAI_API_KEY not found in environment variables. Please set it in the .env file.")
try:
    CLIENT = openai.OpenAI(api_key=API_KEY)
    logger.info("OpenAI 클라이언트가 성공적으로 초기화되었습니다.")
except Exception as e:
    logger.exception(f"OpenAI 클라이언트 초기화 중 오류 발생: {e}")
    raise SystemExit(f"Failed to initialize OpenAI client: {e}")

SAMPLE_RATE = 16000
BLOCK_SIZE = 4000  # 0.25초 분량
TARGET_LANGUAGE = "en"
DEFAULT_LANGUAGE = "ko"

openai.api_key = API_KEY
CLIENT = openai.OpenAI()
