# app/models.py
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Text, func
from .database import Base

class BareMessage(Base):
    __tablename__ = "bare_messages"
    id = Column(Integer, primary_key=True)
    channel_name = Column(String, index=True)
    message_id = Column(BigInteger, unique=True)
    message_text = Column(Text)
    message_timestamp = Column(DateTime)
    crawled_at = Column(DateTime, default=func.now())

class ChannelState(Base):
    __tablename__ = "channel_states"
    channel_name = Column(String, primary_key=True)
    last_message_id = Column(BigInteger, default=0)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
