from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SCRAPER_")

    user_agent: str = "JobScraper/0.1 (+local development)"
    request_timeout_seconds: float = 20.0
    request_delay_seconds: float = 1.0
    max_results: int = 25
    output_dir: Path = Path("data")


settings = Settings()
