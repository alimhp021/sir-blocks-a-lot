# remove_duplicates.py
"""
Script to remove duplicate messages from the telegram crawler database.
Duplicates are identified by message_id, keeping the earliest crawled_at entry.
"""

import os
import sys
from sqlalchemy import create_engine, func, and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Add the current directory to Python path to import app modules
sys.path.insert(0, os.getcwd())

try:
    from app.models import BareMessage
    from app.config import settings
    from app.database import SessionLocal
except ImportError as e:
    print(f"Error importing app modules: {e}")
    print("Make sure you're running this script from the project root directory")
    sys.exit(1)


def remove_duplicate_messages():
    """
    Remove duplicate messages from the database.
    Keeps the message with the earliest crawled_at timestamp for each unique message_id.
    """
    db = SessionLocal()
    
    try:
        print("Starting duplicate removal process...")
        
        # Find all message_ids that have duplicates
        duplicate_query = (
            db.query(BareMessage.message_id)
            .group_by(BareMessage.message_id)
            .having(func.count(BareMessage.message_id) > 1)
        )
        
        duplicate_message_ids = [row[0] for row in duplicate_query.all()]
        
        if not duplicate_message_ids:
            print("No duplicate messages found.")
            return 0
        
        print(f"Found {len(duplicate_message_ids)} message_ids with duplicates.")
        
        total_deleted = 0
        
        for message_id in duplicate_message_ids:
            # Get all messages with this message_id, ordered by crawled_at
            messages = (
                db.query(BareMessage)
                .filter(BareMessage.message_id == message_id)
                .order_by(BareMessage.crawled_at.asc())
                .all()
            )
            
            # Keep the first one (earliest crawled_at), delete the rest
            messages_to_delete = messages[1:]  # Skip the first message
            
            for msg in messages_to_delete:
                print(f"Deleting duplicate: ID={msg.id}, message_id={msg.message_id}, "
                      f"channel={msg.channel_name}, crawled_at={msg.crawled_at}")
                db.delete(msg)
                total_deleted += 1
        
        # Commit all deletions
        db.commit()
        print(f"Successfully deleted {total_deleted} duplicate messages.")
        
        return total_deleted
        
    except Exception as e:
        print(f"Error during duplicate removal: {e}")
        db.rollback()
        return 0
    finally:
        db.close()


def get_database_stats():
    """Get some basic statistics about the database."""
    db = SessionLocal()
    
    try:
        # Total messages
        total_messages = db.query(BareMessage).count()
        
        # Messages per channel
        channel_stats = (
            db.query(
                BareMessage.channel_name,
                func.count(BareMessage.id).label('count')
            )
            .group_by(BareMessage.channel_name)
            .order_by(func.count(BareMessage.id).desc())
            .all()
        )
        
        print(f"\n=== Database Statistics ===")
        print(f"Total messages: {total_messages}")
        print(f"Messages by channel:")
        for channel, count in channel_stats:
            print(f"  - {channel}: {count} messages")
        
        # Check for remaining duplicates
        remaining_duplicates = (
            db.query(BareMessage.message_id)
            .group_by(BareMessage.message_id)
            .having(func.count(BareMessage.message_id) > 1)
            .count()
        )
        
        print(f"Remaining duplicate message_ids: {remaining_duplicates}")
        
    except Exception as e:
        print(f"Error getting database stats: {e}")
    finally:
        db.close()


def main():
    """Main function to run the duplicate removal process."""
    print("=== Telegram Crawler - Duplicate Message Remover ===\n")
    
    # Show initial stats
    print("Initial database state:")
    get_database_stats()
    
    print("\n" + "="*50)
    
    # Remove duplicates
    deleted_count = remove_duplicate_messages()
    
    print("\n" + "="*50)
    
    # Show final stats
    print("Final database state:")
    get_database_stats()
    
    print(f"\n=== Process Complete ===")
    print(f"Total duplicates removed: {deleted_count}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)