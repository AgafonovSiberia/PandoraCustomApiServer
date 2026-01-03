from aiohttp import TCPConnector, ClientSession, DummyCookieJar, ClientTimeout
from dishka import (
    AsyncContainer,
    Scope,
    make_async_container,
    provide,
)
from dishka.integrations.fastapi import FastapiProvider
from fastapi import Request
from sqlalchemy.ext.asyncio.session import AsyncSession

from apps.common.config import (
    ConsumerSettings,
    DatabaseSettings,
    ProducerSettings,
    RedisSettings,
    SecureSettings,
)
from apps.common.core.protocols.broker.consumer import IConsumer, IConsumerSettings
from apps.common.core.protocols.broker.producer import IProducer, IProducerSettings
from apps.common.core.protocols.cache import ICache
from apps.common.core.protocols.repository import IConfigRepo, IDeviceRepo, IUserRepo
from apps.common.dao.device import AuthDevice
from apps.common.dao.user import AuthUser
from apps.common.infrastructure.broker.consumer import KafkaAsyncConsumer
from apps.common.infrastructure.broker.producer import KafkaAsyncProducer
from apps.common.infrastructure.cache.redis import RedisCache
from apps.common.infrastructure.database.database import DatabaseCore
from apps.common.repository.config import ConfigRepo
from apps.common.repository.device import DeviceRepo
from apps.common.repository.user import UserRepo
from apps.gateway.services.auth import AuthService
from apps.gateway.services.config import ConfigService
from apps.gateway.services.device import DeviceService
from apps.gateway.services.pandora import PandoraService
from apps.gateway.services.pandora_client.client import PandoraClient, resolve_pandora_client
from apps.gateway.services.user import UserService
from apps.gateway.api.deps import authenticate_device_from_request


class DatabaseProvider(FastapiProvider):
    @provide(scope=Scope.APP)
    async def database_core(self) -> DatabaseCore:
        db_settings = DatabaseSettings()
        return DatabaseCore(db_settings)

    @provide(scope=Scope.REQUEST, provides=AsyncSession)
    async def db_session(self, database: DatabaseCore) -> AsyncGenerator[AsyncSession, Any]:
        async with database.session_factory()() as session:
            async with session.begin():
                yield session


class ConfigProvider(FastapiProvider):
    @provide(scope=Scope.APP)
    async def producer_settings(self) -> IProducerSettings:
        return ProducerSettings()

    @provide(scope=Scope.APP)
    async def consumer_settings(self) -> IConsumerSettings:
        return ConsumerSettings()

    @provide(scope=Scope.APP)
    async def secure_settings(self) -> SecureSettings:
        return SecureSettings()


class InfraProvider(FastapiProvider):
    @provide(scope=Scope.APP)
    async def cache(self) -> ICache:
        settings = RedisSettings()
        return RedisCache(url=settings.redis_url, prefix="api")

    @provide(scope=Scope.APP)
    async def producer(self, settings: IProducerSettings) -> IProducer:
        return KafkaAsyncProducer(settings)

    @provide(scope=Scope.APP)
    async def consumer(self, settings: IConsumerSettings) -> IConsumer:
        return KafkaAsyncConsumer(settings)

    @provide(scope=Scope.APP)
    async def tcp_connector(self) -> TCPConnector:
        return TCPConnector(limit=1000, limit_per_host=0, ttl_dns_cache=300, enable_cleanup_closed=True)

    @provide(scope=Scope.APP)
    async def http_session(self, connector: TCPConnector) -> AsyncGenerator[ClientSession, Any]:
        timeout = ClientTimeout(total=15)
        async with ClientSession(connector=connector, cookie_jar=DummyCookieJar(), timeout=timeout) as session:
            yield session


class RepoProvider(FastapiProvider):
    @provide(scope=Scope.REQUEST)
    async def user_repo(self, session: AsyncSession) -> IUserRepo:
        return UserRepo(session=session)

    @provide(scope=Scope.REQUEST)
    async def device_repo(self, session: AsyncSession) -> IDeviceRepo:
        return DeviceRepo(session=session)

    @provide(scope=Scope.REQUEST)
    async def config_repo(self, session: AsyncSession) -> IConfigRepo:
        return ConfigRepo(session=session)


class ServiceProvider(FastapiProvider):
    @provide(scope=Scope.REQUEST)
    async def user_service(self, user_repo: IUserRepo, cache: ICache, auth_settings: SecureSettings) -> UserService:
        return UserService(user_repo=user_repo, cache=cache, auth_settings=auth_settings)

    @provide(scope=Scope.REQUEST)
    async def auth_service(self, user_repo: IUserRepo, cache: ICache, auth_settings: SecureSettings) -> AuthService:
        return AuthService(user_repo=user_repo, cache=cache, auth_settings=auth_settings)

    @provide(scope=Scope.REQUEST)
    async def auth_user_guard(self, request: Request, auth_service: AuthService) -> AuthUser:
        token, user_id = await auth_service.verify_request(request)
        return AuthUser(id=user_id, token=token)

    @provide(scope=Scope.REQUEST)
    async def auth_device_guard(self, request: Request, device_service: DeviceService) -> AuthDevice:
        return await authenticate_device_from_request(request, device_service)

    @provide(scope=Scope.REQUEST)
    async def device_service(self, user_repo: IUserRepo, device_repo: IDeviceRepo, cache: ICache) -> DeviceService:
        return DeviceService(user_repo=user_repo, device_repo=device_repo, cache=cache)

    @provide(scope=Scope.REQUEST)
    async def config_service(self, user_repo: IUserRepo, config_repo: IConfigRepo, cache: ICache) -> ConfigService:
        return ConfigService(user_repo=user_repo, config_repo=config_repo, cache=cache)

    @provide(scope=Scope.REQUEST)
    async def pandora_client(
        self,
        auth_device: AuthDevice,
        config_service: ConfigService,
        cache: ICache,
        http_session: ClientSession,
    ) -> PandoraClient:
        pandora_cred = await config_service.get_pandora_cred(user_id=auth_device.user_id)
        return await resolve_pandora_client(
            user_id=auth_device.user_id, pandora_cred=pandora_cred, cache=cache, http_session=http_session
        )

    @provide(scope=Scope.REQUEST)
    async def engine_service(self, user_repo: IUserRepo, pandora_client: PandoraClient) -> PandoraService:
        return PandoraService(user_repo=user_repo, pandora_client=pandora_client)


def create_container() -> AsyncContainer:
    container = make_async_container(
        RepoProvider(), ConfigProvider(), DatabaseProvider(), InfraProvider(), ServiceProvider()
    )
    return container
