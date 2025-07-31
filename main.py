# main.py
# Import necessary libraries
import asyncio
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
import logging
import os
from pathlib import Path
import re
from datetime import datetime

# --- Database Imports ---
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

# --- Library Fallback: Try to import kurigram, fallback to pyrogram ---
try:
    from kurigram import Client
    from kurigram.errors import FloodWait, UserDeactivated, AuthKeyUnregistered
    print("Successfully imported kurigram.")
except ImportError:
    print("Failed to import kurigram. Falling back to pyrogram.")
    try:
        from pyrogram import Client
        from pyrogram.errors import FloodWait, UserDeactivated, AuthKeyUnregistered
        print("Successfully imported pyrogram.")
    except ImportError:
        print("Error: Neither kurigram nor pyrogram are installed.")
        exit()

try:
    from v2ray2proxy import V2RayProxy
    print("Successfully imported v2ray2proxy.")
except ImportError:
    print("Warning: v2ray2proxy is not installed.")
    V2RayProxy = None

# --- Database Configuration ---
# For a real application, use environment variables for these!
# Make sure you have updated this with your actual user, password, and db name
DATABASE_URL = "postgresql://myuser:alimhp021isme@localhost/telegram_data"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Database Model ---
class Price(Base):
    __tablename__ = "prices"
    id = Column(Integer, primary_key=True, index=True)
    bitcoin_price = Column(Float, nullable=False)
    ethereum_price = Column(Float, nullable=False)
    message_timestamp = Column(DateTime, nullable=False, index=True)
    crawled_at = Column(DateTime, default=datetime.utcnow)

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Telegram Channel Crawler",
    description="An API to crawl, parse, and store Telegram channel data in a PostgreSQL database.",
    version="2.1.0",
)

# Create the database tables on startup
@app.on_event("startup")
def on_startup():
    try:
        Base.metadata.create_all(bind=engine)
        logging.info("Database tables created successfully.")
    except Exception as e:
        logging.error(f"Error creating database tables: {e}")
        # This will prevent the app from starting if the DB is not configured correctly
        raise

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


# --- Pydantic Models ---
class ProxyConfig(BaseModel):
    scheme: str = Field(..., description="Proxy scheme (e.g., 'socks5', 'http', 'vless', 'mtproto').")
    hostname: Optional[str] = Field(None)
    port: Optional[int] = Field(None)
    secret: Optional[str] = Field(None)
    vless_url: Optional[str] = Field(None)

class CrawlRequest(BaseModel):
    api_id: int
    api_hash: str
    channel_name: str
    proxy: Optional[ProxyConfig] = None
    limit: int = Field(1, description="Number of messages to process. For prices, 1 is enough.")

class Message(BaseModel):
    id: int
    text: Optional[str] = None
    date: str
    author: Optional[str] = None
    views: Optional[int] = None
    media_type: Optional[str] = None

class CrawlResponse(BaseModel):
    channel_name: str
    message_processed: Message
    data_saved: dict

class PriceResponse(BaseModel):
    id: int
    bitcoin_price: float
    ethereum_price: float
    message_timestamp: datetime
    crawled_at: datetime
    # FIX: Pydantic V2 uses from_attributes instead of orm_mode
    model_config = ConfigDict(from_attributes=True)

# --- Dependency to get DB session ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Helper Functions ---
def parse_price(text: str) -> Optional[float]:
    """Robustly parses price strings with different thousand/decimal separators."""
    if not text:
        return None
    
    last_dot = text.rfind('.')
    last_comma = text.rfind(',')

    # Assume the last separator is the decimal one
    if last_comma > last_dot:
        # European style: 1.234,56 -> 1234.56
        text = text.replace('.', '').replace(',', '.')
    elif last_dot > last_comma:
        # US style: 1,234.56 -> 1234.56
        text = text.replace(',', '')
    
    try:
        return float(text)
    except (ValueError, TypeError):
        logging.warning(f"Could not parse '{text}' as a float.")
        return None

