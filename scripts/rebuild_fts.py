from sqlalchemy import text ; from app.db import SessionLocal

def rebuild(*, session_factory=SessionLocal) -> None:
    db = session_factory()
    try:
        db.execute(text("INSERT INTO articles_fts(articles_fts) VALUES('rebuild')")); db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    rebuild(); print("FTS index rebuilt")
