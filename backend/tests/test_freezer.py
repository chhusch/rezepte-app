"""Freezer: list oldest first, edit, match against plan ingredients."""

import io
import json
import zipfile
from datetime import date

import pytest

from app.services import freezer

FREEZER = "/api/freezer"


def add(c, name, **kw):
	resp = c.post(FREEZER, json=dict(name=name, **kw))
	assert resp.status_code == 201, resp.text
	return resp.json()


def names(c):
	return [i["name"] for i in c.get(FREEZER).json()]


def test_list_oldest_first(auth_client):
	add(auth_client, "Erbsen", frozen_on="2026-10-01")
	add(auth_client, "Hackfleisch", frozen_on="2026-06-12")
	add(auth_client, "Zopf")
	assert names(auth_client) == ["Hackfleisch", "Erbsen", "Zopf"]


def test_add_defaults_and_shape(auth_client):
	item = add(auth_client, "  Beeren ", amount="500", unit="g")
	assert item == {"id": item["id"], "name": "Beeren", "amount": "500",
			"unit": "g", "note": "",
			"frozen_on": date.today().isoformat()}


@pytest.mark.parametrize("body", [
	{"name": ""},
	{"name": "   "},
	{"name": "x", "amount": "-1"},
	{"name": "x", "frozen_on": "gestern"},
])
def test_invalid(auth_client, body):
	assert auth_client.post(FREEZER, json=body).status_code == 422


def test_update_and_delete(auth_client):
	item = add(auth_client, "Hackfleisch", amount="2", unit="Pack")
	resp = auth_client.put(f"{FREEZER}/{item['id']}",
			       json={"name": "Hackfleisch", "amount": "1",
				     "unit": "Pack",
				     "frozen_on": item["frozen_on"]})
	assert resp.status_code == 200, resp.text
	assert resp.json()["amount"] == "1"
	assert auth_client.delete(f"{FREEZER}/{item['id']}").status_code == 204
	assert names(auth_client) == []


def test_unknown_item(auth_client):
	assert auth_client.put(FREEZER + "/9",
			       json={"name": "x"}).status_code == 404
	assert auth_client.delete(FREEZER + "/9").status_code == 404


@pytest.mark.parametrize("ingredient, stored, hit", [
	("Hackfleisch", ["Hackfleisch gemischt"], True),
	("Hackfleisch gemischt", ["hackfleisch"], True),
	("Erbsen", ["Hackfleisch"], False),
	("", ["Erbsen"], False),
])
def test_matches(ingredient, stored, hit):
	words = [set(s.lower().split()) for s in stored]
	assert freezer.matches(ingredient, words) is hit


def test_plan_ingredients_mark_freezer(auth_client):
	resp = auth_client.post("/api/recipes", json={
		"category_id": None, "tags": [], "favorite": False,
		"source": {"kind": "none"},
		"version": {"title": "Lasagne", "ingredients": [
			{"amount": "500", "unit": "g", "name": "Hackfleisch"},
			{"amount": "1", "unit": "Pack", "name": "Lasagneblätter"}],
			"steps": [{"text": "Backen."}]}})
	rid = resp.json()["id"]
	auth_client.post("/api/plan/entries", json={
		"day": "2026-11-16", "slot": "dinner", "recipe_id": rid})
	add(auth_client, "Hackfleisch gemischt")
	resp = auth_client.get("/api/plan/ingredients",
			       params={"start": "2026-11-16", "days": 1})
	flags = {i["name"]: i["freezer"] for i in resp.json()}
	assert flags == {"Hackfleisch": True, "Lasagneblätter": False}


def test_export_has_plan_and_freezer(auth_client):
	add(auth_client, "Erbsen", frozen_on="2026-10-01")
	auth_client.post("/api/plan/entries", json={
		"day": "2026-11-16", "slot": "lunch", "text": "Suppe"})
	auth_client.put("/api/plan/days/2026-11-20", json={"note": "Gäste"})
	body = auth_client.get("/api/export").content
	zf = zipfile.ZipFile(io.BytesIO(body))
	data = json.loads(zf.read("recipes.json"))
	assert [i["name"] for i in data["freezer"]] == ["Erbsen"]
	assert [d["day"] for d in data["plan"]] == ["2026-11-16",
						    "2026-11-20"]
	assert data["plan"][0]["entries"][0]["title"] == "Suppe"
	assert data["plan"][1]["note"] == "Gäste"


@pytest.mark.parametrize("method, path", [
	("GET", FREEZER),
	("POST", FREEZER),
	("PUT", FREEZER + "/1"),
	("DELETE", FREEZER + "/1"),
])
def test_requires_login(client, method, path):
	assert client.request(method, path, json={}).status_code == 401
