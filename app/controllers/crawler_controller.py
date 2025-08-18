# app/controllers/crawler_controller.py
from sqlalchemy.orm import Session
from app.config import settings
from app.models import ChannelState, BareMessage
from app.services.telegram_service import TelegramService

async def run_crawl_cycle(db: Session):
    total_new_messages_saved = 0

    async with TelegramService() as tg_service:
        for channel in settings.channel_list:
            state = db.query(ChannelState).filter(ChannelState.channel_name == channel).first()
            if not state:
                state = ChannelState(channel_name=channel, last_message_id=0)
                db.add(state)
                db.commit()

            messages_to_add, newest_id_found = await tg_service.get_new_messages(
                channel_name=channel,
                last_known_id=state.last_message_id
            )

            if messages_to_add:
                found_ids = [m.message_id for m in messages_to_add]
                existing_ids_q = db.query(BareMessage.message_id).filter(BareMessage.message_id.in_(found_ids))
                existing_ids = {res[0] for res in existing_ids_q.all()}

                final_messages = [m for m in messages_to_add if m.message_id not in existing_ids]

                if final_messages:
                    # --- UPDATED LOGIC WITH HYPERLINKS ---
                    # Forward messages before saving them to the DB
                    for msg in reversed(final_messages): # Send oldest first
                        warehouse_text = f"📢 **New Message from: {msg.channel_name}**\n\n{msg.message_text}"
                        
                        # Pass channel name and message ID to create hyperlink
                        await tg_service.send_to_warehouse(
                            message_text=warehouse_text,
                            channel_name=msg.channel_name,
                            message_id=msg.message_id
                        )
                    # --- END OF UPDATED LOGIC ---

                    db.add_all(reversed(final_messages))
                    total_new_messages_saved += len(final_messages)

            if newest_id_found > state.last_message_id:
                state.last_message_id = newest_id_found
                db.commit()

    return total_new_messages_saved