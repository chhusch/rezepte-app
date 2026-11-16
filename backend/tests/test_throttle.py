"""Login throttling, setup from outside, password change, logout-all."""

import logging
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app import auth
from app.deps import is_home_network
from app.main import app
from app.models import LoginFailure, Session
from app.services import auth as auth_service
from app.services import throttle
from tests.conftest import TEST_PASSWORD, TEST_USER

LOGIN = "/api/auth/login"
SETUP = "/api/auth/setup"
PASSWORD = "/api/auth/password"
LOGOUT_ALL = "/api/auth/logout-all"
ME = "/api/auth/me"
OUTSIDE_ADDR = ("185.199.108.7", 40000)
GOOD = {"username": TEST_USER, "password": TEST_PASSWORD}
BAD = {"username": TEST_USER, "password": "falsch"}
NEW_PASSWORD = "ein-neues-langes"


@pytest.fixture
def outside(client):
	"""Second client on the same app and database, other address."""
	with TestClient(app, client=OUTSIDE_ADDR) as c:
		yield c


@pytest.fixture
def user(db):
	return auth_service.create_user(db, TEST_USER, TEST_PASSWORD)


def fail(c, n=throttle.MAX_FAILURES):
	for _ in range(n):
		assert c.post(LOGIN, json=BAD).status_code == 401


def age_failures(db, delta):
	db.execute(update(LoginFailure)
		   .values(at=LoginFailure.at - delta))
	db.commit()


def test_locked_after_max_failures(client, user):
	fail(client)
	r = client.post(LOGIN, json=GOOD)
	assert r.status_code == 429
	assert 0 < int(r.headers["retry-after"]) <= 15 * 60
	assert auth.COOKIE_NAME not in r.cookies


def test_one_below_limit_still_allowed(client, user):
	fail(client, throttle.MAX_FAILURES - 1)
	assert client.post(LOGIN, json=GOOD).status_code == 200


def test_lock_is_per_address(client, outside, user):
	fail(outside)
	assert outside.post(LOGIN, json=GOOD).status_code == 429
	assert client.post(LOGIN, json=GOOD).status_code == 200


def test_unknown_user_counts(client, user):
	for _ in range(throttle.MAX_FAILURES):
		client.post(LOGIN, json={"username": "x", "password": "y"})
	assert client.post(LOGIN, json=GOOD).status_code == 429


def test_lock_ends_after_window(client, db, user):
	fail(client)
	age_failures(db, throttle.WINDOW)
	assert client.post(LOGIN, json=GOOD).status_code == 200


def test_success_clears_failures(client, db, user):
	fail(client, throttle.MAX_FAILURES - 1)
	assert client.post(LOGIN, json=GOOD).status_code == 200
	assert db.scalars(select(LoginFailure)).all() == []


def test_old_failures_are_purged(client, db, user):
	fail(client, 2)
	age_failures(db, throttle.WINDOW)
	fail(client, 1)
	assert len(db.scalars(select(LoginFailure)).all()) == 1


def test_failure_is_logged_with_address(client, user, caplog):
	with caplog.at_level(logging.WARNING, logger="app.auth"):
		fail(client, 1)
	assert "192.168.0.20" in caplog.text
	assert repr(TEST_USER) in caplog.text


def test_unknown_user_costs_a_hash_check(client, monkeypatch):
	calls = []
	monkeypatch.setattr(auth, "waste_verify", calls.append)
	client.post(LOGIN, json={"username": "x", "password": "y"})
	assert calls == ["y"]


def test_setup_refused_from_outside(outside, db):
	r = outside.post(SETUP, json={"username": "fremd",
				      "password": NEW_PASSWORD})
	assert r.status_code == 403
	assert auth_service.has_users(db) is False


@pytest.mark.parametrize("ip, home", [
	("192.168.0.20", True), ("10.8.0.2", True), ("127.0.0.1", True),
	("172.18.0.3", True), ("185.199.108.7", False), ("8.8.8.8", False),
	("", False), ("testclient", False),
])
def test_is_home_network(ip, home):
	assert is_home_network(ip) is home


def test_change_password(auth_client, db):
	other = auth_service.login(db, TEST_USER, TEST_PASSWORD)
	r = auth_client.post(PASSWORD, json={"current": TEST_PASSWORD,
					     "new": NEW_PASSWORD})
	assert r.status_code == 200
	assert auth.COOKIE_NAME in r.cookies
	assert auth_client.get(ME).status_code == 200
	assert auth_service.user_for_token(db, other) is None
	assert len(db.scalars(select(Session)).all()) == 1
	assert auth_service.login(db, TEST_USER, NEW_PASSWORD)
	assert auth_service.login(db, TEST_USER, TEST_PASSWORD) is None


def test_change_password_wrong_current(auth_client, db):
	r = auth_client.post(PASSWORD, json={"current": "falsch",
					     "new": NEW_PASSWORD})
	assert r.status_code == 403
	assert auth_client.get(ME).status_code == 200
	assert len(db.scalars(select(LoginFailure)).all()) == 1


def test_change_password_too_short(auth_client):
	r = auth_client.post(PASSWORD, json={"current": TEST_PASSWORD,
					     "new": "kurz"})
	assert r.status_code == 422


def test_change_password_throttled(auth_client):
	for _ in range(throttle.MAX_FAILURES):
		auth_client.post(PASSWORD, json={"current": "falsch",
						 "new": NEW_PASSWORD})
	r = auth_client.post(PASSWORD, json={"current": TEST_PASSWORD,
					     "new": NEW_PASSWORD})
	assert r.status_code == 429


def test_change_password_requires_login(client):
	r = client.post(PASSWORD, json={"current": "a", "new": NEW_PASSWORD})
	assert r.status_code == 401


def test_logout_all(auth_client, db):
	other = auth_service.login(db, TEST_USER, TEST_PASSWORD)
	assert auth_client.post(LOGOUT_ALL).status_code == 200
	assert auth_client.get(ME).status_code == 401
	assert auth_service.user_for_token(db, other) is None
	assert db.scalars(select(Session)).all() == []
