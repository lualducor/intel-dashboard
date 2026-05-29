from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from ..config import get_settings ; from ..db import get_db ; from ..services import search as search_service ; from ..templating import templates

router = APIRouter()

@router.get("/search")
def search_page(request: Request, q: str = "", db: Session = Depends(get_db)):
    results = search_service.search_articles(db, q) if q.strip() else []
    return templates.TemplateResponse(request, "search.html",
        {"q": q, "results": results, "settings": get_settings()})
