"""household: user colors, invites, authors of notes and cook log

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

COLOR_LEN = 20
FIRST_COLOR = "sea"
AUTHORED = ("notes", "cook_log")


def _fk_name(table):
	return "fk_%s_user_id" % table


def _add_author(table):
	with op.batch_alter_table(table) as b:
		b.add_column(sa.Column("user_id", sa.Integer))
		b.create_foreign_key(_fk_name(table), "users", ["user_id"],
				     ["id"], ondelete="SET NULL")


def _assign_single_user():
	"""Before households there was one user: everything is theirs."""
	conn = op.get_bind()
	ids = conn.execute(sa.text("SELECT id FROM users")).scalars().all()
	if len(ids) != 1:
		return
	for table in AUTHORED:
		conn.execute(sa.text("UPDATE %s SET user_id = :id" % table),
			     {"id": ids[0]})


def upgrade() -> None:
	with op.batch_alter_table("users") as b:
		b.add_column(sa.Column("color", sa.String(COLOR_LEN),
				       nullable=False,
				       server_default=FIRST_COLOR))
	with op.batch_alter_table("users") as b:
		b.alter_column("color", server_default=None)
	for table in AUTHORED:
		_add_author(table)
	_assign_single_user()

	op.create_table(
		"invites",
		sa.Column("id", sa.Integer, primary_key=True),
		sa.Column("token_hash", sa.String(128), nullable=False,
			  unique=True),
		sa.Column("created_by", sa.Integer,
			  sa.ForeignKey("users.id", ondelete="SET NULL")),
		sa.Column("created_at", sa.DateTime(timezone=True),
			  server_default=sa.func.now(), nullable=False),
		sa.Column("expires_at", sa.DateTime(timezone=True),
			  nullable=False),
	)


def downgrade() -> None:
	op.drop_table("invites")
	for table in AUTHORED:
		with op.batch_alter_table(table) as b:
			b.drop_constraint(_fk_name(table), type_="foreignkey")
			b.drop_column("user_id")
	with op.batch_alter_table("users") as b:
		b.drop_column("color")
