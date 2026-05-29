from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..services import horoscope as horoscope_service
from ..services import queues
from ..templating import templates

router = APIRouter(prefix="/horoscope")


@router.post("/refresh")
async def refresh(request: Request, db: Session = Depends(get_db)):
    result = await horoscope_service.refresh_horoscope()
    return templates.TemplateResponse(
        request,
        "_horoscope.html",
        {
            "request": request,
            "horoscope": queues.horoscope_today(db),
            "horoscope_error": None if result.get("ok") else result.get("error"),
        },
    )
