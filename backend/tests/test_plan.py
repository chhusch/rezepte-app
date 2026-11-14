"""Meal plan: entries, day settings, ingredient totals, bulk shopping."""

import pytest

PLAN = "/api/plan"
ENTRIES = PLAN + "/entries"
START = "2026-11-16"
TUESDAY = "2026-11-17"


def recipe(title, servings, ingredients):
	return {
		"category_id": None,
		"tags": [],
		"favorite": False,
		"source": {"kind": "none"},
		"version": {
			"title": title,
			"servings": servings,
			"ingredients": [{"amount": a, "unit": u, "name": n}
					for a, u, n in ingredients],
			"steps": [{"text": "Kochen."}],
		},
	}


def new_recipe(c, title, servings=None, ingredients=()):
	resp = c.post("/api/recipes",
		      json=recipe(title, servings, ingredients))
	assert resp.status_code == 201, resp.text
	return resp.json()["id"]


def add(c, day=START, slot="dinner", **kw):
	resp = c.post(ENTRIES, json=dict(day=day, slot=slot, **kw))
	assert resp.status_code == 201, resp.text
	return resp.json()


def plan(c, start=START, days=4):
	resp = c.get(PLAN, params={"start": start, "days": days})
	assert resp.status_code == 200, resp.text
	return resp.json()


def ingredients(c, start=START, days=4):
	resp = c.get(PLAN + "/ingredients",
		     params={"start": start, "days": days})
	assert resp.status_code == 200, resp.text
	return {(i["name"], i["unit"]): i for i in resp.json()}


def test_empty_plan_lists_every_day(auth_client):
	days = plan(auth_client, days=7)
	assert [d["day"] for d in days] == [
		"2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19",
		"2026-11-20", "2026-11-21", "2026-11-22"]
	assert days[0] == {"day": START, "note": "", "color": None,
			   "breakfast": False, "zvieri": False,
			   "entries": []}


@pytest.mark.parametrize("days", [0, 15])
def test_days_out_of_range(auth_client, days):
	resp = auth_client.get(PLAN, params={"start": START, "days": days})
	assert resp.status_code == 422


def test_text_and_recipe_entries(auth_client):
	rid = new_recipe(auth_client, "Älplermagronen", 4)
	first = add(auth_client, text="  Rösti mit Spiegelei ")
	second = add(auth_client, recipe_id=rid, servings=2)
	assert first["title"] == "Rösti mit Spiegelei"
	assert first["recipe_id"] is None
	assert (second["title"], second["servings"]) == ("Älplermagronen", 2)
	assert (first["position"], second["position"]) == (0, 1)
	entries = plan(auth_client)[0]["entries"]
	assert [e["title"] for e in entries] == ["Rösti mit Spiegelei",
						 "Älplermagronen"]


@pytest.mark.parametrize("body", [
	{"text": ""},
	{"text": "x", "servings": 0},
	{"text": "x", "slot": "znacht"},
])
def test_invalid_entry(auth_client, body):
	data = dict({"day": START, "slot": "lunch"}, **body)
	assert auth_client.post(ENTRIES, json=data).status_code == 422


def test_unknown_recipe(auth_client):
	resp = auth_client.post(ENTRIES, json={"day": START, "slot": "lunch",
					       "recipe_id": 999})
	assert resp.status_code == 422


def test_move_entry_goes_to_end_of_meal(auth_client):
	add(auth_client, day=TUESDAY, slot="lunch", text="Suppe")
	e = add(auth_client, text="Salat")
	resp = auth_client.put(f"{ENTRIES}/{e['id']}",
			       json={"day": TUESDAY, "slot": "lunch",
				     "text": "Salat"})
	assert resp.status_code == 200, resp.text
	assert resp.json()["position"] == 1
	days = plan(auth_client)
	assert days[0]["entries"] == []
	assert [x["title"] for x in days[1]["entries"]] == ["Suppe", "Salat"]


def test_update_and_delete_unknown(auth_client):
	body = {"day": START, "slot": "lunch", "text": "x"}
	assert auth_client.put(ENTRIES + "/9", json=body).status_code == 404
	assert auth_client.delete(ENTRIES + "/9").status_code == 404


