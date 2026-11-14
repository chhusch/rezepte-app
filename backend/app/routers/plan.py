"""Meal plan endpoints under /plan."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.schemas import (
	PlanDayIn,
	PlanDayOut,
	PlanEntryIn,
	PlanEntryOut,
	PlanIngredientOut,
)
from app.services import plan as service

ENTRY_NOT_FOUND = "entry not found"
RECIPE_NOT_FOUND = "recipe not found"

router = APIRouter(prefix="/plan", dependencies=[Depends(current_user)])

DAYS = Query(default=7, ge=1, le=service.MAX_DAYS)


@router.get("", response_model=list[PlanDayOut])
def get_plan(start: date, days: int = DAYS,
	     db: Session = Depends(get_db)):
	return service.get_plan(db, start, days)


@router.get("/ingredients", response_model=list[PlanIngredientOut])
def ingredients(start: date, days: int = DAYS,
		db: Session = Depends(get_db)):
	return service.ingredients(db, start, days)


@router.put("/days/{day}", response_model=PlanDayOut)
def set_day(day: date, data: PlanDayIn, db: Session = Depends(get_db)):
	return service.set_day(db, day, data)


@router.post("/entries", response_model=PlanEntryOut, status_code=201)
def add_entry(data: PlanEntryIn, db: Session = Depends(get_db)):
	try:
		return service.add_entry(db, data)
	except service.RecipeMissing:
		raise HTTPException(status_code=422, detail=RECIPE_NOT_FOUND)


@router.put("/entries/{entry_id}", response_model=PlanEntryOut)
def update_entry(entry_id: int, data: PlanEntryIn,
		 db: Session = Depends(get_db)):
	try:
		out = service.update_entry(db, entry_id, data)
	except service.RecipeMissing:
		raise HTTPException(status_code=422, detail=RECIPE_NOT_FOUND)
	if out is None:
		raise HTTPException(status_code=404, detail=ENTRY_NOT_FOUND)
	return out


@router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: int, db: Session = Depends(get_db)):
	if not service.delete_entry(db, entry_id):
		raise HTTPException(status_code=404, detail=ENTRY_NOT_FOUND)
	return Response(status_code=204)
