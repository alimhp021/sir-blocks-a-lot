# test_crawl_verbose.py
"""
Test the actual crawl endpoint with verbose logging.
This helps debug what's happening during the actual API call.
"""

import os
import sys
import asyncio
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.getcwd())

try:
    from app.database import SessionLocal
    from app.controllers.crawler_controller import run_crawl_cycle
except ImportError as e:
    print(f"Error importing app modules: {e}")
    sys.exit(1)


async def test_crawl_with_logging():
    """Test the actual crawl function with detailed logging."""
    print(f"🕐 Starting crawl test at {datetime.now()}")
    print("=" * 50)
    
    db = SessionLocal()
    try:
        print("📡 Calling run_crawl_cycle...")
        new_messages_count = await run_crawl_cycle(db)
        print(f"✅ Crawl completed successfully!")
        print(f"📊 New messages found: {new_messages_count}")
        
        if new_messages_count == 0:
            print("\n⚠️  No new messages were found. This could mean:")
            print("  1. No new messages in the channels")
            print("  2. All messages are already in the database")
            print("  3. Channel access issues")
            print("  4. Last message ID is set too high")
            print("\nRun debug_crawler.py for detailed analysis")
        
    except Exception as e:
        print(f"❌ Error during crawl: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_crawl_with_logging())
