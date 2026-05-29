from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..services import briefing
from ..templating import templates

router = APIRouter()


@router.post("/briefing/regenerate")
def regenerate(request: Request, db: Session = Depends(get_db)):
    b = briefing.generate_briefing(db, get_settings())
    return templates.TemplateResponse(request, "_briefing.html", {"briefing": b})
