# app/services/telegram_service.py
from typing import List, Tuple
import asyncio
from pyrogram import Client
from pyrogram.errors import FloodWait
from app.config import settings
from app.models import BareMessage

class TelegramService:
    def __init__(self, session_name: str = "telegram_crawler_session"):
        self.session_name = session_name
        self.client = Client(
            name=self.session_name,
            api_id=settings.api_id,
            api_hash=settings.api_hash
        )

    async def get_new_messages(self, channel_name: str, last_known_id: int) -> Tuple[List[BareMessage], int]:
        all_recent_messages = []
        async for message in self.client.get_chat_history(channel_name, limit=100):
            all_recent_messages.append(message)

        if not all_recent_messages:
            return [], last_known_id

        newest_id_in_batch = all_recent_messages[0].id

        messages_to_add = []
        for message in all_recent_messages:
            if message.id > last_known_id:
                message_content = message.text or message.caption
                if message_content:
                    messages_to_add.append(
                        BareMessage(
                            channel_name=channel_name,
                            message_id=message.id,
                            message_text=message_content,
                            message_timestamp=message.date
                        )
                    )
        return messages_to_add, newest_id_in_batch

    def create_message_link(self, channel_name: str, message_id: int) -> str:
        """
        Create a Telegram message link for the given channel and message ID.
        
        Args:
            channel_name: The channel username (without @)
            message_id: The message ID
            
        Returns:
            A clickable Telegram link to the specific message
        """
        # Remove @ if present in channel name
        clean_channel_name = channel_name.lstrip('@')
        return f"https://t.me/{clean_channel_name}/{message_id}"

    async def send_to_warehouse(self, message_text: str, channel_name: str = None, message_id: int = None):
        """
        Sends a message to the configured warehouse channel with proper rate limiting.
        
        Args:
            message_text: The message content to forward
            channel_name: Optional channel name to create a link back to original message
            message_id: Optional message ID to create a link back to original message
        """
        if not settings.warehouse_channel_id:
            return
            
        # Add hyperlink if channel and message ID are provided
        final_message = message_text
        if channel_name and message_id:
            message_link = self.create_message_link(channel_name, message_id)
            final_message = f"{message_text}\n\n🔗 [View Original Message]({message_link})"
        
        max_retries = settings.max_send_retries
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Try Markdown first
                from pyrogram import enums
                await self.client.send_message(
                    chat_id=settings.warehouse_channel_id,
                    text=final_message,
                    parse_mode=enums.ParseMode.MARKDOWN
                )
                print(f"✅ Successfully sent message to warehouse (attempt {retry_count + 1})")
                return  # Success - exit the function
                
            except FloodWait as e:
                print(f"⏱️ Rate limited: waiting {e.value} seconds before retry {retry_count + 1}/{max_retries}")
                await asyncio.sleep(e.value)
                retry_count += 1
                continue
                
            except Exception as parse_error:
                # Try HTML as fallback
                try:
                    html_message = f"{message_text}\n\n🔗 <a href=\"{self.create_message_link(channel_name, message_id)}\">View Original Message</a>" if channel_name and message_id else message_text
                    await self.client.send_message(
                        chat_id=settings.warehouse_channel_id,
                        text=html_message,
                        parse_mode=enums.ParseMode.HTML
                    )
                    print(f"✅ Successfully sent message to warehouse using HTML (attempt {retry_count + 1})")
                    return  # Success - exit the function
                    
                except FloodWait as e:
                    print(f"⏱️ Rate limited during HTML attempt: waiting {e.value} seconds before retry {retry_count + 1}/{max_retries}")
                    await asyncio.sleep(e.value)
                    retry_count += 1
                    continue
                    
                except Exception as html_error:
                    # Final fallback: plain text
                    try:
                        if channel_name and message_id:
                            message_link = self.create_message_link(channel_name, message_id)
                            fallback_message = f"{message_text}\n\n🔗 View Original Message:\n{message_link}"
                        else:
                            fallback_message = message_text
                        
                        await self.client.send_message(
                            chat_id=settings.warehouse_channel_id,
                            text=fallback_message
                        )
                        print(f"✅ Successfully sent message to warehouse using plain text (attempt {retry_count + 1})")
                        return  # Success - exit the function
                        
                    except FloodWait as e:
                        print(f"⏱️ Rate limited during plain text attempt: waiting {e.value} seconds before retry {retry_count + 1}/{max_retries}")
                        await asyncio.sleep(e.value)
                        retry_count += 1
                        continue
                        
                    except Exception as final_error:
                        print(f"❌ All formatting attempts failed: {final_error}")
                        break
        
        # If we get here, all retries failed
        print(f"❌ Failed to send message to warehouse after {max_retries} attempts")

    async def __aenter__(self):
        await self.client.start()

        # --- YOUR CACHE-WARMING LOGIC ---
        # This is the key fix to ensure the client knows about all channels.
        print("[INFO] Initializing channel cache by getting dialogs...")
        async for dialog in self.client.get_dialogs(limit=200):
            # We don't need to do anything with the dialogs,
            # just fetching them is enough to populate the cache.
            pass
        print("[INFO] Cache initialized.")
        # --- END OF FIX ---

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client and self.client.is_connected:
            await self.client.stop()