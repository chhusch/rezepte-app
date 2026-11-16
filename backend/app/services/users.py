"""Household members and invites. Everyone has the same rights; nobody
removes their own account, so one always remains."""

from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from app import auth
from app.models import Invite, User
from app.services import auth as auth_service

INVITE_DAYS = 7


class UserError(ValueError):
	"""Carries a short German message for the API response."""

	def __init__(self, detail: str):
		super().__init__(detail)
		self.detail = detail


def list_users(db: DbSession) -> list[User]:
	return list(db.scalars(select(User).order_by(User.id)))


def set_color(db: DbSession, user: User, color: str) -> User:
	if color not in auth_service.COLORS:
		raise UserError("Unbekannte Farbe")
	user.color = color
	db.commit()
	return user


def remove_user(db: DbSession, me: User, user_id: int) -> None:
	user = db.get(User, user_id)
	if user is None:
		raise UserError("Benutzer nicht gefunden")
	if user.id == me.id:
		raise UserError("Das eigene Konto lässt sich nicht entfernen")
	db.delete(user)
	db.commit()


def _purge_expired(db: DbSession) -> None:
	db.execute(delete(Invite).where(Invite.expires_at <= auth.now_utc()))


def create_invite(db: DbSession, me: User) -> tuple[Invite, str]:
	"""Return the invite and its raw token; only the hash is kept."""
	_purge_expired(db)
	token = auth.new_token()
	inv = Invite(token_hash=auth.hash_token(token), created_by=me.id,
		     expires_at=auth.now_utc() + timedelta(days=INVITE_DAYS))
	db.add(inv)
	db.commit()
	db.refresh(inv)
	return inv, token


def list_invites(db: DbSession) -> list[Invite]:
	_purge_expired(db)
	db.commit()
	return list(db.scalars(select(Invite).order_by(Invite.created_at)))


def delete_invite(db: DbSession, invite_id: int) -> bool:
	inv = db.get(Invite, invite_id)
	if inv is None:
		return False
	db.delete(inv)
	db.commit()
	return True


def find_invite(db: DbSession, token: str) -> Invite | None:
	"""A valid, unexpired invite for this raw token, else None."""
	inv = db.scalar(select(Invite)
			.where(Invite.token_hash == auth.hash_token(token)))
	if inv is None or auth.as_utc(inv.expires_at) <= auth.now_utc():
		return None
	return inv


def accept_invite(db: DbSession, inv: Invite, username: str,
		  password: str) -> User:
	if auth_service.get_user(db, username) is not None:
		raise UserError("Benutzername ist vergeben")
	user = auth_service.create_user(db, username, password)
	db.delete(inv)
	db.commit()
	return user
