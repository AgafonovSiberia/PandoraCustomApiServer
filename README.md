# PandoraCustomAPIServer

Система управления устройствами сигнализации Pandora через веб-интерфейс и API.

## Описание

PandoraWear — это приложение для управления устройствами сигнализации Pandora. Проект состоит из backend API (FastAPI) и frontend веб-интерфейса (React), позволяющих пользователям регистрироваться, управлять устройствами и отправлять команды на устройства Pandora.

## Архитектура

Проект состоит из следующих компонентов:

### Backend (Gateway)
- **FastAPI** — REST API сервер
- **PostgreSQL** — основная база данных
- **Redis** — кеширование и хранение сессий
- **Kafka** — брокер сообщений (опционально)
- **Alembic** — миграции базы данных
- **Dishka** — dependency injection

### Frontend (Admin UI)
- **React 19** + **TypeScript**
- **Vite** — сборщик и dev-сервер
- **Material-UI (MUI)** — компоненты интерфейса
- **React Router** — маршрутизация
- **React Hook Form** + **Zod** — валидация форм
- **Axios** — HTTP клиент

### Infrastructure
- **Docker Compose** — оркестрация сервисов
- **Traefik** — reverse proxy с автоматическим SSL (Let's Encrypt)
- **PostgreSQL 18** — база данных
- **Redis 8.2** — кеш и сессии
- **Redis Insight** — GUI для Redis

## Структура проекта

```
.
├── apps/
│   ├── gateway/          # Backend API сервис
│   │   ├── api/          # API роуты и схемы
│   │   ├── auth/         # Аутентификация и JWT
│   │   ├── services/     # Бизнес-логика
│   │   └── main.py       # Точка входа
│   ├── admin-ui/         # Frontend приложение
│   │   └── src/
│   │       ├── features/ # Функциональные модули
│   │       ├── layouts/  # Компоненты макетов
│   │       └── api/      # API клиент
│   ├── common/           # Общая логика
│   │   ├── dao/          # Data Access Objects
│   │   ├── repository/ # Репозитории
│   │   ├── services/     # Общие сервисы
│   │   └── infrastructure/
│   │       ├── database/ # Модели и миграции
│   │       ├── cache/    # Реализации кеша
│   │       └── broker/   # Kafka producer/consumer
│   └── bot/              # Telegram бот (опционально)
├── docker-compose.yaml    # Конфигурация Docker Compose
├── pyproject.toml        # Python зависимости
└── Makefile              # Команды для разработки
```

## Функциональность

### Аутентификация
- Регистрация пользователей
- Вход в систему (JWT токены)
- Выход из системы
- Получение информации о текущем пользователе

### Управление устройствами
- Получение списка всех устройств пользователя
- Генерация кода сопряжения
- Сопряжение устройства по коду
- Сопряжение устройства по учетным данным
- Отзыв сопряжения с устройством

### Интеграция с Pandora
- Получение списка доступных устройств Pandora
- Отправка команд на устройства (запуск/остановка двигателя и т.д.)

## Требования

- **Python** >= 3.13
- **Node.js** >= 18 (для frontend)
- **Docker** и **Docker Compose**
- **uv** (Python package manager)

## Установка и запуск

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd PandoraWear
```

### 2. Настройка окружения

Создайте файл `.env` в корне проекта:

```env
# Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=pandora_user
POSTGRES_PASSWORD=pandora_password
POSTGRES_DB=pandora_db

# Security
SECURE_SECRET_KEY=your-secret-key-here
SECURE_JWT_TTL=86400

# Redis
REDIS_URL=redis://redis:6379/0

# Kafka (опционально)
PRODUCER_BOOTSTRAP_SERVERS=kafka:9092
CONSUMER_BOOTSTRAP_SERVERS=kafka:9092
CONSUMER_TOPIC_NAMES=topic1,topic2

# Traefik
SERVER_HOST=your-domain.com
TRAEFIK_ACME_EMAIL=your-email@example.com
```

### 3. Создание Docker сети

```bash
docker network create app
```

### 4. Запуск через Docker Compose

```bash
# Запуск всех сервисов
docker compose up -d --build

# Просмотр логов
docker compose logs -f gateway
docker compose logs -f admin
```

### 5. Запуск через Makefile

```bash
# Сборка и запуск
make build

# Просмотр логов
make log app=gateway

# Остановка
make down
```

## Разработка

### Backend

#### Локальная разработка

```bash
# Установка зависимостей
uv sync

# Запуск миграций
make migration-upgrade

# Создание новой миграции
make migration-create msg="описание миграции"

# Запуск сервера (локально)
cd apps/gateway
uv run fastapi dev main.py
```

#### Отладка

Для отладки используйте `docker-compose.debug.yaml`:

```bash
make build-debug app=gateway
make log-debug app=gateway
```

### Frontend

```bash
cd apps/admin-ui

# Установка зависимостей
pnpm install

# Запуск dev-сервера
pnpm dev

# Сборка для production
pnpm build

# Линтинг
pnpm lint
```

## API Endpoints

### Аутентификация (`/api/users`)

- `POST /api/users/register` — регистрация пользователя
- `POST /api/users/login` — вход в систему
- `POST /api/users/logout` — выход из системы
- `GET /api/users/me` — информация о текущем пользователе

### Устройства (`/api/devices`)

- `GET /api/devices` — список всех устройств
- `POST /api/devices/pairing` — генерация кода сопряжения
- `POST /api/devices/pairing/code/{code}` — сопряжение по коду
- `POST /api/devices/pairing/cred` — сопряжение по учетным данным
- `DELETE /api/devices/{device_id}` — отзыв сопряжения

### Pandora (`/api/alarm`)

- `GET /api/alarm/devices` — список устройств Pandora
- `POST /api/alarm/command` — отправка команды на устройство

## Миграции базы данных

```bash
# Создание новой миграции
make migration-create msg="описание изменений"

# Применение миграций
make migration-upgrade

# Откат последней миграции
make migration-downgrade
```

## Тестирование

```bash
# Запуск тестов
uv run pytest

# Запуск с покрытием
uv run pytest --cov=apps
```

## Структура базы данных

### Основные таблицы

- **users** — пользователи системы
- **devices** — зарегистрированные устройства
- **credentials** — учетные данные Pandora

## Безопасность

- Пароли хешируются с помощью `bcrypt`
- JWT токены для аутентификации
- Токены устройств с ограниченным сроком действия
- CORS настроен для frontend домена
- SSL/TLS через Traefik и Let's Encrypt

## Мониторинг и логи

- Логи контейнеров доступны через `docker compose logs`
- Redis Insight доступен для мониторинга Redis
- Traefik dashboard доступен на порту 8080

## Производственное развертывание

1. Настройте переменные окружения в `.env`
2. Убедитесь, что Docker сеть `app` создана
3. Настройте домен в `SERVER_HOST`
4. Запустите через `docker compose up -d`
5. Traefik автоматически получит SSL сертификат

## Технологии

### Backend
- FastAPI 0.121.2
- SQLAlchemy 2.0.44
- Alembic 1.17.1
- asyncpg 0.30.0
- Redis 7.0.1
- aiokafka 0.12.0
- PyJWT 2.10.1
- bcrypt 5.0.0
- Dishka 1.7.2

### Frontend
- React 19.1.1
- TypeScript 5.9.3
- Vite 7.1.7
- Material-UI 7.3.4
- React Router 7.9.5
- Axios 1.13.1
- Zod 4.1.12

### Infrastructure
- PostgreSQL 18.0
- Redis 8.2
- Traefik v3.1
- Docker Compose

## Лицензия

[Укажите лицензию проекта]

## Контакты

[Укажите контактную информацию]

