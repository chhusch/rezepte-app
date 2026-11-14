"""Freezer endpoints under /freezer."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.schemas import FreezerItemIn, FreezerItemOut
from app.services import freezer as service

ITEM_NOT_FOUND = "item not found"

router = APIRouter(prefix="/freezer", dependencies=[Depends(current_user)])


@router.get("", response_model=list[FreezerItemOut])
def list_items(db: Session = Depends(get_db)):
	return service.list_items(db)


@router.post("", response_model=FreezerItemOut, status_code=201)
def add_item(data: FreezerItemIn, db: Session = Depends(get_db)):
	return service.add_item(db, data)


@router.put("/{item_id}", response_model=FreezerItemOut)
def update_item(item_id: int, data: FreezerItemIn,
		db: Session = Depends(get_db)):
	item = service.update_item(db, item_id, data)
	if item is None:
		raise HTTPException(status_code=404, detail=ITEM_NOT_FOUND)
	return item


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)):
	if not service.delete_item(db, item_id):
		raise HTTPException(status_code=404, detail=ITEM_NOT_FOUND)
	return Response(status_code=204)