async def start_vless_proxy(vless_url: str):
    if not V2RayProxy:
        raise RuntimeError("v2ray2proxy is not installed.")
    logging.info("Starting VLESS to SOCKS5 proxy...")
    proxy = V2RayProxy(vless_url)
    await asyncio.sleep(5)
    logging.info(f"VLESS proxy running at: {proxy.socks5_proxy_url}")
    return proxy, proxy.socks5_proxy_url

def parse_mtproto_proxy(proxy_config: ProxyConfig):
    return {
        "scheme": "socks5", 
        "hostname": proxy_config.hostname,
        "port": proxy_config.port,
        "username": "",
        "password": proxy_config.secret
    }

# --- API Endpoints ---
@app.post("/crawl_and_save", response_model=CrawlResponse)
async def crawl_and_save(request: CrawlRequest, db: Session = Depends(get_db)):
    home_dir = Path.home()
    session_dir = home_dir / ".telegram_crawler_sessions"
    session_dir.mkdir(exist_ok=True)
    session_name = str(session_dir / request.channel_name)

    proxy_dict = None
    vless_proxy_instance = None
    client = None

    try:
        # --- FIX: Restore detailed proxy handling ---
        if request.proxy:
            if request.proxy.scheme == 'vless' and request.proxy.vless_url:
                vless_proxy_instance, socks5_url = await start_vless_proxy(request.proxy.vless_url)
                parts = socks5_url.replace("socks5://", "").split(":")
                proxy_dict = {"scheme": "socks5", "hostname": parts[0], "port": int(parts[1])}
            elif request.proxy.scheme == 'mtproto':
                proxy_dict = parse_mtproto_proxy(request.proxy)
            elif request.proxy.scheme in ['socks5', 'socks4', 'http']:
                proxy_dict = request.proxy.dict(exclude_none=True)

        client = Client(name=session_name, api_id=request.api_id, api_hash=request.api_hash, proxy=proxy_dict)
        
        logging.info(f"Connecting with session: {session_name}")
        await client.start()

        latest_message = None
        async for message in client.get_chat_history(request.channel_name, limit=1):
            latest_message = message
            break

        if not latest_message or not latest_message.text:
            raise HTTPException(status_code=404, detail="No text message found to process.")

        btc_match = re.search(r"Bitcoin #BTC\s*:\s*\$([\d.,]+)", latest_message.text)
        eth_match = re.search(r"Ethereum #ETH\s*:\s*\$([\d.,]+)", latest_message.text)

        btc_price = parse_price(btc_match.group(1)) if btc_match else None
        eth_price = parse_price(eth_match.group(1)) if eth_match else None

        if btc_price is None or eth_price is None:
            raise HTTPException(status_code=400, detail="Could not parse Bitcoin or Ethereum price from the message.")
        
        db_price_entry = Price(
            bitcoin_price=btc_price,
            ethereum_price=eth_price,
            message_timestamp=latest_message.date
        )
        db.add(db_price_entry)
        db.commit()
        db.refresh(db_price_entry)
        
        logging.info(f"Saved prices to DB: BTC=${btc_price}, ETH=${eth_price}")

        message_data = Message(
            id=latest_message.id,
            text=latest_message.text,
            date=str(latest_message.date),
            views=latest_message.views,
            media_type="text"
        )
        
        return CrawlResponse(
            channel_name=request.channel_name,
            message_processed=message_data,
            data_saved={"btc_price": btc_price, "eth_price": eth_price, "timestamp": latest_message.date}
        )

    except Exception as e:
        # Log the full traceback for better debugging
        logging.error(f"An unexpected error occurred in crawl_and_save", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # --- FIX: Add defensive checks before stopping client/proxy ---
        if client and client.is_connected:
            await client.stop()
        if vless_proxy_instance:
            vless_proxy_instance.stop()
            logging.info("VLESS proxy stopped.")

@app.get("/prices", response_model=List[PriceResponse])
def get_prices(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    """Retrieve the latest price entries from the database."""
    prices = db.query(Price).order_by(Price.message_timestamp.desc()).offset(skip).limit(limit).all()
    return prices

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Welcome to the Telegram Crawler API. See /docs for usage."}
