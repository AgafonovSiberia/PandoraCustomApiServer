import uuid
from fastapi import HTTPException, Request

from apps.common.dao.device import AuthDevice
from apps.gateway.services.device import DeviceService


async def authenticate_device_from_request(request: Request, device_service: DeviceService) -> AuthDevice:
    token = request.headers.get("Authorization")
    if not token or not token.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    cleaned_token = token.removeprefix("Bearer ").strip()
    device_id = request.cookies.get("device_id")
    if not device_id:
        raise HTTPException(status_code=401, detail="Missing device_id")

    try:
        device_uuid = uuid.UUID(device_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid device_id format")

    device = await device_service.process_token(device_id=device_uuid, token=cleaned_token)
    return AuthDevice(id=device.id, user_id=device.user_id, name=device.name)
