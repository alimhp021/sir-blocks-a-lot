# app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from app.config import settings # <-- CORRECTED IMPORT

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency to get a DB session in API routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
