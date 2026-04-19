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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
