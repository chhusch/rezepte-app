"""freezer items

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

NAME_LEN = 200
UNIT_LEN = 50


def upgrade() -> None:
	op.create_table(
		"freezer_items",
		sa.Column("id", sa.Integer, primary_key=True),
		sa.Column("name", sa.String(NAME_LEN), nullable=False),
		sa.Column("amount", sa.Numeric(10, 3)),
		sa.Column("unit", sa.String(UNIT_LEN), nullable=False),
		sa.Column("note", sa.String(NAME_LEN), nullable=False),
		sa.Column("frozen_on", sa.Date, nullable=False),
	)


def downgrade() -> None:
	op.drop_table("freezer_items")
