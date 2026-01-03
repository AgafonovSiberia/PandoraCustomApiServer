
from apps.common.core.protocols.cache import ICache
from apps.common.dao.config import PandoraCredDomain
from apps.gateway.services.pandora_client.const import PandoraEndpoints, PandoraCommand
from apps.gateway.services.pandora_client.session import PandoraSession
from aiohttp import ClientSession


class PandoraClient:
    TIMESTAMP_LATEST = -1

    def __init__(self, session: PandoraSession):
        self._session = session

    async def get_all_devices(self) -> dict:
        return await self._session.request_json(method="GET", path=PandoraEndpoints.devices)

    async def get_updates(self) -> dict:
        return await self._session.request_json(method="GET", path=PandoraEndpoints.update, params={"ts": self.TIMESTAMP_LATEST})

    async def run_command(
        self,
        pandora_command: PandoraCommand,
        device_id: int,
    ) -> dict:
        return await self._session.request_json(
            method="POST", path=PandoraEndpoints.command, data={"id": device_id, "command": pandora_command.value}
        )


async def resolve_pandora_client(
    user_id: int, pandora_cred: PandoraCredDomain, cache: ICache, http_session: ClientSession
) -> PandoraClient:
    session = PandoraSession(credentials=pandora_cred, user_id=user_id, cache=cache, http_session=http_session)
    return PandoraClient(session=session)
