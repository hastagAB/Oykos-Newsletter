"""add implication_kind

Revision ID: 9b50a0fc750b
Revises: d053db13cc38
Create Date: 2026-08-08 00:20:42.390493
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '9b50a0fc750b'
down_revision: Union[str, None] = 'd053db13cc38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default is required: SQLite refuses ADD COLUMN NOT NULL without one
    # on a table that already has rows, and production has 183.
    op.add_column(
        'news_items',
        sa.Column(
            'implication_kind',
            sa.String(length=30),
            nullable=False,
            server_default='worth_attention',
        ),
    )


def downgrade() -> None:
    op.drop_column('news_items', 'implication_kind')
