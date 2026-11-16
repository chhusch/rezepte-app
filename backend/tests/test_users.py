"""Household: members, colors, invites and authors."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app import auth
from app.main import app
from app.models import Invite, LoginFailure, Note, Session, User
from app.services import auth as auth_service
from app.services import throttle
from tests.conftest import HOME_ADDR, TEST_USER
from tests.test_recipes import post_recipe

PARTNER = "partner"
PASSWORD = "auch-ein-langes"
ACCOUNT = {"username": PARTNER, "password": PASSWORD}


@pytest.fixture
def guest(client):
	"""Second browser without a session, same app and database."""
	with TestClient(app, client=HOME_ADDR) as c:
		yield c


def invite(c) -> str:
	r = c.post("/api/invites")
	assert r.status_code == 201, r.text
	return r.json()["token"]


def accept(c, token, body=ACCOUNT):
	return c.post("/api/auth/invite/" + token, json=body)


def test_list_users_marks_me(auth_client):
	r = auth_client.get("/api/users")
	assert r.json() == [{"id": 1, "username": TEST_USER,
			     "color": "sea", "me": True}]


def test_users_require_login(client):
	assert client.get("/api/users").status_code == 401
	assert client.post("/api/invites").status_code == 401


def test_set_color(auth_client):
	r = auth_client.put("/api/users/me", json={"color": "mustard"})
	assert r.json()["color"] == "mustard"
	r = auth_client.put("/api/users/me", json={"color": "lila"})
	assert r.status_code == 400


def test_invite_flow(auth_client, guest, db):
	token = invite(auth_client)
	assert len(auth_client.get("/api/invites").json()) == 1
	assert guest.get("/api/auth/invite/" + token).status_code == 200
	r = accept(guest, token)
	assert r.status_code == 201
	assert guest.get("/api/auth/me").json() == {"username": PARTNER}
	partner = auth_service.get_user(db, PARTNER)
	assert partner.color == "razz"
	assert db.scalars(select(Invite)).all() == []
	assert accept(guest, token).status_code == 404


def test_invite_token_stored_hashed(auth_client, db):
	token = invite(auth_client)
	inv = db.scalars(select(Invite)).one()
	assert inv.token_hash == auth.hash_token(token)
	assert token not in inv.token_hash


def test_expired_invite_rejected(auth_client, guest, db):
	token = invite(auth_client)
	db.execute(update(Invite).values(
		expires_at=auth.now_utc() - timedelta(seconds=1)))
	db.commit()
	assert guest.get("/api/auth/invite/" + token).status_code == 404
	assert auth_client.get("/api/invites").json() == []


def test_withdrawn_invite_rejected(auth_client, guest):
	token = invite(auth_client)
	iid = auth_client.get("/api/invites").json()[0]["id"]
	assert auth_client.delete("/api/invites/%d" % iid).status_code == 204
	assert accept(guest, token).status_code == 404
	assert auth_client.delete("/api/invites/%d" % iid).status_code == 404


def test_accept_validates(auth_client, guest):
	token = invite(auth_client)
	r = accept(guest, token, {"username": PARTNER, "password": "kurz"})
	assert r.status_code == 422
	r = accept(guest, token, {"username": TEST_USER,
				  "password": PASSWORD})
	assert r.status_code == 409
	assert accept(guest, token).status_code == 201


def test_guessing_invites_is_throttled(auth_client, guest, db):
	token = invite(auth_client)
	for _ in range(throttle.MAX_FAILURES):
		assert guest.get("/api/auth/invite/x").status_code == 404
	assert len(db.scalars(select(LoginFailure)).all()) == \
		throttle.MAX_FAILURES
	assert accept(guest, token).status_code == 429


def test_remove_user(auth_client, guest, db):
	accept(guest, invite(auth_client))
	partner = auth_service.get_user(db, PARTNER)
	rid = post_recipe(guest)["id"]
	r = guest.post("/api/recipes/%d/notes" % rid, json={"text": "Gut"})
	assert r.json()["author"] == {"username": PARTNER, "color": "razz"}
	r = auth_client.delete("/api/users/%d" % partner.id)
	assert r.status_code == 204
	assert guest.get("/api/auth/me").status_code == 401
	db.expire_all()
	assert db.scalars(select(Note)).one().user_id is None
	assert db.scalars(select(Session).where(
		Session.user_id == partner.id)).all() == []
	body = auth_client.get("/api/recipes/%d" % rid).json()
	assert body["notes"][0]["author"] is None


def test_cannot_remove_self(auth_client, db):
	me = db.scalars(select(User)).one()
	r = auth_client.delete("/api/users/%d" % me.id)
	assert r.status_code == 400
	assert auth_client.delete("/api/users/999").status_code == 400


def test_colors_cycle_when_all_taken(db):
	names = ["u%d" % i for i in range(len(auth_service.COLORS) + 1)]
	users = [auth_service.create_user(db, n, PASSWORD) for n in names]
	assert [u.color for u in users] == \
		list(auth_service.COLORS) + [auth_service.COLORS[0]]
