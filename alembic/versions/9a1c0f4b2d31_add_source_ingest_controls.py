"""add source ingest controls

Revision ID: 9a1c0f4b2d31
Revises: fdc4204ffb06
Create Date: 2026-07-12 23:55:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9a1c0f4b2d31"
down_revision: Union[str, Sequence[str], None] = "fdc4204ffb06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column("max_items_per_fetch", sa.Integer(), nullable=False, server_default="50"),
    )
    op.add_column(
        "sources",
        sa.Column("max_item_age_days", sa.Integer(), nullable=False, server_default="90"),
    )
    op.add_column("sources", sa.Column("feed_etag", sa.String(), nullable=True))
    op.add_column("sources", sa.Column("feed_last_modified", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "feed_last_modified")
    op.drop_column("sources", "feed_etag")
    op.drop_column("sources", "max_item_age_days")
    op.drop_column("sources", "max_items_per_fetch")
