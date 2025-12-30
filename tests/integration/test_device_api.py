import pytest
from httpx import AsyncClient, codes

async def get_auth_client(client: AsyncClient, email="test@example.com", password="password"):
    # Register
    await client.post("/api/users/register", json={
        "email": email,
        "username": "testuser",
        "password": password
    })
    # Login
    response = await client.post("/api/users/login", json={
        "email": email,
        "password": password
    })

    client.headers.update({"Authorization": f"Bearer {response.json().get('access_token')}"})
    return client

@pytest.mark.asyncio
async def test_get_all_devices_empty(client: AsyncClient):
    client = await get_auth_client(client)
    resp = await client.get("/api/devices")
    assert resp.status_code == codes.OK
    assert resp.json() == []

@pytest.mark.asyncio
async def test_pairing_flow(client: AsyncClient):
    client = await get_auth_client(client)
    
    # 1. Request pairing code
    device_name = "Test Device"
    resp = await client.post("/api/devices/pairing", json={"name": device_name})
    assert resp.status_code == codes.OK
    data = resp.json()
    assert "pair_code" in data
    pair_code = data["pair_code"]
    
    # 2. Confirm pairing (using code)
    resp_confirm = await client.post(f"/api/devices/pairing/code/{pair_code}")
    assert resp_confirm.status_code == codes.OK
    confirm_data = resp_confirm.json()
    assert "device_id" in confirm_data
    assert "token" in confirm_data
    
    # 3. Verify device is in the list
    resp_list = await client.get("/api/devices")
    assert resp_list.status_code == codes.OK
    devices = resp_list.json()
    assert len(devices) == 1
    assert devices[0]["name"] == device_name
    assert devices[0]["id"] == confirm_data["device_id"]

@pytest.mark.asyncio
async def test_pairing_by_cred(client: AsyncClient):
    email = "test_cred@example.com"
    password = "password"
    client = await get_auth_client(client, email=email, password=password)

    payload = {
        "email": email,
        "password": password,
        "device_name": "TestDevice"
    }
    
    resp = await client.post("/api/devices/pairing/cred", json=payload)
    assert resp.status_code == codes.OK
    data = resp.json()
    assert "device_id" in data
    assert "token" in data

    client.cookies.update({"device_id": data["device_id"], 'token': data['token']})

    resp_list = await client.get("/api/devices")
    devices = resp_list.json()
    assert len(devices) == 1

    assert devices[0]["name"] == "TestDevice"

@pytest.mark.asyncio
async def test_revoke_device(client: AsyncClient):
    client = await get_auth_client(client)
    
    # Add a device first
    resp_pair = await client.post("/api/devices/pairing", json={"name": "To Delete"})
    code = resp_pair.json()["pair_code"]
    resp_confirm = await client.post(f"/api/devices/pairing/code/{code}")
    device_id = resp_confirm.json()["device_id"]
    
    # Verify it exists
    resp_list = await client.get("/api/devices")
    assert len(resp_list.json()) == 1
    
    # Revoke
    resp_del = await client.delete(f"/api/devices/{device_id}")
    assert resp_del.status_code == codes.NO_CONTENT
    
    # Check list empty
    resp_list_after = await client.get("/api/devices")
    assert resp_list_after.json() == []
