# app/config.py
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Database
    db_type: str
    db_username: str
    db_password: str
    db_host: str
    db_name: str

    # Telegram
    api_id: int
    api_hash: str
    vless_url: str | None = None
    channels_to_crawl: str

    @property
    def database_url(self) -> str:
        return f"{self.db_type}://{self.db_username}:{self.db_password}@{self.db_host}/{self.db_name}"

    @property
    def channel_list(self) -> List[str]:
        return self.channels_to_crawl.split(',')

    class Config:
        env_file = ".env"

settings = Settings()