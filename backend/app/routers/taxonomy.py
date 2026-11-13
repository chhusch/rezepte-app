"""Categories (list, create, rename, delete) and tags (list, create)."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.schemas import (
	CategoryCount, CategoryIn, CategoryOut, CategoryRecipe, TagIn, TagOut,
)
from app.services import taxonomy as service

router = APIRouter(dependencies=[Depends(current_user)])

CATEGORY_NOT_FOUND = "category not found"
NAME_TAKEN = "category name already exists"


@router.get("/categories", response_model=list[CategoryCount])
def list_categories(db: Session = Depends(get_db)):
	return service.list_categories_counted(db)


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryIn, db: Session = Depends(get_db)):
	try:
		return service.create_category(db, data.name)
	except ValueError as err:
		raise HTTPException(status_code=422, detail=str(err))


@router.put("/categories/{cat_id}", response_model=CategoryOut)
def rename_category(cat_id: int, data: CategoryIn,
		    db: Session = Depends(get_db)):
	try:
		cat = service.rename_category(db, cat_id, data.name)
	except service.NameTaken:
		raise HTTPException(status_code=409, detail=NAME_TAKEN)
	except ValueError as err:
		raise HTTPException(status_code=422, detail=str(err))
	if cat is None:
		raise HTTPException(status_code=404, detail=CATEGORY_NOT_FOUND)
	return cat


@router.get("/categories/{cat_id}/recipes",
	    response_model=list[CategoryRecipe])
def category_recipes(cat_id: int, db: Session = Depends(get_db)):
	rows = service.category_recipes(db, cat_id)
	if rows is None:
		raise HTTPException(status_code=404, detail=CATEGORY_NOT_FOUND)
	return rows


@router.delete("/categories/{cat_id}", status_code=204)
def delete_category(cat_id: int, db: Session = Depends(get_db)):
	if not service.delete_category(db, cat_id):
		raise HTTPException(status_code=404, detail=CATEGORY_NOT_FOUND)
	return Response(status_code=204)


@router.get("/tags", response_model=list[TagOut])
def list_tags(db: Session = Depends(get_db)):
	return service.list_tags(db)


@router.post("/tags", response_model=TagOut, status_code=201)
def create_tag(data: TagIn, db: Session = Depends(get_db)):
	try:
		return service.create_tag(db, data.name)
	except ValueError as err:
		raise HTTPException(status_code=422, detail=str(err))
