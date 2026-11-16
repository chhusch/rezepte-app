"""Login throttling per client address.

An address with MAX_FAILURES failed attempts within WINDOW is refused
until the oldest of them is older than WINDOW. Per address and not per
user, so a stranger cannot lock the owner out.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from app import auth
from app.models import LoginFailure

MAX_FAILURES = 5
WINDOW = timedelta(minutes=15)

log = logging.getLogger("app.auth")


def _since(now: datetime) -> datetime:
	return now - WINDOW


def retry_after(db: DbSession, ip: str) -> int:
	"""Seconds until the address may try again, 0 if not blocked."""
	now = auth.now_utc()
	times = db.scalars(select(LoginFailure.at)
			   .where(LoginFailure.ip == ip,
				  LoginFailure.at > _since(now))
			   .order_by(LoginFailure.at.desc())
			   .limit(MAX_FAILURES)).all()
	if len(times) < MAX_FAILURES:
		return 0
	free_at = auth.as_utc(times[-1]) + WINDOW
	return max(1, int((free_at - now).total_seconds()) + 1)


def record_failure(db: DbSession, ip: str, what: str) -> None:
	now = auth.now_utc()
	db.execute(delete(LoginFailure)
		   .where(LoginFailure.at <= _since(now)))
	db.add(LoginFailure(ip=ip, at=now))
	db.commit()
	log.warning("auth failure: %s from %s", what, ip)


def clear(db: DbSession, ip: str) -> None:
	db.execute(delete(LoginFailure).where(LoginFailure.ip == ip))
	db.commit()
