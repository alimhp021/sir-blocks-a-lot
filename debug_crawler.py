# debug_crawler.py
"""
Comprehensive debugging script for the Telegram crawler.
This script will help identify why messages aren't being crawled.
"""

import os
import sys
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import desc

# Add the current directory to Python path
sys.path.insert(0, os.getcwd())

try:
    from app.models import BareMessage, ChannelState
    from app.config import settings
    from app.database import SessionLocal
    from app.services.telegram_service import TelegramService
except ImportError as e:
    print(f"Error importing app modules: {e}")
    print("Make sure you're running this script from the project root directory")
    sys.exit(1)


async def debug_channel_access():
    """Test if we can access each configured channel."""
    print("=== DEBUGGING CHANNEL ACCESS ===")
    
    async with TelegramService() as tg_service:
        for channel in settings.channel_list:
            print(f"\n🔍 Testing channel: {channel}")
            try:
                # Try to get basic channel info
                chat = await tg_service.client.get_chat(channel)
                print(f"  ✅ Channel found: {chat.title} (ID: {chat.id})")
                print(f"  📊 Type: {chat.type}")
                print(f"  👥 Members: {getattr(chat, 'members_count', 'Unknown')}")
                
                # Try to get recent messages
                message_count = 0
                recent_messages = []
                async for message in tg_service.client.get_chat_history(channel, limit=5):
                    message_count += 1
                    message_content = message.text or message.caption or "[Media/No Text]"
                    recent_messages.append({
                        'id': message.id,
                        'date': message.date,
                        'content': message_content[:50] + "..." if len(message_content) > 50 else message_content
                    })
                
                print(f"  📨 Recent messages found: {message_count}")
                for msg in recent_messages:
                    print(f"    - ID: {msg['id']}, Date: {msg['date']}, Content: '{msg['content']}'")
                    
            except Exception as e:
                print(f"  ❌ Error accessing channel: {e}")


def debug_database_state():
    """Check the current state of the database."""
    print("\n=== DEBUGGING DATABASE STATE ===")
    
    db = SessionLocal()
    try:
        # Check channel states
        print("\n📋 Channel States:")
        states = db.query(ChannelState).all()
        for state in states:
            print(f"  - {state.channel_name}: last_message_id = {state.last_message_id}, updated_at = {state.updated_at}")
        
        if not states:
            print("  ⚠️  No channel states found!")
        
        # Check recent messages
        print("\n📨 Recent Messages in DB:")
        recent_messages = (
            db.query(BareMessage)
            .order_by(desc(BareMessage.crawled_at))
            .limit(10)
            .all()
        )
        
        for msg in recent_messages:
            content_preview = msg.message_text[:50] + "..." if len(msg.message_text) > 50 else msg.message_text
            print(f"  - ID: {msg.message_id}, Channel: {msg.channel_name}, "
                  f"Crawled: {msg.crawled_at}, Content: '{content_preview}'")
        
        if not recent_messages:
            print("  ⚠️  No messages found in database!")
        
        # Count messages per channel
        print("\n📊 Message counts by channel:")
        from sqlalchemy import func
        counts = (
            db.query(
                BareMessage.channel_name,
                func.count(BareMessage.id).label('count'),
                func.max(BareMessage.message_id).label('max_id'),
                func.max(BareMessage.crawled_at).label('last_crawled')
            )
            .group_by(BareMessage.channel_name)
            .all()
        )
        
        for count in counts:
            print(f"  - {count.channel_name}: {count.count} messages, "
                  f"max_id: {count.max_id}, last_crawled: {count.last_crawled}")
    
    except Exception as e:
        print(f"❌ Database error: {e}")
    finally:
        db.close()


async def test_message_detection():
    """Test if new messages would be detected."""
    print("\n=== TESTING MESSAGE DETECTION LOGIC ===")
    
    db = SessionLocal()
    try:
        async with TelegramService() as tg_service:
            for channel in settings.channel_list:
                print(f"\n🔍 Testing message detection for: {channel}")
                
                # Get current state from DB
                state = db.query(ChannelState).filter(ChannelState.channel_name == channel).first()
                last_known_id = state.last_message_id if state else 0
                print(f"  📍 Last known message ID: {last_known_id}")
                
                # Get recent messages from Telegram
                all_recent_messages = []
                async for message in tg_service.client.get_chat_history(channel, limit=20):
                    all_recent_messages.append(message)
                
                if not all_recent_messages:
                    print(f"  ⚠️  No messages found in channel history!")
                    continue
                
                newest_id = all_recent_messages[0].id
                print(f"  📍 Newest message ID in channel: {newest_id}")
                
                # Check for new messages
                new_messages = []
                for message in all_recent_messages:
                    if message.id > last_known_id:
                        message_content = message.text or message.caption
                        if message_content:
                            new_messages.append({
                                'id': message.id,
                                'date': message.date,
                                'content': message_content[:100] + "..." if len(message_content) > 100 else message_content
                            })
                
                print(f"  📊 New messages that would be processed: {len(new_messages)}")
                for msg in new_messages[:5]:  # Show first 5
                    print(f"    - ID: {msg['id']}, Date: {msg['date']}, Content: '{msg['content']}'")
                
                if len(new_messages) > 5:
                    print(f"    ... and {len(new_messages) - 5} more")
                
                # Check for duplicates
                if new_messages:
                    message_ids = [msg['id'] for msg in new_messages]
                    existing_count = db.query(BareMessage).filter(BareMessage.message_id.in_(message_ids)).count()
                    print(f"  🔄 Messages already in DB: {existing_count}")
                    print(f"  ✨ Messages that would be added: {len(new_messages) - existing_count}")
    
    except Exception as e:
        print(f"❌ Error in message detection test: {e}")
    finally:
        db.close()


