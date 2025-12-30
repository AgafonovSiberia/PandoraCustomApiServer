# Unit-тесты для Device API

Этот каталог содержит unit-тесты для модулей, связанных с управлением устройствами в приложении.

## Структура тестов

### `test_device_routes.py`
Unit-тесты для эндпоинтов API в [`apps/gateway/api/routes/device.py`](../../apps/gateway/api/routes/device.py:1)

**Покрытые эндпоинты:**
- `GET /api/devices` - получение списка устройств
- `POST /api/devices/pairing` - генерация кода сопряжения
- `POST /api/devices/pairing/code/{code}` - сопряжение по коду
- `POST /api/devices/pairing/cred` - сопряжение по учетным данным
- `DELETE /api/devices/{device_id}` - отзыв устройства

**Тестовые классы:**
- `TestGetAllDevices` - тесты получения списка устройств
- `TestPair` - тесты генерации кода сопряжения
- `TestPairConfirm` - тесты сопряжения по коду
- `TestPairConfirmByCred` - тесты сопряжения по учетным данным
- `TestRevoke` - тесты отзыва устройств
- `TestDeviceRouteIntegration` - интеграционные тесты потоков

### `test_device_service.py`
Unit-тесты для бизнес-логики в [`apps/gateway/services/device.py`](../../apps/gateway/services/device.py:21)

**Покрытые методы:**
- `get_all()` - получение всех устройств пользователя
- `generate_pair_code()` - генерация кода сопряжения
- `pair_by_code()` - сопряжение устройства по коду
- `pair_by_cred()` - сопряжение по учетным данным
- `device_revoke()` - отзыв устройства
- `process_token()` - обработка токена устройства
- `verify_request()` - верификация запроса

**Тестовые классы:**
- `TestGetAll` - тесты получения устройств
- `TestGeneratePairCode` - тесты генерации кода
- `TestPairByCode` - тесты сопряжения по коду
- `TestPairByCred` - тесты сопряжения по учетным данным
- `TestDeviceRevoke` - тесты отзыва
- `TestProcessToken` - тесты обработки токенов
- `TestVerifyRequest` - тесты верификации запросов
- `TestHelperMethods` - тесты вспомогательных методов

## Мокирование внешних зависимостей

Все тесты изолированы от внешних зависимостей:

- **Репозитории** (`IUserRepo`, `IDeviceRepo`) - мокируются через `AsyncMock`
- **Кеш** (`ICache`) - мокируется через `AsyncMock`
- **Внешние API** - не вызываются, все взаимодействия мокируются
- **База данных** - не используется в unit-тестах

## Запуск тестов

### Запуск всех unit-тестов
```bash
pytest tests/unit/
```

### Запуск конкретного файла
```bash
pytest tests/unit/test_device_routes.py
pytest tests/unit/test_device_service.py
```

### Запуск конкретного класса тестов
```bash
pytest tests/unit/test_device_routes.py::TestGetAllDevices
pytest tests/unit/test_device_service.py::TestPairByCode
```

### Запуск конкретного теста
```bash
pytest tests/unit/test_device_routes.py::TestGetAllDevices::test_get_all_devices_success
```

### Запуск с покрытием кода
```bash
pytest tests/unit/ --cov=apps/gateway/api/routes/device --cov=apps/gateway/services/device
```

### Запуск с подробным выводом
```bash
pytest tests/unit/ -v
```

### Запуск с выводом print-ов
```bash
pytest tests/unit/ -s
```

## Фикстуры

### Общие фикстуры

- `mock_auth_user` - мокированный аутентифицированный пользователь
- `mock_device_service` - мокированный DeviceService
- `mock_user_repo` - мокированный репозиторий пользователей
- `mock_device_repo` - мокированный репозиторий устройств
- `mock_cache` - мокированный кеш
- `sample_device` - пример устройства для тестов
- `sample_devices` - список устройств для тестов
- `sample_user` - пример пользователя для тестов

## Покрытие тестами

Тесты покрывают следующие сценарии:

### Успешные сценарии
- ✅ Получение списка устройств
- ✅ Генерация кода сопряжения
- ✅ Сопряжение устройства по коду
- ✅ Сопряжение устройства по учетным данным
- ✅ Отзыв устройства
- ✅ Обработка токенов из кеша
- ✅ Верификация запросов

### Сценарии ошибок
- ❌ Устройство с таким именем уже существует
- ❌ Невалидный код сопряжения
- ❌ Истекший код сопряжения
- ❌ Пользователь не найден
- ❌ Неверный пароль
- ❌ Отсутствует имя устройства
- ❌ Устройство не найдено
- ❌ Отсутствует токен авторизации
- ❌ Неверный формат токена
- ❌ Отсутствует device_id в cookies
- ❌ Истекший токен устройства

### Граничные случаи
- 🔄 Пустой список устройств
- 🔄 Полный жизненный цикл устройства
- 🔄 Обработка токенов не из кеша
- 🔄 Генерация различных типов токенов

## Примеры использования

### Пример теста с мокированием
```python
@pytest.mark.asyncio
async def test_get_all_devices_success(
    mock_device_service, mock_auth_user, sample_devices
):
    # Arrange - настройка моков
    mock_device_service.get_all.return_value = sample_devices

    # Act - выполнение тестируемого кода
    result = await get_all_devices(
        auth_user=mock_auth_user,
        device_service=mock_device_service
    )

    # Assert - проверка результатов
    assert result == sample_devices
    mock_device_service.get_all.assert_called_once_with(user_id=mock_auth_user.id)
```

### Пример теста с исключением
```python
@pytest.mark.asyncio
async def test_pair_device_already_exists(
    mock_device_service, mock_auth_user
):
    # Arrange
    device_data = DeviceRegData(name="Existing Device")
    mock_device_service.generate_pair_code.side_effect = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="DEVICE_ALREADY_EXISTS"
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await pair(
            device_data=device_data,
            auth_user=mock_auth_user,
            device_service=mock_device_service
        )

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc_info.value.detail == "DEVICE_ALREADY_EXISTS"
```

## Зависимости

Для запуска тестов требуются следующие пакеты:
- `pytest` - фреймворк для тестирования
- `pytest-asyncio` - поддержка async/await в pytest
- `pytest-mock` - расширение для мокирования (опционально)
- `pytest-cov` - измерение покрытия кода (опционально)

## Интеграция с CI/CD

Тесты можно интегрировать в CI/CD пайплайн:

```yaml
# Пример для GitHub Actions
- name: Run unit tests
  run: |
    pytest tests/unit/ -v --cov=apps/gateway --cov-report=xml
```

## Рекомендации

1. **Изоляция тестов** - каждый тест должен быть независимым
2. **Мокирование** - все внешние зависимости должны быть замокированы
3. **Читаемость** - используйте паттерн Arrange-Act-Assert
4. **Покрытие** - стремитесь к покрытию всех веток кода
5. **Документация** - добавляйте docstring к тестам для пояснения