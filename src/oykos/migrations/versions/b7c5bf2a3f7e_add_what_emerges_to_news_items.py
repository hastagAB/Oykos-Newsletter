"""add what_emerges to news_items

Revision ID: b7c5bf2a3f7e
Revises: f415afb31625
Create Date: 2026-08-09 18:36:20.301274
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b7c5bf2a3f7e'
down_revision: Union[str, None] = 'f415afb31625'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default is required: the table is populated, and the column is
    # NOT NULL.
    op.add_column(
        "news_items",
        sa.Column("what_emerges", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("news_items", "what_emerges")
