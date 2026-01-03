import logging
import urllib.parse
from http import HTTPStatus
from typing import Any

from aiohttp import ClientResponse, ClientSession
from urllib.parse import urljoin
from apps.common.core.protocols.cache import ICache
from apps.common.dao.config import PandoraCredDomain
from apps.gateway.services.pandora_client import excepton
from apps.gateway.services.pandora_client.const import PandoraEndpoints, AuthResponseField

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)


class PandoraSession:
    LOGIN_TIMEOUT_SECONDS: int = 10
    SESSION_MAX_LIFETIME_SECONDS: int = 60 * 60 * 24 * 10
    
    CACHE_PREFIX = "pandora_session:"

    DEFAULT_LANG = "ru"
    SESSION_COOKIE_NAME = "sid"
    SUCCESS_STATUS_MARKERS = ("ok", "success", True)

    DEFAULT_COOKIES = {"lang": DEFAULT_LANG}
    DEFAULT_USER_AGENT = USER_AGENT
    DEFAULT_HEADERS = {"User-Agent": DEFAULT_USER_AGENT}

    def __init__(
        self,
        user_id: int,
        credentials: PandoraCredDomain,
        cache: ICache,
        http_session: ClientSession,
    ) -> None:
        self.user_id = user_id
        self._credentials = credentials
        self._cache = cache
        self._http_session = http_session
        self._session_id: str | None = None

    @property
    def cache_key(self) -> str:
        return f"{self.CACHE_PREFIX}{self.user_id}"

    def _join_url(self, path: str) -> str:
        return urljoin(PandoraEndpoints.base_url, path)

    @staticmethod
    async def _try_get_json_or_text(response: ClientResponse) -> dict | str:
        try:
            return await response.json()
        except Exception:
            return await response.text()

    async def _get_session_id(self) -> str | None:
        if self._session_id:
            return self._session_id

        if session_id := await self._cache.get(self.cache_key):
            self._session_id = session_id
            logger.debug(f"[User:{self.user_id}] session_id loaded from cache")
            return int(self._session_id)  # type: ignore # TODO: проверить типы, в оригинале возвращался str

        return None

    async def _perform_login(self) -> str:
        """
        Выполняет логин и сохраняет session_id.
        """
        payload = {
            "login": self._credentials.email,
            "password": self._credentials.password,
            "lang": self.DEFAULT_LANG,
        }
        
        # SECURITY FIX: Не логируем payload с паролем!
        logger.info(f"[User:{self.user_id}] Logging in to Pandora API...")

        try:
            async with self._http_session.post(
                self._join_url(PandoraEndpoints.login),
                json=payload,
                timeout=self.LOGIN_TIMEOUT_SECONDS,
                headers=self.DEFAULT_HEADERS
            ) as response:
                
                data = await self._try_get_json_or_text(response)
                
                if response.status >= HTTPStatus.BAD_REQUEST:
                    logger.error(f"[User:{self.user_id}] Login failed. HTTP {response.status}: {data!r}")
                    raise excepton.LoginException(f"HTTP {response.status}: {data!r}")

        except Exception as exc:
            logger.exception(f"[User:{self.user_id}] Login transport error")
            raise excepton.LoginException(str(exc))

        # Валидация типа ответа
        if not isinstance(data, dict):
            logger.error(f"[User:{self.user_id}] Login response is not JSON: {data!r}")
            raise excepton.LoginException(f"Invalid response format: {data!r}")

        if data.get(AuthResponseField.STATUS) not in self.SUCCESS_STATUS_MARKERS:
             logger.error(f"[User:{self.user_id}] Login logical error: {data!r}")
             raise excepton.LoginException(f"Login failed: {data}")

        session_id = data.get(AuthResponseField.SESSION_ID)
        if not session_id:
            logger.error(f"[User:{self.user_id}] No session_id in response: {data!r}")
            raise excepton.LoginException("No session_id in login response")

        self._session_id = str(session_id)
        await self._cache.set(self.cache_key, self._session_id, ttl=self.SESSION_MAX_LIFETIME_SECONDS)
        
        logger.info(f"[User:{self.user_id}] Login successful. session_id refreshed.")
        return self._session_id

    async def request_json(self, method: str, path: str, **kwargs: Any) -> Any:
        session_id = await self._get_session_id()
        if not session_id:
            session_id = await self._perform_login()

        response_status, response_data = await self._execute_request(
            method, path, session_id, **kwargs
        )

        if response_status not in (
            HTTPStatus.UNAUTHORIZED, 
            HTTPStatus.FORBIDDEN, 
            HTTPStatus.PROXY_AUTHENTICATION_REQUIRED
        ):
            return response_data

        logger.warning(f"[User:{self.user_id}] Token expired (HTTP {response_status}). Retrying login...")
        
        self._session_id = None
        session_id = await self._perform_login()

        response_status, response_data = await self._execute_request(
            method, path, session_id, **kwargs
        )

        if response_status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
             raise excepton.LoginException(f"UNAUTHORIZED AFTER RELOGIN: HTTP {response_status}, body={response_data}")

        return response_data

    async def _execute_request(self, method: str, path: str, session_id: str, **kwargs: Any) -> tuple[int, Any]:
        headers = self.DEFAULT_HEADERS.copy()
        cookies = self.DEFAULT_COOKIES.copy()
        
        headers.update(kwargs.pop("headers", {}))
        cookies.update(kwargs.pop("cookies", {}))

        if session_id:
            cookies[self.SESSION_COOKIE_NAME] = str(session_id)

        url = self._join_url(path)
        
        logger.debug(f"[User:{self.user_id}] Request {method} {path}")

        async with self._http_session.request(
            method, url, headers=headers, cookies=cookies, **kwargs
        ) as response:
            data = await self._try_get_json_or_text(response)
            return response.status, data
