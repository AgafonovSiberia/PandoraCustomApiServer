import pytest
from httpx import AsyncClient, codes


@pytest.mark.asyncio
async def test_register_user_success(client: AsyncClient):
    payload = {
        "email": "some_user@yandex.ru",
        "username": "some_user",
        "password": "some_password",
    }

    resp = await client.post("/api/users/register", json=payload)

    assert resp.status_code in (codes.CREATED,)


@pytest.mark.asyncio
async def test_register_user_duplicate_email(client: AsyncClient):
    payload = {
        "email": "some_user@yandex.ru",
        "username": "some_user",
        "password": "some_password",
    }

    first = await client.post("/api/users/register", json=payload)
    assert first.status_code in (codes.CREATED,)

    second = await client.post("/api/users/register", json=payload)
    assert second.status_code in (codes.NOT_FOUND,)


@pytest.mark.asyncio
async def test_login_user_success(client: AsyncClient):
    reg_payload = {
        "email": "some_user@yandex.ru",
        "username": "some_user",
        "password": "some_password",
    }
    reg_resp = await client.post("/api/users/register", json=reg_payload)
    assert reg_resp.status_code in (codes.CREATED,)

    login_payload = {
        "email": reg_payload["email"],
        "password": reg_payload["password"],
    }
    login_resp = await client.post("/api/users/login", json=login_payload)

    assert login_resp.status_code in (codes.OK,)
    assert "access_token" in login_resp.json()


@pytest.mark.asyncio
async def test_login_user_invalid_password(client: AsyncClient):
    reg_payload = {
        "email": "some_user@yandex.ru",
        "username": "some_user",
        "password": "some_password",
    }
    await client.post("/api/users/register", json=reg_payload)

    login_payload = {
        "email": reg_payload["email"],
        "password": "wrong-password",
    }
    login_resp = await client.post("/api/users/login", json=login_payload)

    assert login_resp.status_code in (codes.UNAUTHORIZED,)
