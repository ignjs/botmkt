import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
