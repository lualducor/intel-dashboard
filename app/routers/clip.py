from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from ..config import get_settings
from ..db import get_db
from ..services import clipper
from ..templating import templates

router = APIRouter()


@router.get("/clip")
def clip_form(request: Request):
    return templates.TemplateResponse(request, "clip.html", {})


@router.post("/clip")
def clip_submit(
    request: Request,
    url: str = Form(...),
    use_type: str | None = Form(None),
    content_angle: str | None = Form(None),
    db: Session = Depends(get_db),
):
    clipper.clip_url(
        db,
        url,
        settings=get_settings(),
        use_type=(use_type or None),
        content_angle=(content_angle or None),
    )
    return RedirectResponse(url="/saved", status_code=303)
