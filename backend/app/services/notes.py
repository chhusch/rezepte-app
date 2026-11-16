"""Notes on a recipe: add and delete."""

from sqlalchemy.orm import Session

from app.models import Note, Recipe, User
from app.schemas import NoteIn


def add_note(db: Session, recipe_id: int, data: NoteIn,
	     user: User) -> Note | None:
	if db.get(Recipe, recipe_id) is None:
		return None
	note = Note(recipe_id=recipe_id, text=data.text, user_id=user.id)
	db.add(note)
	db.commit()
	db.refresh(note)
	return note


def delete_note(db: Session, recipe_id: int, note_id: int) -> bool:
	note = db.get(Note, note_id)
	if note is None or note.recipe_id != recipe_id:
		return False
	db.delete(note)
	db.commit()
	return True
