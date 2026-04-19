import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
    API_HOST = os.getenv("API_HOST", "127.0.0.1")
    API_PORT = int(os.getenv("API_PORT", 8000))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    API_KEY = os.getenv("API_KEY")

    # E1 — ATR Stop-Loss
    ATR_MULTIPLIER = float(os.getenv("ATR_MULTIPLIER", 2.0))

    # E2 — Scheduler / Alerts
    MARKET_OPEN = os.getenv("MARKET_OPEN", "09:30")
    MARKET_CLOSE = os.getenv("MARKET_CLOSE", "17:00")
    MARKET_TZ = os.getenv("MARKET_TZ", "America/New_York")
    ALERT_COOLDOWN_HOURS = int(os.getenv("ALERT_COOLDOWN_HOURS", 4))

    # E3 — Portfolio Metrics
    RISK_FREE_RATE = float(os.getenv("RISK_FREE_RATE", 5.0))
    BENCHMARK_SYMBOL = os.getenv("BENCHMARK_SYMBOL", "^GSPC")

    # E5 — Alpaca Broker
    ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
    ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
    ALPACA_MODE = os.getenv("ALPACA_MODE", "paper")
