"""
Unit-тесты для модуля apps/gateway/services/device.py

Эти тесты проверяют бизнес-логику DeviceService с мокированием
репозиториев и кеша для изоляции от внешних зависимостей.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status

from apps.common.dao.device import DeviceDomain, DeviceIn, DevicePairDataOut, DeviceUpdate
from apps.common.dao.user import ConfirmDeviceIn, UserDomain
from apps.gateway.services.device import DeviceService


@pytest.fixture
def mock_user_repo():
    """Мок репозитория пользователей"""
    return AsyncMock()


@pytest.fixture
def mock_device_repo():
    """Мок репозитория устройств"""
    return AsyncMock()


@pytest.fixture
def mock_cache():
    """Мок кеша"""
    return AsyncMock()


@pytest.fixture
def device_service(mock_user_repo, mock_device_repo, mock_cache):
    """Фикстура DeviceService с мокированными зависимостями"""
    return DeviceService(
        user_repo=mock_user_repo,
        device_repo=mock_device_repo,
        cache=mock_cache
    )


@pytest.fixture
def sample_user():
    """Пример пользователя"""
    return UserDomain(
        id=1,
        email="test@example.com",
        username="testuser",
        active=True,
        password_hash=b"$2b$12$hashed_password"
    )


@pytest.fixture
def sample_device():
    """Пример устройства"""
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


class TestGetAll:
    """Тесты для метода get_all"""

    @pytest.mark.asyncio
    async def test_get_all_devices_success(
        self, device_service, mock_device_repo, sample_device
    ):
        """Тест успешного получения всех устройств пользователя"""
        # Arrange
        user_id = 1
        devices = [sample_device]
        mock_device_repo.get_all_devices.return_value = devices

        # Act
        result = await device_service.get_all(user_id=user_id)

        # Assert
        assert result == devices
        mock_device_repo.get_all_devices.assert_called_once_with(user_id=user_id)

    @pytest.mark.asyncio
    async def test_get_all_devices_empty(
        self, device_service, mock_device_repo
    ):
        """Тест получения пустого списка устройств"""
        # Arrange
        user_id = 1
        mock_device_repo.get_all_devices.return_value = []

        # Act
        result = await device_service.get_all(user_id=user_id)

        # Assert
        assert result == []
        mock_device_repo.get_all_devices.assert_called_once_with(user_id=user_id)


class TestGeneratePairCode:
    """Тесты для метода generate_pair_code"""

    @pytest.mark.asyncio
    async def test_generate_pair_code_success(
        self, device_service, mock_device_repo, mock_cache
    ):
        """Тест успешной генерации кода сопряжения"""
        # Arrange
        user_id = 1
        device_name = "New Device"
        mock_device_repo.get_by_name.return_value = None
        mock_cache.set_json.return_value = None

        # Act
        with patch.object(DeviceService, '_generate_code', return_value="123456"):
            code = await device_service.generate_pair_code(
                user_id=user_id,
                device_name=device_name
            )

        # Assert
        assert code == "123456"
        assert len(code) == 6
        assert code.isdigit()
        mock_device_repo.get_by_name.assert_called_once_with(device_name=device_name)
        mock_cache.set_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_pair_code_device_exists(
        self, device_service, mock_device_repo, sample_device
    ):
        """Тест генерации кода когда устройство уже существует"""
        # Arrange
        user_id = 1
        device_name = "Existing Device"
        mock_device_repo.get_by_name.return_value = sample_device

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await device_service.generate_pair_code(
                user_id=user_id,
                device_name=device_name
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert exc_info.value.detail == "DEVICE_ALREADY_EXISTS"

    @pytest.mark.asyncio
    async def test_generate_pair_code_cache_storage(
        self, device_service, mock_device_repo, mock_cache
    ):
        """Тест сохранения кода в кеш"""
        # Arrange
        user_id = 1
        device_name = "Test Device"
        mock_device_repo.get_by_name.return_value = None

        # Act
        with patch.object(DeviceService, '_generate_code', return_value="654321"):
            await device_service.generate_pair_code(
                user_id=user_id,
                device_name=device_name
            )

        # Assert
        mock_cache.set_json.assert_called_once()
        call_args = mock_cache.set_json.call_args
        assert call_args.kwargs['key'] == "pair:654321"
        assert call_args.kwargs['data'] == {
            "user_id": user_id,
            "device_name": device_name
        }
        assert call_args.kwargs['ttl'] == 60  # PAIR_CODE_TTL_SECONDS


class TestPairByCode:
    """Тесты для метода pair_by_code"""

    @pytest.mark.asyncio
    async def test_pair_by_code_success(
        self, device_service, mock_cache, mock_device_repo, sample_device
    ):
        """Тест успешного сопряжения по коду"""
        # Arrange
        pair_code = "123456"
        cache_data = {"user_id": 1, "device_name": "Test Device"}
        mock_cache.get_json.return_value = cache_data
        mock_device_repo.upsert_device.return_value = sample_device
        mock_cache.set.return_value = None

        # Act
        with patch.object(DeviceService, '_generate_token', return_value="test_token"):
            with patch('apps.gateway.services.device.hash_value', return_value=b"hashed"):
                result = await device_service.pair_by_code(pair_code=pair_code)

        # Assert
        assert isinstance(result, DevicePairDataOut)
        assert result.device_id == str(sample_device.id)
        assert result.token == "test_token"
        mock_cache.get_json.assert_called_once_with(key=f"pair:{pair_code}")

    @pytest.mark.asyncio
    async def test_pair_by_code_invalid_code(
        self, device_service, mock_cache
    ):
        """Тест сопряжения с невалидным кодом"""
        # Arrange
        pair_code = "invalid"
        mock_cache.get_json.return_value = None

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await device_service.pair_by_code(pair_code=pair_code)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert exc_info.value.detail == "INVALID_CODE"

    @pytest.mark.asyncio
    async def test_pair_by_code_expired_code(
        self, device_service, mock_cache
    ):
        """Тест сопряжения с истекшим кодом (не найден в кеше)"""
        # Arrange
        pair_code = "expired"
        mock_cache.get_json.return_value = None

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await device_service.pair_by_code(pair_code=pair_code)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert exc_info.value.detail == "INVALID_CODE"


class TestPairByCred:
    """Тесты для метода pair_by_cred"""

    @pytest.mark.asyncio
    async def test_pair_by_cred_success(
        self, device_service, mock_user_repo, mock_device_repo, 
        mock_cache, sample_user, sample_device
    ):
        """Тест успешного сопряжения по учетным данным"""
        # Arrange
        confirm_in = ConfirmDeviceIn(
            email="test@example.com",
            password="password123",
            device_name="Test Device"
        )
        mock_user_repo.get_by_email.return_value = sample_user
        mock_device_repo.upsert_device.return_value = sample_device
        mock_cache.set.return_value = None

        # Act
        with patch('apps.gateway.services.device.check_hashed_value', return_value=True):
            with patch.object(DeviceService, '_generate_token', return_value="token"):
                with patch('apps.gateway.services.device.hash_value', return_value=b"hashed"):
                    result = await device_service.pair_by_cred(confirm_in=confirm_in)

        # Assert
        assert isinstance(result, DevicePairDataOut)
        assert result.device_id == str(sample_device.id)
        mock_user_repo.get_by_email.assert_called_once_with(email=confirm_in.email)

    @pytest.mark.asyncio
    async def test_pair_by_cred_no_device_name(self, device_service):
        """Тест сопряжения без имени устройства"""
        # Arrange
        confirm_in = ConfirmDeviceIn(
            email="test@example.com",
            password="password123",
            device_name=""
        )

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await device_service.pair_by_cred(confirm_in=confirm_in)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "UNDEFINED_DEVICE_NAME"

    @pytest.mark.asyncio
    async def test_pair_by_cred_user_not_found(
        self, device_service, mock_user_repo
    ):
        """Тест сопряжения когда пользователь не найден"""
        # Arrange
        confirm_in = ConfirmDeviceIn(
            email="nonexistent@example.com",
            password="password123",
            device_name="Test Device"
        )
        mock_user_repo.get_by_email.return_value = None

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await device_service.pair_by_cred(confirm_in=confirm_in)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "USER_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_pair_by_cred_invalid_password(
        self, device_service, mock_user_repo, sample_user
    ):
        """Тест сопряжения с неверным паролем"""
        # Arrange
        confirm_in = ConfirmDeviceIn(
            email="test@example.com",
            password="wrong_password",
            device_name="Test Device"
        )
        mock_user_repo.get_by_email.return_value = sample_user

        # Act & Assert
        with patch('apps.gateway.services.device.check_hashed_value', return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await device_service.pair_by_cred(confirm_in=confirm_in)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "INVALID_CREDENTIALS"


class TestDeviceRevoke:
    """Тесты для метода device_revoke"""

    @pytest.mark.asyncio
    async def test_device_revoke_success(
        self, device_service, mock_cache, mock_device_repo
    ):
        """Тест успешного отзыва устройства"""
        # Arrange
        device_id = uuid.uuid4()
        mock_cache.delete.return_value = None
        mock_device_repo.delete_device.return_value = None

        # Act
        await device_service.device_revoke(device_id=device_id)

        # Assert
        mock_cache.delete.assert_called_once_with(key=str(device_id))
        mock_device_repo.delete_device.assert_called_once_with(device_id)


class TestProcessToken:
    """Тесты для метода process_token"""

    @pytest.mark.asyncio
    async def test_process_token_from_cache(
        self, device_service, mock_cache, mock_device_repo, sample_device
    ):
        """Тест обработки токена из кеша"""
        # Arrange
        device_id = sample_device.id
        token = "valid_token"
        mock_cache.get.return_value = "hashed_token"
        mock_device_repo.get.return_value = sample_device
        mock_device_repo.update_device.return_value = sample_device

        # Act
        with patch('apps.gateway.services.device.check_hashed_value', return_value=True):
            result = await device_service.process_token(
                device_id=device_id,
                token=token
            )

        # Assert
        assert result == sample_device
        mock_cache.get.assert_called_once()
        mock_device_repo.update_device.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_token_device_not_found(
        self, device_service, mock_cache, mock_device_repo
    ):
        """Тест обработки токена когда устройство не найдено"""
        # Arrange
        device_id = uuid.uuid4()
        token = "token"
        mock_cache.get.return_value = None
        mock_device_repo.get.return_value = None

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await device_service.process_token(
                device_id=device_id,
                token=token
            )

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "TOKEN_EXPIRED"


class TestVerifyRequest:
    """Тесты для метода verify_request"""

    @pytest.mark.asyncio
    async def test_verify_request_success(
        self, device_service, sample_device
    ):
        """Тест успешной верификации запроса"""
        # Arrange
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "Bearer test_token"
        mock_request.cookies.get.return_value = str(sample_device.id)

        # Act
        with patch.object(
            device_service, 
            'process_token', 
            return_value=sample_device
        ) as mock_process:
            result = await device_service.verify_request(request=mock_request)

        # Assert
        assert result == sample_device
        mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_request_missing_token(self, device_service):
        """Тест верификации без токена"""
        # Arrange
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await device_service.verify_request(request=mock_request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Missing token"

    @pytest.mark.asyncio
    async def test_verify_request_invalid_token_format(self, device_service):
        """Тест верификации с неверным форматом токена"""
        # Arrange
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "InvalidFormat token"

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await device_service.verify_request(request=mock_request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Missing token"

    @pytest.mark.asyncio
    async def test_verify_request_missing_device_id(self, device_service):
        """Тест верификации без device_id в cookies"""
        # Arrange
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "Bearer test_token"
        mock_request.cookies.get.return_value = None

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await device_service.verify_request(request=mock_request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Missing device_id"


class TestHelperMethods:
    """Тесты для вспомогательных методов"""

    def test_generate_code_format(self):
        """Тест формата генерируемого кода"""
        # Act
        code = DeviceService._generate_code()

        # Assert
        assert len(code) == 6
        assert code.isdigit()
        assert 0 <= int(code) <= 999999

    def test_generate_token_length(self):
        """Тест длины генерируемого токена"""
        # Act
        token = DeviceService._generate_token()

        # Assert
        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_refresh_token_length(self):
        """Тест длины refresh токена"""
        # Act
        refresh_token = DeviceService._generate_refresh_token()

        # Assert
        assert isinstance(refresh_token, str)
        assert len(refresh_token) > 0

    def test_pair_code_key_format(self):
        """Тест формата ключа для кода сопряжения"""
        # Arrange
        code = "123456"

        # Act
        key = DeviceService.pair_code_key(code)

        # Assert
        assert key == "pair:123456"

    def test_device_key_format_with_uuid(self):
        """Тест формата ключа устройства с UUID"""
        # Arrange
        device_id = uuid.uuid4()

        # Act
        key = DeviceService.device_key(device_id)

        # Assert
        assert key == f"device:{str(device_id)}"

    def test_device_key_format_with_string(self):
        """Тест формата ключа устройства со строкой"""
        # Arrange
        device_id = "test-device-id"

        # Act
        key = DeviceService.device_key(device_id)

        # Assert
        assert key == "device:test-device-id"