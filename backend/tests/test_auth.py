"""
Tests for JWT helpers and auth endpoints (signup, login, me).
Uses in-memory DB — no AWS credentials required.
"""

import pytest
from api.auth import _create_token, decode_token
from fastapi import HTTPException


class TestJwtHelpers:
    def test_round_trip(self):
        token = _create_token("user-abc", "user@example.com")
        payload = decode_token(token)
        assert payload["sub"] == "user-abc"
        assert payload["email"] == "user@example.com"

    def test_invalid_token_raises(self):
        with pytest.raises(HTTPException) as exc:
            decode_token("not.a.valid.token")
        assert exc.value.status_code == 401

    def test_tampered_token_raises(self):
        token = _create_token("user-abc", "user@example.com")
        bad = token[:-4] + "xxxx"
        with pytest.raises(HTTPException):
            decode_token(bad)


class TestSignup:
    async def test_success(self, client):
        resp = await client.post("/api/auth/signup", json={
            "email": "new@axon.dev",
            "password": "Password1!",
            "name": "New User",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["email"] == "new@axon.dev"
        assert "password" not in data["user"]

    async def test_duplicate_email(self, auth_headers):
        client, headers, user = auth_headers
        resp = await client.post("/api/auth/signup", json={
            "email": user["email"],
            "password": "Password1!",
            "name": "Dupe",
        })
        assert resp.status_code == 409

    async def test_short_password_rejected(self, client):
        resp = await client.post("/api/auth/signup", json={
            "email": "short@axon.dev",
            "password": "tiny",
            "name": "Short",
        })
        assert resp.status_code == 422

    async def test_invalid_email_rejected(self, client):
        resp = await client.post("/api/auth/signup", json={
            "email": "not-an-email",
            "password": "Password1!",
            "name": "User",
        })
        assert resp.status_code == 422


class TestLogin:
    async def test_success(self, client):
        await client.post("/api/auth/signup", json={
            "email": "login@axon.dev", "password": "Password1!", "name": "Login User"
        })
        resp = await client.post("/api/auth/login", json={
            "email": "login@axon.dev", "password": "Password1!"
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_wrong_password(self, client):
        await client.post("/api/auth/signup", json={
            "email": "wp@axon.dev", "password": "CorrectPass1", "name": "User"
        })
        resp = await client.post("/api/auth/login", json={
            "email": "wp@axon.dev", "password": "WrongPass1"
        })
        assert resp.status_code == 401

    async def test_unknown_email(self, client):
        resp = await client.post("/api/auth/login", json={
            "email": "nobody@axon.dev", "password": "anything"
        })
        assert resp.status_code == 401


class TestMe:
    async def test_authenticated(self, auth_headers):
        client, headers, user = auth_headers
        resp = await client.get("/api/auth/me", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == user["email"]

    async def test_unauthenticated(self, client):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    async def test_bad_token(self, client):
        resp = await client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
        assert resp.status_code == 401
