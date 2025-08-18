# test_send.py
import asyncio
from pyrogram import Client
from datetime import datetime
from pyrogram.errors import PeerIdInvalid

# --- CONFIGURATION ---
API_ID = 20383014
API_HASH = "5e38f4b75146d33899c3884a8b4b42b1"
WAREHOUSE_CHANNEL_ID = -1002515543914
SESSION_NAME = "telegram_crawler_session"

async def main():
    print("--- Attempting to connect and send a message to the warehouse channel ---")
    
    try:
        async with Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH) as app:
            print("\n[SUCCESS] Client connected successfully.")
            
            # Warm up the cache by getting dialogs (but don't print them)
            print("[INFO] Initializing channel cache...")
            dialogs = []
            async for dialog in app.get_dialogs(limit=100):  # Limit to avoid too much data
                dialogs.append(dialog)
                # Stop once we find our target channel
                if dialog.chat.id == WAREHOUSE_CHANNEL_ID:
                    break
            
            print(f"[INFO] Cache initialized. Found {len(dialogs)} recent chats.")
            
            # Now try to get the channel
            try:
                chat = await app.get_chat(WAREHOUSE_CHANNEL_ID)
                print(f"[SUCCESS] Channel resolved: {chat.title}")
            except PeerIdInvalid:
                print("[ERROR] Channel still not found. Make sure:")
                print("1. You're a member/admin of the channel")
                print("2. The channel ID is correct")
                print("3. You've interacted with the channel recently")
                return
            
            # Create and send test message
            test_message = f"Test message from Python script at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            print(f"\nAttempting to send message:")
            print(f"'{test_message}'")
            
            result = await app.send_message(
                chat_id=WAREHOUSE_CHANNEL_ID,
                text=test_message
            )
            
            print(f"\n[SUCCESS] Message sent successfully!")
            print(f"Message ID: {result.id}")
            print("Check your channel to confirm.")
            
    except Exception as e:
        print(f"\n[ERROR] An exception occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
