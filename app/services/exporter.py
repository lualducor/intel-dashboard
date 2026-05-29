import csv as _csv
import io
import json

from sqlalchemy import and_, exists, select
from sqlalchemy.orm import Session

from ..models import Article, ArticleUse


def _record(article: Article, *, for_content: bool = False) -> dict:
    data = {
        "id": article.id,
        "title": article.title,
        "url": article.original_url,
        "source": article.source.name,
        "topic": article.topic,
        "category": article.category,
        "status": article.status,
        "final_score": round(article.final_score, 4),
        "score_explanation": article.score_explanation,
    }
    if for_content:
        data["uses"] = [
            {
                "use_type": use.use_type,
                "status": use.status,
                "content_angle": use.content_angle,
            }
            for use in article.uses
        ]
    return data


def export_as(
    db: Session,
    fmt: str,
    *,
    status_in: list[str] | None = None,
    for_content: bool = False,
) -> str:
    stmt = select(Article)
    if for_content:
        stmt = stmt.where(exists().where(ArticleUse.article_id == Article.id))
    elif status_in:
        stmt = stmt.where(and_(Article.status.in_(status_in)))
    stmt = stmt.order_by(Article.final_score.desc())

    articles = db.scalars(stmt).all()
    records = [_record(article, for_content=for_content) for article in articles]

    if fmt == "md":
        lines = []
        for record in records:
            lines.append(
                f"- [{record['title']}]({record['url']}) — "
                f"{record['final_score']:.2f} · {record['source']}"
            )
            if for_content:
                for use in record["uses"]:
                    lines.append(
                        f"  - {use['use_type']}: {use['status']} · "
                        f"{use['content_angle'] or ''}"
                    )
        return "\n".join(lines)

    if fmt == "csv":
        output = io.StringIO()
        writer = _csv.writer(output)
        writer.writerow(
            ["id", "title", "url", "source", "topic", "category", "status", "final_score"]
        )
        for record in records:
            writer.writerow(
                [
                    record["id"],
                    record["title"],
                    record["url"],
                    record["source"],
                    record["topic"],
                    record["category"],
                    record["status"],
                    record["final_score"],
                ]
            )
        return output.getvalue()

    if fmt == "json":
        return json.dumps(records, ensure_ascii=False, indent=2)

    raise ValueError