def test_delete_entry(auth_client):
	e = add(auth_client, text="Pizza")
	assert auth_client.delete(f"{ENTRIES}/{e['id']}").status_code == 204
	assert plan(auth_client)[0]["entries"] == []


def test_recipe_title_follows_rename_and_survives_delete(auth_client):
	rid = new_recipe(auth_client, "Zopf")
	add(auth_client, recipe_id=rid)
	auth_client.put(f"/api/recipes/{rid}", json=recipe("Butterzopf",
							   None, ()))
	assert plan(auth_client)[0]["entries"][0]["title"] == "Butterzopf"
	auth_client.delete(f"/api/recipes/{rid}")
	entry = plan(auth_client)[0]["entries"][0]
	assert entry["recipe_id"] is None
	assert entry["title"] == "Zopf"


def test_day_settings(auth_client):
	resp = auth_client.put(f"{PLAN}/days/{TUESDAY}",
			       json={"note": " Gäste ", "color": "razz",
				     "zvieri": True})
	assert resp.status_code == 200, resp.text
	day = plan(auth_client)[1]
	assert (day["note"], day["color"]) == ("Gäste", "razz")
	assert (day["breakfast"], day["zvieri"]) == (False, True)
	auth_client.put(f"{PLAN}/days/{TUESDAY}", json={})
	day = plan(auth_client)[1]
	assert (day["note"], day["color"], day["zvieri"]) == ("", None, False)


def test_day_color_must_be_known(auth_client):
	resp = auth_client.put(f"{PLAN}/days/{START}", json={"color": "red"})
	assert resp.status_code == 422


def test_ingredients_scaled_and_merged(auth_client):
	zopf = new_recipe(auth_client, "Zopf", 4, [
		("500", "g", "Mehl"), ("2", "dl", "Milch"), (None, "", "Salz")])
	wahe = new_recipe(auth_client, "Wähe", 2, [
		("200", "g", "mehl"), ("1", "Stück", "Ei")])
	add(auth_client, recipe_id=zopf, servings=2)
	add(auth_client, day=TUESDAY, recipe_id=wahe)
	add(auth_client, text="Resten")
	auth_client.post("/api/pantry", json={"name": "Salz"})
	auth_client.post("/api/shopping", json={"name": "Milch",
						"unit": "dl"})
	lines = ingredients(auth_client)
	mehl = lines[("Mehl", "g")]
	assert mehl["amount"] == "450"
	assert mehl["recipes"] == ["Zopf", "Wähe"]
	assert lines[("Milch", "dl")]["amount"] == "1"
	assert lines[("Milch", "dl")]["on_list"] is True
	assert lines[("Salz", "")]["pantry"] is True
	assert lines[("Ei", "Stück")]["pantry"] is False


def test_ingredients_only_in_range(auth_client):
	rid = new_recipe(auth_client, "Zopf", 4, [("500", "g", "Mehl")])
	add(auth_client, day="2026-11-20", recipe_id=rid)
	assert ingredients(auth_client, days=4) == {}
	assert ("Mehl", "g") in ingredients(auth_client, days=5)


def test_bulk_shopping_merges_open_lines(auth_client):
	auth_client.post("/api/shopping", json={"name": "Mehl", "unit": "g",
						"amount": "100"})
	resp = auth_client.post("/api/shopping/bulk", json={"items": [
		{"name": "mehl", "unit": "g", "amount": "450"},
		{"name": "Ei", "unit": "Stück", "amount": "1"}]})
	assert resp.status_code == 200, resp.text
	items = {i["name"]: i for i in auth_client.get("/api/shopping").json()}
	assert set(items) == {"Mehl", "Ei"}
	assert items["Mehl"]["amount"] == "550"


@pytest.mark.parametrize("method, path", [
	("GET", PLAN + "?start=" + START),
	("GET", PLAN + "/ingredients?start=" + START),
	("PUT", PLAN + "/days/" + START),
	("POST", ENTRIES),
	("PUT", ENTRIES + "/1"),
	("DELETE", ENTRIES + "/1"),
	("POST", "/api/shopping/bulk"),
])
def test_requires_login(client, method, path):
	assert client.request(method, path, json={}).status_code == 401
