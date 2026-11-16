"""FastAPI dependencies shared by routers."""

import ipaddress

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import COOKIE_NAME
from app.db import get_db
from app.models import User
from app.services import auth as auth_service

NOT_LOGGED_IN = "not logged in"


def current_user(request: Request,
		 db: Session = Depends(get_db)) -> User:
	token = request.cookies.get(COOKIE_NAME)
	user = None
	if token:
		user = auth_service.user_for_token(db, token)
	if user is None:
		raise HTTPException(status_code=401, detail=NOT_LOGGED_IN)
	return user


def client_ip(request: Request) -> str:
	"""Visitor address; uvicorn takes it from the header Caddy sets."""
	return request.client.host if request.client else ""


def is_home_network(ip: str) -> bool:
	try:
		addr = ipaddress.ip_address(ip)
	except ValueError:
		return False
	return addr.is_private or addr.is_loopback
