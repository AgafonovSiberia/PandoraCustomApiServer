"""
Unit-тесты для модуля apps/gateway/api/routes/device.py

Эти тесты изолированы от внешних зависимостей (БД, Redis, внешние API)
с помощью мокирования через pytest-mock.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from apps.common.dao.device import DeviceDomain, DevicePairDataOut, DeviceRegData
from apps.common.dao.user import AuthUser, ConfirmDeviceIn
from apps.gateway.services.device import DeviceService


@pytest.fixture
def mock_auth_user():
    """Фикстура для мокирования аутентифицированного пользователя"""
    return AuthUser(
        id=1,
        token="test_auth_token"
    )


@pytest.fixture
def mock_device_service():
    """Фикстура для мокирования DeviceService"""
    service = AsyncMock(spec=DeviceService)
    return service


@pytest.fixture
def sample_device():
    """Фикстура для примера устройства"""
    return DeviceDomain(
        id=uuid.uuid4(),
        name="Test Device",
        user_id=1,
        token_hash=b"hashed_token",
        expires_at=datetime.now(UTC) + timedelta(days=60),
        last_rotated_at=datetime.now(UTC),
        last_used_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )


@pytest.fixture
def sample_devices(sample_device):
    """Фикстура для списка устройств"""
    device2 = DeviceDomain(
        id=uuid.uuid4(),
        name="Test Device 2",
        user_id=1,
        token_hash=b"hashed_token_2",
        expires_at=datetime.now(UTC) + timedelta(days=60),
        last_rotated_at=datetime.now(UTC),
        last_used_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    return [sample_device, device2]


class TestGetAllDevices:
    """Тесты для эндпоинта GET /api/devices"""

    @pytest.mark.asyncio
    async def test_get_all_devices_success(
        self, mock_device_service, mock_auth_user, sample_devices
    ):
        """Тест успешного получения списка устройств"""
        # Arrange
        mock_device_service.get_all.return_value = sample_devices

        # Act
        from apps.gateway.api.routes.device import get_all_devices
        result = await get_all_devices(
            auth_user=mock_auth_user,
            device_service=mock_device_service
        )

        # Assert
        assert result == sample_devices
        mock_device_service.get_all.assert_called_once_with(user_id=mock_auth_user.id)

    @pytest.mark.asyncio
    async def test_get_all_devices_empty(
        self, mock_device_service, mock_auth_user
    ):
        """Тест получения пустого списка устройств"""
        # Arrange
        mock_device_service.get_all.return_value = None

        # Act
        from apps.gateway.api.routes.device import get_all_devices
        result = await get_all_devices(
            auth_user=mock_auth_user,
            device_service=mock_device_service
        )

        # Assert
        assert result == []
        mock_device_service.get_all.assert_called_once_with(user_id=mock_auth_user.id)

    @pytest.mark.asyncio
    async def test_get_all_devices_returns_empty_list(
        self, mock_device_service, mock_auth_user
    ):
        """Тест когда сервис возвращает пустой список"""
        # Arrange
        mock_device_service.get_all.return_value = []

        # Act
        from apps.gateway.api.routes.device import get_all_devices
        result = await get_all_devices(
            auth_user=mock_auth_user,
            device_service=mock_device_service
        )

        # Assert
        assert result == []
        mock_device_service.get_all.assert_called_once_with(user_id=mock_auth_user.id)


class TestPair:
    """Тесты для эндпоинта POST /api/devices/pairing"""

    @pytest.mark.asyncio
    async def test_pair_success(
        self, mock_device_service, mock_auth_user
    ):
        """Тест успешной генерации кода сопряжения"""
        # Arrange
        device_data = DeviceRegData(name="New Device")
        expected_code = "123456"
        mock_device_service.generate_pair_code.return_value = expected_code

        # Act
        from apps.gateway.api.routes.device import pair
        result = await pair(
            device_data=device_data,
            auth_user=mock_auth_user,
            device_service=mock_device_service
        )

        # Assert
        assert result.status_code == status.HTTP_200_OK
        assert result.body.decode() == '{"pair_code":"123456"}'
        mock_device_service.generate_pair_code.assert_called_once_with(
            user_id=mock_auth_user.id,
            device_name=device_data.name
        )

    @pytest.mark.asyncio
    async def test_pair_device_already_exists(
        self, mock_device_service, mock_auth_user
    ):
        """Тест когда устройство с таким именем уже существует"""
        # Arrange
        device_data = DeviceRegData(name="Existing Device")
        mock_device_service.generate_pair_code.side_effect = HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DEVICE_ALREADY_EXISTS"
        )

        # Act & Assert
        from apps.gateway.api.routes.device import pair
        with pytest.raises(HTTPException) as exc_info:
            await pair(
                device_data=device_data,
                auth_user=mock_auth_user,
                device_service=mock_device_service
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert exc_info.value.detail == "DEVICE_ALREADY_EXISTS"


class TestPairConfirm:
    """Тесты для эндпоинта POST /api/devices/pairing/code/{code}"""

    @pytest.mark.asyncio
    async def test_pair_confirm_success(self, mock_device_service):
        """Тест успешного сопряжения по коду"""
        # Arrange
        pair_code = "123456"
        device_id = uuid.uuid4()
        expected_result = DevicePairDataOut(
            device_id=str(device_id),
            token="test_token_123"
        )
        mock_device_service.pair_by_code.return_value = expected_result

        # Act
        from apps.gateway.api.routes.device import pair_confirm
        result = await pair_confirm(
            code=pair_code,
            device_service=mock_device_service
        )

        # Assert
        assert result == expected_result
        mock_device_service.pair_by_code.assert_called_once_with(pair_code=pair_code)

    @pytest.mark.asyncio
    async def test_pair_confirm_invalid_code(self, mock_device_service):
        """Тест сопряжения с невалидным кодом"""
        # Arrange
        pair_code = "invalid"
        mock_device_service.pair_by_code.side_effect = HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="INVALID_CODE"
        )

        # Act & Assert
        from apps.gateway.api.routes.device import pair_confirm
        with pytest.raises(HTTPException) as exc_info:
            await pair_confirm(
                code=pair_code,
                device_service=mock_device_service
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert exc_info.value.detail == "INVALID_CODE"

    @pytest.mark.asyncio
    async def test_pair_confirm_expired_code(self, mock_device_service):
        """Тест сопряжения с истекшим кодом"""
        # Arrange
        pair_code = "expired"
        mock_device_service.pair_by_code.side_effect = HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="INVALID_CODE"
        )

        # Act & Assert
        from apps.gateway.api.routes.device import pair_confirm
        with pytest.raises(HTTPException) as exc_info:
            await pair_confirm(
                code=pair_code,
                device_service=mock_device_service
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


class TestPairConfirmByCred:
    """Тесты для эндпоинта POST /api/devices/pairing/cred"""

    @pytest.mark.asyncio
    async def test_pair_confirm_by_cred_success(self, mock_device_service):
        """Тест успешного сопряжения по учетным данным"""
        # Arrange
        confirm_in = ConfirmDeviceIn(
            email="test@example.com",
            password="password123",
            device_name="Test Device"
        )
        device_id = uuid.uuid4()
        expected_result = DevicePairDataOut(
            device_id=str(device_id),
            token="test_token_456"
        )
        mock_device_service.pair_by_cred.return_value = expected_result
        mock_request = MagicMock()

        # Act
        from apps.gateway.api.routes.device import pair_confirm_by_cred
        result = await pair_confirm_by_cred(
            confirm_in=confirm_in,
            request=mock_request,
            device_service=mock_device_service
        )

        # Assert
        assert result == expected_result
        mock_device_service.pair_by_cred.assert_called_once_with(confirm_in=confirm_in)

    @pytest.mark.asyncio
    async def test_pair_confirm_by_cred_user_not_found(self, mock_device_service):
        """Тест сопряжения когда пользователь не найден"""
        # Arrange
        confirm_in = ConfirmDeviceIn(
            email="nonexistent@example.com",
            password="password123",
            device_name="Test Device"
        )
        mock_device_service.pair_by_cred.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="USER_NOT_FOUND"
        )
        mock_request = MagicMock()

        # Act & Assert
        from apps.gateway.api.routes.device import pair_confirm_by_cred
        with pytest.raises(HTTPException) as exc_info:
            await pair_confirm_by_cred(
                confirm_in=confirm_in,
                request=mock_request,
                device_service=mock_device_service
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "USER_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_pair_confirm_by_cred_invalid_password(self, mock_device_service):
        """Тест сопряжения с неверным паролем"""
        # Arrange
        confirm_in = ConfirmDeviceIn(
            email="test@example.com",
            password="wrong_password",
            device_name="Test Device"
        )
        mock_device_service.pair_by_cred.side_effect = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="INVALID_CREDENTIALS"
        )
        mock_request = MagicMock()

        # Act & Assert
        from apps.gateway.api.routes.device import pair_confirm_by_cred
        with pytest.raises(HTTPException) as exc_info:
            await pair_confirm_by_cred(
                confirm_in=confirm_in,
                request=mock_request,
                device_service=mock_device_service
            )

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_pair_confirm_by_cred_no_device_name(self, mock_device_service):
        """Тест сопряжения без имени устройства"""
        # Arrange
        confirm_in = ConfirmDeviceIn(
            email="test@example.com",
            password="password123",
            device_name=""
        )
        mock_device_service.pair_by_cred.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="UNDEFINED_DEVICE_NAME"
        )
        mock_request = MagicMock()

        # Act & Assert
        from apps.gateway.api.routes.device import pair_confirm_by_cred
        with pytest.raises(HTTPException) as exc_info:
            await pair_confirm_by_cred(
                confirm_in=confirm_in,
                request=mock_request,
                device_service=mock_device_service
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "UNDEFINED_DEVICE_NAME"


class TestRevoke:
    """Тесты для эндпоинта DELETE /api/devices/{device_id}"""

    @pytest.mark.asyncio
    async def test_revoke_success(self, mock_device_service):
        """Тест успешного отзыва сопряжения"""
        # Arrange
        device_id = uuid.uuid4()
        mock_device_service.device_revoke.return_value = None

        # Act
        from apps.gateway.api.routes.device import revoke
        result = await revoke(
            device_id=device_id,
            device_service=mock_device_service
        )

        # Assert
        assert result.status_code == status.HTTP_204_NO_CONTENT
        mock_device_service.device_revoke.assert_called_once_with(device_id=device_id)

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_device(self, mock_device_service):
        """Тест отзыва несуществующего устройства"""
        # Arrange
        device_id = uuid.uuid4()
        mock_device_service.device_revoke.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DEVICE_NOT_FOUND"
        )

        # Act & Assert
        from apps.gateway.api.routes.device import revoke
        with pytest.raises(HTTPException) as exc_info:
            await revoke(
                device_id=device_id,
                device_service=mock_device_service
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "DEVICE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_revoke_with_invalid_uuid(self, mock_device_service):
        """Тест отзыва с невалидным UUID"""
        # Arrange
        # UUID будет валидирован FastAPI автоматически, 
        # но мы можем протестировать поведение сервиса
        device_id = uuid.uuid4()
        mock_device_service.device_revoke.side_effect = ValueError("Invalid UUID")

        # Act & Assert
        from apps.gateway.api.routes.device import revoke
        with pytest.raises(ValueError):
            await revoke(
                device_id=device_id,
                device_service=mock_device_service
            )


class TestDeviceRouteIntegration:
    """Интеграционные тесты для проверки взаимодействия между эндпоинтами"""

    @pytest.mark.asyncio
    async def test_full_pairing_flow(
        self, mock_device_service, mock_auth_user
    ):
        """Тест полного потока сопряжения устройства"""
        # Arrange
        device_name = "Integration Test Device"
        pair_code = "654321"
        device_id = uuid.uuid4()
        token = "integration_token"

        mock_device_service.generate_pair_code.return_value = pair_code
        mock_device_service.pair_by_code.return_value = DevicePairDataOut(
            device_id=str(device_id),
            token=token
        )

        # Act - Step 1: Generate pair code
        from apps.gateway.api.routes.device import pair
        device_data = DeviceRegData(name=device_name)
        pair_result = await pair(
            device_data=device_data,
            auth_user=mock_auth_user,
            device_service=mock_device_service
        )

        # Assert Step 1
        assert pair_result.status_code == status.HTTP_200_OK
        assert pair_code in pair_result.body.decode()

        # Act - Step 2: Confirm pairing
        from apps.gateway.api.routes.device import pair_confirm
        confirm_result = await pair_confirm(
            code=pair_code,
            device_service=mock_device_service
        )

        # Assert Step 2
        assert confirm_result.device_id == str(device_id)
        assert confirm_result.token == token

        # Verify all calls
        mock_device_service.generate_pair_code.assert_called_once()
        mock_device_service.pair_by_code.assert_called_once()

    @pytest.mark.asyncio
    async def test_device_lifecycle(
        self, mock_device_service, mock_auth_user, sample_device
    ):
        """Тест жизненного цикла устройства: создание -> получение -> удаление"""
        # Arrange
        device_name = "Lifecycle Test Device"
        pair_code = "111111"
        device_id = sample_device.id

        mock_device_service.generate_pair_code.return_value = pair_code
        mock_device_service.pair_by_code.return_value = DevicePairDataOut(
            device_id=str(device_id),
            token="lifecycle_token"
        )
        mock_device_service.get_all.return_value = [sample_device]
        mock_device_service.device_revoke.return_value = None

        # Act & Assert - Create
        from apps.gateway.api.routes.device import pair, get_all_devices, revoke
        
        device_data = DeviceRegData(name=device_name)
        await pair(
            device_data=device_data,
            auth_user=mock_auth_user,
            device_service=mock_device_service
        )

        # Act & Assert - Get
        devices = await get_all_devices(
            auth_user=mock_auth_user,
            device_service=mock_device_service
        )
        assert len(devices) == 1
        assert devices[0].id == device_id

        # Act & Assert - Delete
        delete_result = await revoke(
            device_id=device_id,
            device_service=mock_device_service
        )
        assert delete_result.status_code == status.HTTP_204_NO_CONTENT

        # Verify all service calls
        mock_device_service.generate_pair_code.assert_called_once()
        mock_device_service.get_all.assert_called_once()
        mock_device_service.device_revoke.assert_called_once()