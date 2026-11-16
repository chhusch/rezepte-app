"""login failures for throttling

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

IP_LEN = 45


def upgrade() -> None:
	op.create_table(
		"login_failures",
		sa.Column("id", sa.Integer, primary_key=True),
		sa.Column("ip", sa.String(IP_LEN), nullable=False),
		sa.Column("at", sa.DateTime(timezone=True), nullable=False),
	)
	op.create_index("ix_login_failures_ip", "login_failures", ["ip"])


def downgrade() -> None:
	op.drop_index("ix_login_failures_ip", table_name="login_failures")
	op.drop_table("login_failures")
