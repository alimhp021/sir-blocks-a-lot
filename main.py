# main.py
import asyncio
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
import logging
from datetime import datetime

# --- Database Imports ---
from sqlalchemy import create_engine, Column, Integer, String, BigInteger, DateTime, Text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

# --- Library Imports ---
try:
    from pyrogram import Client
    from pyrogram.errors import FloodWait
    print("Using pyrogram.")
except ImportError:
    print("Error: Pyrogram is not installed. Please run 'pip install pyrogram'.")
    exit()

# --- v2ray2proxy Import ---
try:
    from v2ray2proxy import V2RayProxy
    print("Successfully imported v2ray2proxy.")
except ImportError:
    print("Warning: v2ray2proxy is not installed. VLESS proxy functionality will be disabled.")
    V2RayProxy = None


# --- Database Configuration ---
# Make sure this matches your local PostgreSQL setup
DATABASE_URL = "postgresql://myuser:mypassword@localhost/telegram_data"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- NEW Database Models ---
class BareMessage(Base):
    __tablename__ = "bare_messages"
    id = Column(Integer, primary_key=True)
    channel_name = Column(String, index=True)
    message_id = Column(BigInteger, unique=True)
    message_text = Column(Text)
    message_timestamp = Column(DateTime)
    crawled_at = Column(DateTime, default=datetime.utcnow)

class ChannelState(Base):
    __tablename__ = "channel_states"
    channel_name = Column(String, primary_key=True)
    last_message_id = Column(BigInteger, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Decoupled Telegram Crawler",
    description="An API that crawls multiple channels for new messages and saves the raw text to a database.",
    version="4.1.0",
)

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    logging.info("Database tables verified.")

# --- Pydantic Models ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class ProxyConfig(BaseModel):
    scheme: str
    hostname: Optional[str] = None
    port: Optional[int] = None
    vless_url: Optional[str] = None

class CrawlRequest(BaseModel):
    api_id: int
    api_hash: str
    channel_names: List[str] = Field(..., description="A list of channel usernames to crawl.")
    proxy: Optional[ProxyConfig] = None

class CrawlResponse(BaseModel):
    status: str
    new_messages_found: int
    channels_crawled: List[str]

# --- Dependency to get DB session ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Helper to start VLESS proxy ---
async def start_vless_proxy(vless_url: str):
    if not V2RayProxy:
        raise RuntimeError("v2ray2proxy is not installed, cannot start VLESS proxy.")
    
    logging.info("Starting VLESS to SOCKS5 proxy...")
    proxy_instance = V2RayProxy(vless_url)
    await asyncio.sleep(5) # Give it a moment to initialize
    logging.info(f"VLESS proxy should be running at: {proxy_instance.socks5_proxy_url}")
    
    # Parse the local SOCKS5 URL for Pyrogram
    parts = proxy_instance.socks5_proxy_url.replace("socks5://", "").split(":")
    proxy_dict = {"scheme": "socks5", "hostname": parts[0], "port": int(parts[1])}
    
    return proxy_instance, proxy_dict

# --- Main API Endpoint ---
@app.post("/crawl_new_messages", response_model=CrawlResponse)
async def crawl_new_messages(request: CrawlRequest, db: Session = Depends(get_db)):
    session_name = "telegram_crawler_session" # Generic session name
    proxy_dict = None
    vless_proxy_instance = None
    client = None

    try:
        # --- CORRECTED PROXY LOGIC ---
        if request.proxy:
            if request.proxy.scheme.lower() == 'vless' and request.proxy.vless_url:
                if not V2RayProxy:
                    raise HTTPException(status_code=501, detail="v2ray2proxy is not installed on the server.")
                # Start the VLESS proxy and get the resulting SOCKS5 dict
                vless_proxy_instance, proxy_dict = await start_vless_proxy(request.proxy.vless_url)
            elif request.proxy.scheme.lower() in ['socks5', 'socks4', 'http']:
                # Use other proxy types directly
                proxy_dict = request.proxy.dict(exclude_none=True)

        client = Client(name=session_name, api_id=request.api_id, api_hash=request.api_hash, proxy=proxy_dict)
        
        total_new_messages = 0
        await client.start()

        for channel in request.channel_names:
            state = db.query(ChannelState).filter(ChannelState.channel_name == channel).first()
            if not state:
                state = ChannelState(channel_name=channel, last_message_id=0)
                db.add(state)
                db.commit()
            
            last_known_id = state.last_message_id
            newest_id_found = last_known_id
            
            messages_to_add = []
            async for message in client.get_chat_history(channel, limit=100):
                if message.id > last_known_id:
                    if message.text:
                        exists = db.query(BareMessage).filter(BareMessage.message_id == message.id).first()
                        if not exists:
                            messages_to_add.append(
                                BareMessage(
                                    channel_name=channel,
                                    message_id=message.id,
                                    message_text=message.text,
                                    message_timestamp=message.date
                                )
                            )
                    if message.id > newest_id_found:
                        newest_id_found = message.id
                else:
                    break
            
            if messages_to_add:
                db.add_all(reversed(messages_to_add))
                total_new_messages += len(messages_to_add)
            
            state.last_message_id = newest_id_found
            db.commit()

    except Exception as e:
        logging.error("An unexpected error occurred", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if client and client.is_connected:
            await client.stop()
        # Ensure the VLESS proxy instance is stopped if it was created
        if vless_proxy_instance:
            vless_proxy_instance.stop()
            logging.info("VLESS proxy stopped.")

    return CrawlResponse(
        status="success",
        new_messages_found=total_new_messages,
        channels_crawled=request.channel_names
    )
