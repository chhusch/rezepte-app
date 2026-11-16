"""Login, logout, password and whoami. Mounted under /api by main.py."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.auth import COOKIE_NAME, MIN_PASSWORD_LEN
from app.config import settings
from app.db import get_db
from app.deps import client_ip, current_user, is_home_network
from app.models import User
from app.services import auth as auth_service
from app.services import throttle
from app.services import users as users_service

SECONDS_PER_DAY = 86400
WRONG_CREDENTIALS = "Benutzername oder Passwort falsch"
SETUP_DONE = "setup already done"
SETUP_FROM_HOME = "Ersteinrichtung nur aus dem Heimnetz"
TOO_MANY = "Zu viele Fehlversuche, später wieder versuchen"
WRONG_CURRENT = "Aktuelles Passwort falsch"
INVITE_INVALID = "Einladung ungültig oder abgelaufen"
MAX_NAME_LEN = 200

router = APIRouter(prefix="/auth")


class LoginInput(BaseModel):
	username: str
	password: str


class AccountInput(BaseModel):
	username: str = Field(min_length=1, max_length=MAX_NAME_LEN)
	password: str = Field(min_length=MIN_PASSWORD_LEN)

	@field_validator("username", mode="before")
	@classmethod
	def strip_name(cls, value):
		return value.strip() if isinstance(value, str) else value


class PasswordInput(BaseModel):
	current: str
	new: str = Field(min_length=MIN_PASSWORD_LEN)


def _set_cookie(resp: Response, token: str) -> None:
	resp.set_cookie(COOKIE_NAME, token, httponly=True,
			secure=settings.cookie_secure, samesite="lax",
			max_age=settings.session_days * SECONDS_PER_DAY,
			path="/")


def _clear_cookie(resp: Response) -> None:
	resp.delete_cookie(COOKIE_NAME, path="/", httponly=True,
			   secure=settings.cookie_secure, samesite="lax")


def _check_throttle(db: Session, ip: str) -> None:
	wait = throttle.retry_after(db, ip)
	if wait:
		raise HTTPException(status_code=429, detail=TOO_MANY,
				    headers={"Retry-After": str(wait)})


@router.get("/setup")
def setup_state(db: Session = Depends(get_db)):
	"""Public: tells the login screen whether the first user is
	missing."""
	return {"needed": not auth_service.has_users(db)}


@router.post("/setup", status_code=201)
def setup(body: AccountInput, request: Request, resp: Response,
	  db: Session = Depends(get_db)):
	"""Create the single user on first use and log in. Only from the
	home network, so nobody else can claim an empty database."""
	if auth_service.has_users(db):
		raise HTTPException(status_code=409, detail=SETUP_DONE)
	if not is_home_network(client_ip(request)):
		raise HTTPException(status_code=403, detail=SETUP_FROM_HOME)
	auth_service.create_user(db, body.username, body.password)
	token = auth_service.login(db, body.username, body.password)
	_set_cookie(resp, token)
	return {"username": body.username}


def _valid_invite(db: Session, ip: str, token: str):
	"""Unknown tokens count as failures, so links cannot be guessed."""
	_check_throttle(db, ip)
	inv = users_service.find_invite(db, token)
	if inv is None:
		throttle.record_failure(db, ip, "invite")
		raise HTTPException(status_code=404, detail=INVITE_INVALID)
	return inv


@router.get("/invite/{token}")
def invite_state(token: str, request: Request,
		 db: Session = Depends(get_db)):
	inv = _valid_invite(db, client_ip(request), token)
	return {"expires_at": inv.expires_at}


@router.post("/invite/{token}", status_code=201)
def accept_invite(token: str, body: AccountInput, request: Request,
		  resp: Response, db: Session = Depends(get_db)):
	inv = _valid_invite(db, client_ip(request), token)
	try:
		users_service.accept_invite(db, inv, body.username,
					    body.password)
	except users_service.UserError as e:
		raise HTTPException(status_code=409, detail=e.detail)
	token = auth_service.login(db, body.username, body.password)
	_set_cookie(resp, token)
	return {"username": body.username}


@router.post("/login")
def login(body: LoginInput, request: Request, resp: Response,
	  db: Session = Depends(get_db)):
	ip = client_ip(request)
	_check_throttle(db, ip)
	token = auth_service.login(db, body.username, body.password)
	if token is None:
		throttle.record_failure(db, ip, "login %r" % body.username)
		raise HTTPException(status_code=401, detail=WRONG_CREDENTIALS)
	throttle.clear(db, ip)
	_set_cookie(resp, token)
	return {"username": body.username}


@router.post("/password")
def change_password(body: PasswordInput, request: Request,
		    resp: Response, user: User = Depends(current_user),
		    db: Session = Depends(get_db)):
	"""Ends every session, including other devices; this one gets a
	new cookie."""
	ip = client_ip(request)
	_check_throttle(db, ip)
	token = auth_service.change_password(db, user, body.current,
					     body.new)
	if token is None:
		throttle.record_failure(db, ip, "password change")
		raise HTTPException(status_code=403, detail=WRONG_CURRENT)
	_set_cookie(resp, token)
	return {"ok": True}


@router.post("/logout")
def logout(request: Request, resp: Response,
	   db: Session = Depends(get_db)):
	token = request.cookies.get(COOKIE_NAME)
	if token:
		auth_service.logout(db, token)
	_clear_cookie(resp)
	return {"ok": True}


@router.post("/logout-all")
def logout_all(resp: Response, user: User = Depends(current_user),
	       db: Session = Depends(get_db)):
	auth_service.logout_all(db, user)
	_clear_cookie(resp)
	return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
	return {"username": user.username}
