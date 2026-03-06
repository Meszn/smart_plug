from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Smart Plug API"
    app_version: str = "1.0.0"
    debug: bool = False

    database_url: str = "postgresql://smartplug:smartplug123@localhost:5432/smartplug_db"

    network_scan_timeout: float = 1.0
    network_scan_concurrency: int = 50
    polling_timeout: float = 5.0

    # Tapo P-serisi için (HS-serisi gerekmez)
    tapo_email: str = ""
    tapo_password: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()