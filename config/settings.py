from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment."""

    telegram_token: str
    database_url: str

    openai_api_key: str = ""
    perplexity_api_key: str = ""
    log_level: str = "INFO"

    risk_free_rate: float = 5.0
    benchmark_symbol: str = "^GSPC"
    atr_multiplier: float = 2.0
    alert_cooldown_hours: int = 4
    market_open: str = "09:30"
    market_close: str = "17:00"
    market_tz: str = "America/New_York"

    ai_analysis_timeout: int = 30
    ai_max_tokens: int = 600
    earnings_wait_timeout: int = 120

    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_mode: str = "paper"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
