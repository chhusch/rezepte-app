"""meal plan: days and entries

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

NAME_LEN = 200
COLOR_LEN = 20

MEAL_SLOT = sa.Enum("BREAKFAST", "LUNCH", "ZVIERI", "DINNER",
		    name="meal_slot")


def upgrade() -> None:
	op.create_table(
		"plan_days",
		sa.Column("day", sa.Date, primary_key=True),
		sa.Column("note", sa.Text, nullable=False),
		sa.Column("color", sa.String(COLOR_LEN)),
		sa.Column("breakfast", sa.Boolean, nullable=False),
		sa.Column("zvieri", sa.Boolean, nullable=False),
	)
	op.create_table(
		"plan_entries",
		sa.Column("id", sa.Integer, primary_key=True),
		sa.Column("day", sa.Date, nullable=False),
		sa.Column("slot", MEAL_SLOT, nullable=False),
		sa.Column("position", sa.Integer, nullable=False),
		sa.Column("recipe_id", sa.Integer,
			  sa.ForeignKey("recipes.id", ondelete="SET NULL")),
		sa.Column("text", sa.String(NAME_LEN), nullable=False),
		sa.Column("servings", sa.Integer),
	)
	op.create_index("ix_plan_entries_day", "plan_entries", ["day"])
	op.create_index("ix_plan_entries_recipe_id", "plan_entries",
			["recipe_id"])


def downgrade() -> None:
	op.drop_index("ix_plan_entries_recipe_id", "plan_entries")
	op.drop_index("ix_plan_entries_day", "plan_entries")
	op.drop_table("plan_entries")
	op.drop_table("plan_days")
	MEAL_SLOT.drop(op.get_bind(), checkfirst=True)