async def simulate_crawl_cycle():
    """Simulate a full crawl cycle with detailed logging."""
    print("\n=== SIMULATING FULL CRAWL CYCLE ===")
    
    db = SessionLocal()
    total_new_messages_saved = 0
    
    try:
        async with TelegramService() as tg_service:
            for channel in settings.channel_list:
                print(f"\n🔄 Processing channel: {channel}")
                
                # Get or create channel state
                state = db.query(ChannelState).filter(ChannelState.channel_name == channel).first()
                if not state:
                    print(f"  📝 Creating new channel state for {channel}")
                    state = ChannelState(channel_name=channel, last_message_id=0)
                    db.add(state)
                    db.commit()
                
                print(f"  📍 Current last_message_id: {state.last_message_id}")
                
                # Get new messages
                print(f"  🔍 Fetching messages from Telegram...")
                messages_to_add, newest_id_found = await tg_service.get_new_messages(
                    channel_name=channel,
                    last_known_id=state.last_message_id
                )
                
                print(f"  📨 Raw messages found: {len(messages_to_add)}")
                print(f"  📍 Newest ID found: {newest_id_found}")
                
                if messages_to_add:
                    # Check for existing messages
                    found_ids = [m.message_id for m in messages_to_add]
                    existing_ids_q = db.query(BareMessage.message_id).filter(BareMessage.message_id.in_(found_ids))
                    existing_ids = {res[0] for res in existing_ids_q.all()}
                    
                    print(f"  🔄 Messages already in DB: {len(existing_ids)}")
                    
                    final_messages = [m for m in messages_to_add if m.message_id not in existing_ids]
                    print(f"  ✨ New messages to add: {len(final_messages)}")
                    
                    if final_messages:
                        # Show what would be added
                        for msg in final_messages[:3]:  # Show first 3
                            content_preview = msg.message_text[:50] + "..." if len(msg.message_text) > 50 else msg.message_text
                            print(f"    - ID: {msg.message_id}, Content: '{content_preview}'")
                        
                        if len(final_messages) > 3:
                            print(f"    ... and {len(final_messages) - 3} more")
                        
                        # Actually add messages (uncomment to perform real save)
                        # db.add_all(reversed(final_messages))
                        # total_new_messages_saved += len(final_messages)
                        print(f"  💾 Would save {len(final_messages)} messages (simulation mode)")
                        total_new_messages_saved += len(final_messages)
                
                # Update state
                if newest_id_found > state.last_message_id:
                    print(f"  📍 Would update last_message_id from {state.last_message_id} to {newest_id_found}")
                    # state.last_message_id = newest_id_found
                    # db.commit()
                
                print(f"  ✅ Channel {channel} processing complete")
        
        print(f"\n🎉 Simulation complete! Would have saved {total_new_messages_saved} new messages")
    
    except Exception as e:
        print(f"❌ Error in crawl simulation: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def check_configuration():
    """Check the crawler configuration."""
    print("=== CHECKING CONFIGURATION ===")
    print(f"📋 Channels to crawl: {settings.channel_list}")
    print(f"🏠 Warehouse channel ID: {settings.warehouse_channel_id}")
    print(f"🔑 API ID: {settings.api_id}")
    print(f"🔐 API Hash: {'*' * len(settings.api_hash)}")
    print(f"🗄️  Database URL: {settings.database_url}")


async def main():
    """Run all debugging tests."""
    print("🐛 TELEGRAM CRAWLER DEBUGGER")
    print("=" * 50)
    
    # Configuration check
    check_configuration()
    
    # Database state check
    debug_database_state()
    
    # Channel access check
    await debug_channel_access()
    
    # Message detection test
    await test_message_detection()
    
    # Simulate full crawl
    await simulate_crawl_cycle()
    
    print("\n" + "=" * 50)
    print("🎯 DEBUGGING COMPLETE")
    print("\nRecommendations:")
    print("1. Check if channels are accessible and have new messages")
    print("2. Verify last_message_id values aren't too high")
    print("3. Check for permission issues with channels")
    print("4. Review the simulation results above")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDebugging interrupted by user.")
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
