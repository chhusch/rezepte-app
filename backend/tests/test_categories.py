"""Category management: count, rename, recipes in use, delete."""

import pytest

CATEGORIES = "/api/categories"


def recipe(title, category_id):
	return {
		"category_id": category_id,
		"tags": [],
		"favorite": False,
		"source": {"kind": "none"},
		"version": {
			"title": title,
			"ingredients": [{"amount": "1", "unit": "",
					 "name": "Salz"}],
			"steps": [{"text": "Kochen."}],
		},
	}


def new_category(c, name):
	resp = c.post(CATEGORIES, json={"name": name})
	assert resp.status_code == 201, resp.text
	return resp.json()["id"]


def new_recipe(c, title, category_id):
	resp = c.post("/api/recipes", json=recipe(title, category_id))
	assert resp.status_code == 201, resp.text
	return resp.json()["id"]


def counts(c):
	return {r["name"]: r["recipe_count"]
		for r in c.get(CATEGORIES).json()}


@pytest.fixture
def suppen(auth_client):
	"""Category «Suppen» with two recipes, «Salate» with none."""
	cid = new_category(auth_client, "Suppen")
	new_category(auth_client, "Salate")
	new_recipe(auth_client, "Rüeblisuppe", cid)
	new_recipe(auth_client, "Bündner Gerstensuppe", cid)
	new_recipe(auth_client, "Rösti", None)
	return cid


def test_list_counts_recipes(auth_client, suppen):
	assert counts(auth_client) == {"Salate": 0, "Suppen": 2}


def test_recipes_in_category_sorted_by_title(auth_client, suppen):
	resp = auth_client.get(f"{CATEGORIES}/{suppen}/recipes")
	assert resp.status_code == 200, resp.text
	rows = resp.json()
	assert [r["title"] for r in rows] == ["Bündner Gerstensuppe",
					      "Rüeblisuppe"]
	assert set(rows[0]) == {"id", "title"}


def test_rename(auth_client, suppen):
	resp = auth_client.put(f"{CATEGORIES}/{suppen}",
			       json={"name": "  Suppen & Eintöpfe "})
	assert resp.status_code == 200, resp.text
	assert resp.json() == {"id": suppen, "name": "Suppen & Eintöpfe"}
	assert counts(auth_client)["Suppen & Eintöpfe"] == 2


def test_rename_own_name_other_case(auth_client, suppen):
	resp = auth_client.put(f"{CATEGORIES}/{suppen}",
			       json={"name": "SUPPEN"})
	assert resp.status_code == 200, resp.text
	assert resp.json()["name"] == "SUPPEN"


def test_rename_to_existing_name_conflicts(auth_client, suppen):
	resp = auth_client.put(f"{CATEGORIES}/{suppen}",
			       json={"name": "salate"})
	assert resp.status_code == 409
	assert counts(auth_client) == {"Salate": 0, "Suppen": 2}


@pytest.mark.parametrize("bad", ["", "   ", "x" * 201])
def test_rename_bad_name_rejected(auth_client, suppen, bad):
	resp = auth_client.put(f"{CATEGORIES}/{suppen}", json={"name": bad})
	assert resp.status_code == 422


def test_delete_unused(auth_client, suppen):
	salate = [r for r in auth_client.get(CATEGORIES).json()
		  if r["name"] == "Salate"][0]["id"]
	assert auth_client.delete(f"{CATEGORIES}/{salate}").status_code == 204
	assert counts(auth_client) == {"Suppen": 2}


def test_delete_used_keeps_recipes(auth_client, suppen):
	assert auth_client.delete(f"{CATEGORIES}/{suppen}").status_code == 204
	assert counts(auth_client) == {"Salate": 0}
	items = auth_client.get("/api/recipes").json()
	assert len(items) == 3
	assert all(i["category"] is None for i in items)


@pytest.mark.parametrize("method, path, body", [
	("PUT", "/999", {"name": "x"}),
	("DELETE", "/999", None),
	("GET", "/999/recipes", None),
])
def test_unknown_category(auth_client, method, path, body):
	resp = auth_client.request(method, CATEGORIES + path, json=body)
	assert resp.status_code == 404
