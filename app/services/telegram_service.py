# app/services/telegram_service.py
import asyncio
from typing import List, Dict
from pyrogram import Client
from v2ray2proxy import V2RayProxy
from ..config import settings
from ..models import BareMessage

class TelegramService:
    def __init__(self, session_name: str = "telegram_crawler_session"):
        self.session_name = session_name
        self.vless_proxy_instance = None
        self.proxy_dict = None

    async def _setup_proxy(self):
        if settings.vless_url:
            if not V2RayProxy:
                raise RuntimeError("v2ray2proxy is not installed.")
            
            self.vless_proxy_instance = V2RayProxy(settings.vless_url)
            await asyncio.sleep(5)
            parts = self.vless_proxy_instance.socks5_proxy_url.replace("socks5://", "").split(":")
            self.proxy_dict = {"scheme": "socks5", "hostname": parts[0], "port": int(parts[1])}

    async def get_new_messages(self, channel_name: str, last_known_id: int) -> (List[BareMessage], int):
        messages_to_add = []
        newest_id_found = last_known_id
        
        async for message in self.client.get_chat_history(channel_name, limit=100):
            if message.id > last_known_id:
                if message.text:
                    messages_to_add.append(
                        BareMessage(
                            channel_name=channel_name,
                            message_id=message.id,
                            message_text=message.text,
                            message_timestamp=message.date
                        )
                    )
                if message.id > newest_id_found:
                    newest_id_found = message.id
            else:
                break
        
        return messages_to_add, newest_id_found

    async def __aenter__(self):
        await self._setup_proxy()
        self.client = Client(
            name=self.session_name,
            api_id=settings.api_id,
            api_hash=settings.api_hash,
            proxy=self.proxy_dict
        )
        await self.client.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client and self.client.is_connected:
            await self.client.stop()
        if self.vless_proxy_instance:
            self.vless_proxy_instance.stop()
