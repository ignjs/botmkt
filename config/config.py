import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
    API_HOST = os.getenv("API_HOST", "127.0.0.1")
    API_PORT = int(os.getenv("API_PORT", 8000))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", 0))
