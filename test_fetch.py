# test_fetch.py
import asyncio
from pyrogram import Client

# --- CONFIGURATION ---
# !!! IMPORTANT: Replace these with your actual credentials !!!
API_ID = 20383014
API_HASH = "5e38f4b75146d33899c3884a8b4b42b1"
CHANNEL_NAME = "Tasnimnews" # The channel we are testing
SESSION_NAME = "telegram_crawler_session"

async def main():
    print(f"--- Attempting to connect and fetch messages from {CHANNEL_NAME} ---")
    
    try:
        # Using 'with' ensures the client connects and disconnects properly
        async with Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH) as app:
            print("\n[SUCCESS] Client connected successfully.")
            print("Fetching the 10 most recent messages...\n")
            
            count = 0
            # Get the 10 most recent messages
            async for message in app.get_chat_history(CHANNEL_NAME, limit=10):
                count += 1
                
                # --- THIS IS THE FIX ---
                # Check for message.text OR message.caption to get text from all message types
                message_content = message.text or message.caption
                # --- END OF FIX ---

                text_preview = "NO TEXT"
                if message_content:
                    # Sanitize the found text for printing
                    text_preview = message_content.replace("\n", " ").strip()[:70]
                
                print(f"  - Message ID: {message.id}, Date: {message.date}, Text: '{text_preview}...'")
            
            if count == 0:
                print("\n[RESULT] FAILED to fetch any messages.")
            else:
                print(f"\n[RESULT] Successfully fetched {count} messages.")
    except Exception as e:
        print(f"\n[ERROR] An exception occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
