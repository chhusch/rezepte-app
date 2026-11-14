"""Freezer contents, oldest first so forgotten food shows up."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FreezerItem
from app.schemas import FreezerItemIn
from app.services import pantry


def list_items(db: Session) -> list[FreezerItem]:
	stmt = select(FreezerItem).order_by(FreezerItem.frozen_on,
					    FreezerItem.id)
	return list(db.scalars(stmt))


def apply(item: FreezerItem, data: FreezerItemIn) -> None:
	item.name = data.name
	item.amount = data.amount
	item.unit = data.unit
	item.note = data.note
	item.frozen_on = data.frozen_on or date.today()


def add_item(db: Session, data: FreezerItemIn) -> FreezerItem:
	item = FreezerItem()
	apply(item, data)
	db.add(item)
	db.commit()
	db.refresh(item)
	return item


def update_item(db: Session, item_id: int,
		data: FreezerItemIn) -> FreezerItem | None:
	item = db.get(FreezerItem, item_id)
	if item is None:
		return None
	apply(item, data)
	db.commit()
	db.refresh(item)
	return item


def delete_item(db: Session, item_id: int) -> bool:
	item = db.get(FreezerItem, item_id)
	if item is None:
		return False
	db.delete(item)
	db.commit()
	return True


def freezer_words(db: Session) -> list[set[str]]:
	return [set(pantry.norm_name(n).split()) for n in db.scalars(
		select(FreezerItem.name))]


def matches(name: str, stored: list[set[str]]) -> bool:
	"""True when all words of one name occur in the other, so
	"Hackfleisch" matches "Hackfleisch gemischt" either way."""
	words = set(pantry.norm_name(name).split())
	if not words:
		return False
	return any(s and (s <= words or words <= s) for s in stored)
