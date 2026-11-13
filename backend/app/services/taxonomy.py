"""Categories and tags, names unique ignoring case.

Categories can also be renamed and deleted; recipes of a deleted
category keep existing without one.
"""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, aliased

from app.models import Category, Recipe, RecipeVersion, Tag, VersionKind


class NameTaken(Exception):
	pass


def clean_name(name: str) -> str:
	name = (name or "").strip()
	if not name:
		raise ValueError("name must not be empty")
	return name


def find_by_name(db: Session, model, name: str):
	stmt = select(model).where(func.lower(model.name) == name.lower())
	return db.scalars(stmt).first()


def list_categories(db: Session) -> list[Category]:
	stmt = select(Category).order_by(Category.name)
	return list(db.scalars(stmt))


def create_category(db: Session, name: str) -> Category:
	name = clean_name(name)
	cat = find_by_name(db, Category, name)
	if cat is not None:
		return cat
	cat = Category(name=name)
	db.add(cat)
	db.commit()
	db.refresh(cat)
	return cat


def list_categories_counted(db: Session) -> list[dict]:
	"""Categories with the number of recipes using each."""
	n = func.count(Recipe.id)
	stmt = (select(Category, n)
		.outerjoin(Recipe, Recipe.category_id == Category.id)
		.group_by(Category.id)
		.order_by(Category.name))
	return [{"id": c.id, "name": c.name, "recipe_count": cnt}
		for c, cnt in db.execute(stmt)]


def rename_category(db: Session, cat_id: int,
		    name: str) -> Category | None:
	cat = db.get(Category, cat_id)
	if cat is None:
		return None
	name = clean_name(name)
	other = find_by_name(db, Category, name)
	if other is not None and other.id != cat.id:
		raise NameTaken(name)
	cat.name = name
	db.commit()
	db.refresh(cat)
	return cat


def category_recipes(db: Session, cat_id: int) -> list[dict] | None:
	"""Id and own title of every recipe in the category."""
	if db.get(Category, cat_id) is None:
		return None
	own = aliased(RecipeVersion)
	stmt = (select(Recipe.id, own.title)
		.join(own, (own.recipe_id == Recipe.id)
		      & (own.kind == VersionKind.OWN))
		.where(Recipe.category_id == cat_id)
		.order_by(func.lower(own.title), Recipe.id))
	return [{"id": i, "title": t} for i, t in db.execute(stmt)]


def delete_category(db: Session, cat_id: int) -> bool:
	cat = db.get(Category, cat_id)
	if cat is None:
		return False
	db.execute(update(Recipe).where(Recipe.category_id == cat_id)
		   .values(category_id=None))
	db.delete(cat)
	db.commit()
	db.expire_all()
	return True


def list_tags(db: Session) -> list[Tag]:
	stmt = select(Tag).order_by(Tag.name)
	return list(db.scalars(stmt))


def create_tag(db: Session, name: str) -> Tag:
	name = clean_name(name)
	tag = find_by_name(db, Tag, name)
	if tag is not None:
		return tag
	tag = Tag(name=name)
	db.add(tag)
	db.commit()
	db.refresh(tag)
	return tag


def get_or_create_tags(db: Session, names: list[str]) -> list[Tag]:
	"""Resolve tag names to Tag rows, creating missing ones (no commit)."""
	tags: list[Tag] = []
	for raw in names:
		name = (raw or "").strip()
		if not name:
			continue
		if any(t.name.lower() == name.lower() for t in tags):
			continue
		tag = find_by_name(db, Tag, name)
		if tag is None:
			tag = Tag(name=name)
			db.add(tag)
			db.flush()
		tags.append(tag)
	return tags
