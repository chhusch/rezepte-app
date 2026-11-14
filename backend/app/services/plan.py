"""Meal plan: entries per day and meal, day notes, ingredient totals.

An entry holds a recipe or a free text. Its servings scale the
recipe's ingredients against the own version's servings; without
either number the amounts stay as written.
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import PlanDay, PlanEntry, Recipe, RecipeVersion
from app.schemas import PlanDayIn, PlanEntryIn
from app.services import pantry, shopping

MAX_DAYS = 14

LOAD_RECIPE = selectinload(PlanEntry.recipe).selectinload(
	Recipe.versions).selectinload(RecipeVersion.ingredients)


class RecipeMissing(Exception):
	pass


def day_range(start: date, days: int) -> list[date]:
	return [start + timedelta(days=i) for i in range(days)]


def entry_title(entry: PlanEntry) -> str:
	if entry.recipe is not None and entry.recipe.own is not None:
		return entry.recipe.own.title
	return entry.text


def entry_out(entry: PlanEntry) -> dict:
	return {
		"id": entry.id,
		"day": entry.day,
		"slot": entry.slot,
		"position": entry.position,
		"recipe_id": entry.recipe_id,
		"title": entry_title(entry),
		"servings": entry.servings,
	}


def entries_between(db: Session, start: date, days: int) -> list[PlanEntry]:
	end = start + timedelta(days=days)
	stmt = (select(PlanEntry)
		.where(PlanEntry.day >= start, PlanEntry.day < end)
		.options(LOAD_RECIPE)
		.order_by(PlanEntry.day, PlanEntry.position, PlanEntry.id))
	return list(db.scalars(stmt))


def days_between(db: Session, start: date, days: int) -> dict:
	end = start + timedelta(days=days)
	stmt = select(PlanDay).where(PlanDay.day >= start, PlanDay.day < end)
	return {d.day: d for d in db.scalars(stmt)}


def day_out(day: date, row: PlanDay | None, entries: list) -> dict:
	return {
		"day": day,
		"note": row.note if row else "",
		"color": row.color if row else None,
		"breakfast": row.breakfast if row else False,
		"zvieri": row.zvieri if row else False,
		"entries": entries,
	}


def get_plan(db: Session, start: date, days: int) -> list[dict]:
	rows = days_between(db, start, days)
	by_day: dict[date, list] = {d: [] for d in day_range(start, days)}
	for e in entries_between(db, start, days):
		by_day[e.day].append(entry_out(e))
	return [day_out(d, rows.get(d), by_day[d]) for d in by_day]


def recipe_title(db: Session, recipe_id: int | None) -> str | None:
	"""Own title of the recipe; raises RecipeMissing if it is gone."""
	if recipe_id is None:
		return None
	recipe = db.get(Recipe, recipe_id)
	if recipe is None or recipe.own is None:
		raise RecipeMissing(recipe_id)
	return recipe.own.title


def next_position(db: Session, data: PlanEntryIn) -> int:
	stmt = select(func.max(PlanEntry.position)).where(
		PlanEntry.day == data.day, PlanEntry.slot == data.slot)
	top = db.scalar(stmt)
	return 0 if top is None else top + 1


def apply_entry(db: Session, entry: PlanEntry, data: PlanEntryIn) -> None:
	title = recipe_title(db, data.recipe_id)
	if entry.id is None or (entry.day, entry.slot) != (data.day,
							     data.slot):
		entry.position = next_position(db, data)
	entry.day = data.day
	entry.slot = data.slot
	entry.recipe_id = data.recipe_id
	entry.text = data.text or title or ""
	entry.servings = data.servings


def load_entry(db: Session, entry_id: int) -> PlanEntry | None:
	stmt = (select(PlanEntry).where(PlanEntry.id == entry_id)
		.options(LOAD_RECIPE)
		.execution_options(populate_existing=True))
	return db.scalars(stmt).first()


def add_entry(db: Session, data: PlanEntryIn) -> dict:
	entry = PlanEntry()
	apply_entry(db, entry, data)
	db.add(entry)
	db.commit()
	return entry_out(load_entry(db, entry.id))


def update_entry(db: Session, entry_id: int,
		 data: PlanEntryIn) -> dict | None:
	entry = db.get(PlanEntry, entry_id)
	if entry is None:
		return None
	apply_entry(db, entry, data)
	db.commit()
	return entry_out(load_entry(db, entry_id))


def delete_entry(db: Session, entry_id: int) -> bool:
	entry = db.get(PlanEntry, entry_id)
	if entry is None:
		return False
	db.delete(entry)
	db.commit()
	return True


def set_day(db: Session, day: date, data: PlanDayIn) -> dict:
	row = db.get(PlanDay, day)
	if row is None:
		row = PlanDay(day=day)
		db.add(row)
	row.note = data.note
	row.color = data.color
	row.breakfast = data.breakfast
	row.zvieri = data.zvieri
	db.commit()
	return day_out(day, row, [entry_out(e) for e in
				   entries_between(db, day, 1)])


def factor_of(entry: PlanEntry, version: RecipeVersion) -> Decimal:
	if entry.servings and version.servings:
		return Decimal(entry.servings) / Decimal(version.servings)
	return Decimal(1)


def add_line(lines: dict, ing, factor: Decimal, title: str) -> None:
	amount = shopping.scale(ing.amount, factor)
	key = shopping.key_of(ing.name, ing.unit)
	line = lines.get(key)
	if line is None:
		lines[key] = {"name": ing.name, "unit": ing.unit,
			      "amount": amount, "note": ing.note,
			      "recipes": [title]}
		return
	if line["amount"] is None:
		line["amount"] = amount
	elif amount is not None:
		line["amount"] += amount
	line["note"] = shopping.merge_note(line["note"], ing.note)
	if title not in line["recipes"]:
		line["recipes"].append(title)


def ingredients(db: Session, start: date, days: int) -> list[dict]:
	"""Merged ingredients of all planned recipes in the range."""
	lines: dict = {}
	for e in entries_between(db, start, days):
		own = e.recipe.own if e.recipe is not None else None
		if own is None:
			continue
		for ing in own.ingredients:
			add_line(lines, ing, factor_of(e, own), own.title)
	staples = pantry.pantry_names(db)
	listed = shopping.unchecked_by_key(db)
	for key, line in lines.items():
		line["pantry"] = pantry.matches(line["name"], staples)
		line["on_list"] = key in listed
	return list(lines.values())
