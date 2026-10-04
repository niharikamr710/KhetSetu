"""
GET /api/history - server-side aggregate scan log.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..database import ScanRecord, get_session

router = APIRouter()


@router.get("/history")
async def get_history(limit: int = 50, db: Session = Depends(get_session)):
    rows = db.query(ScanRecord).order_by(desc(ScanRecord.created_at)).limit(max(1, min(limit, 200))).all()
    return [
        {
            "id": r.id,
            "date": r.created_at.isoformat(),
            "crop": r.crop,
            "disease": r.disease,
            "confidence": r.confidence,
            "is_healthy": r.is_healthy,
            "is_confident": r.is_confident,
            "status": r.status,
            "source": r.source,
            "demo_mode": r.demo_mode,
        }
        for r in rows
    ]