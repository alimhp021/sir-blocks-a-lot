# app/routers/crawler_router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import schemas # <-- CORRECTED IMPORT
from app.database import get_db # <-- CORRECTED IMPORT
from app.controllers import crawler_controller # <-- CORRECTED IMPORT
from app.config import settings # <-- CORRECTED IMPORT

router = APIRouter()

@router.post("/crawl", response_model=schemas.CrawlResponse)
async def crawl_channels(db: Session = Depends(get_db)):
    try:
        new_messages_count = await crawler_controller.run_crawl_cycle(db)
        return schemas.CrawlResponse(
            status="success",
            new_messages_found=new_messages_count,
            channels_crawled=settings.channel_list
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
