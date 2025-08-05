# app/schemas.py
from pydantic import BaseModel
from typing import List

class CrawlResponse(BaseModel):
    status: str
    new_messages_found: int
    channels_crawled: List[str]
