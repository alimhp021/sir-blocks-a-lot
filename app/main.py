# app/main.py
from fastapi import FastAPI
from .database import engine, Base
from .routers import crawler_router

# Create all database tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Refactored Telegram Crawler",
    version="5.0.0"
)

app.include_router(crawler_router.router, tags=["Crawler"])

@app.get("/")
def read_root():
    return {"message": "Crawler is running. Use the /crawl endpoint."}
