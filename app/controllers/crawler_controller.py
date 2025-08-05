# app/controllers/crawler_controller.py
from sqlalchemy.orm import Session
from ..config import settings
from ..models import ChannelState, BareMessage
from ..services.telegram_service import TelegramService

async def run_crawl_cycle(db: Session):
    total_new_messages = 0
    
    async with TelegramService() as tg_service:
        for channel in settings.channel_list:
            # Get state from DB
            state = db.query(ChannelState).filter(ChannelState.channel_name == channel).first()
            if not state:
                state = ChannelState(channel_name=channel, last_message_id=0)
                db.add(state)
                db.commit()

            # Get new messages from Telegram
            messages_to_add, newest_id_found = await tg_service.get_new_messages(
                channel_name=channel,
                last_known_id=state.last_message_id
            )
            
            # Save new messages to DB
            if messages_to_add:
                # Check for duplicates before adding
                existing_ids = {
                    res[0] for res in db.query(BareMessage.message_id).filter(
                        BareMessage.message_id.in_([m.message_id for m in messages_to_add])
                    ).all()
                }
                
                final_messages = [m for m in messages_to_add if m.message_id not in existing_ids]

                if final_messages:
                    db.add_all(reversed(final_messages))
                    total_new_messages += len(final_messages)

            # Update state in DB
            state.last_message_id = newest_id_found
            db.commit()
            
    return total_new_messages
