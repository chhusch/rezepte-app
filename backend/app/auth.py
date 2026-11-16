"""Password hashing and session token helpers. No HTTP here."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from functools import cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import settings

COOKIE_NAME = "session"
TOKEN_BYTES = 32
MIN_PASSWORD_LEN = 12

_hasher = PasswordHasher()


def hash_password(pw: str) -> str:
	return _hasher.hash(pw)


def verify_password(hash_: str, pw: str) -> bool:
	try:
		return _hasher.verify(hash_, pw)
	except (VerificationError, InvalidHashError):
		return False


@cache
def _dummy_hash() -> str:
	return _hasher.hash(secrets.token_urlsafe(TOKEN_BYTES))


def waste_verify(pw: str) -> None:
	"""Take as long as a real check, so a response does not tell
	whether a user name exists."""
	verify_password(_dummy_hash(), pw)


def new_token() -> str:
	return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
	return hashlib.sha256(token.encode("utf-8")).hexdigest()


def now_utc() -> datetime:
	return datetime.now(timezone.utc)


def as_utc(dt: datetime) -> datetime:
	"""SQLite returns naive datetimes; treat them as UTC."""
	if dt.tzinfo is None:
		return dt.replace(tzinfo=timezone.utc)
	return dt


def session_expiry() -> datetime:
	return now_utc() + timedelta(days=settings.session_days)
