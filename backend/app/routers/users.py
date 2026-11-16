"""Household members and invites. Mounted under /api by main.py."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import User
from app.schemas import ColorIn, InviteCreated, InviteOut, UserOut
from app.services import users as service

INVITE_NOT_FOUND = "Einladung nicht gefunden"

router = APIRouter()


def to_out(user: User, me: User) -> UserOut:
	return UserOut(id=user.id, username=user.username, color=user.color,
		       me=user.id == me.id)


def _bad(e: service.UserError):
	raise HTTPException(status_code=400, detail=e.detail)


@router.get("/users", response_model=list[UserOut])
def list_users(me: User = Depends(current_user),
	       db: Session = Depends(get_db)):
	return [to_out(u, me) for u in service.list_users(db)]


@router.put("/users/me", response_model=UserOut)
def set_color(body: ColorIn, me: User = Depends(current_user),
	      db: Session = Depends(get_db)):
	try:
		return to_out(service.set_color(db, me, body.color), me)
	except service.UserError as e:
		_bad(e)


@router.delete("/users/{user_id}", status_code=204)
def remove_user(user_id: int, me: User = Depends(current_user),
		db: Session = Depends(get_db)):
	try:
		service.remove_user(db, me, user_id)
	except service.UserError as e:
		_bad(e)
	return Response(status_code=204)


@router.get("/invites", response_model=list[InviteOut],
	    dependencies=[Depends(current_user)])
def list_invites(db: Session = Depends(get_db)):
	return [InviteOut.model_validate(i)
		for i in service.list_invites(db)]


@router.post("/invites", response_model=InviteCreated, status_code=201)
def create_invite(me: User = Depends(current_user),
		  db: Session = Depends(get_db)):
	inv, token = service.create_invite(db, me)
	return InviteCreated(id=inv.id, created_at=inv.created_at,
			     expires_at=inv.expires_at, token=token)


@router.delete("/invites/{invite_id}", status_code=204,
	       dependencies=[Depends(current_user)])
def delete_invite(invite_id: int, db: Session = Depends(get_db)):
	if not service.delete_invite(db, invite_id):
		raise HTTPException(status_code=404, detail=INVITE_NOT_FOUND)
	return Response(status_code=204)
