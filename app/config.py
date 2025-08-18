# app/config.py
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    db_type: str
    db_username: str
    db_password: str
    db_host: str
    db_name: str
    api_id: int
    api_hash: str
    channels_to_crawl: str
    warehouse_channel_id: int
    
    # Rate limiting settings (optional)
    message_delay_seconds: int = 2  # Delay between forwarded messages
    max_send_retries: int = 3       # Maximum retries for failed sends

    @property
    def database_url(self) -> str:
        return f"{self.db_type}://{self.db_username}:{self.db_password}@{self.db_host}/{self.db_name}"

    @property
    def channel_list(self) -> List[str]:
        return self.channels_to_crawl.split(',')

    class Config:
        env_file = ".env"

settings = Settings()