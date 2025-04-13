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