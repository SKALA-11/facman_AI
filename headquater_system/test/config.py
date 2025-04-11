import os
from dotenv import load_dotenv
import openai

load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
SAMPLE_RATE = 16000
BLOCK_SIZE = 4000  # 0.25초 분량
TARGET_LANGUAGE = "en"
DEFAULT_LANGUAGE = "ko"

openai.api_key = API_KEY
CLIENT = openai.OpenAI()
