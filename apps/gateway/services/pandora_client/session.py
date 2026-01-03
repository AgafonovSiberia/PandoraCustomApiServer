import logging
from typing import Any

from aiohttp import ClientSession
from aiohttp.http import HTTPStatus

from apps.common.core.protocols.cache import ICache
from apps.common.dao.config import PandoraCredDomain
from apps.gateway.services.pandora_client import excepton
from apps.gateway.services.pandora_client.const import URL, AuthResponseField

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)


class PandoraSession:
    LOGIN_TIMEOUT: int = 10
    SESSION_MAX_LIFETIME: int = 60 * 60 * 24 * 10
    
    CACHE_PREFIX = "pandora_session:"

    COOKIES_TEMPLATE = {"lang": "ru"}
    HEADERS_TEMPLATE = {"User-Agent": USER_AGENT}

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
        self._session_id = None
        self.http_session: ClientSession | None = http_session

    @property
    def cache_key(self) -> str:
        return f"{self.CACHE_PREFIX}{self.user_id}"

    async def _get_session_id_from_cache(self) -> str | None:
        session_id = await self._cache.get(self.cache_key)
        return session_id or None

    async def _save_session_id_to_cache(self, session_id: str) -> None:
        await self._cache.set(self.cache_key, session_id, ttl=self.SESSION_MAX_LIFETIME)

    async def _do_login_request(self) -> dict[str, Any]:
        payload = {
            "login": self._credentials.email,
            "password": self._credentials.password,
            "lang": "ru",
        }
        logger.error(f"[_do_login_request] - payload:{payload}")
        try:
            async with ClientSession(base_url=URL.base_url) as session:
                response = await session.post(
                    URL.login, json=payload, timeout=self.LOGIN_TIMEOUT, headers=self.HEADERS_TEMPLATE
                )
                status = response.status
                try:
                    data = await response.json()
                except Exception:
                    data = await response.text()
        except Exception as exc:
            logger.exception("Failed to login to Pandora API")
            raise excepton.LoginException(str(exc))

        if status >= HTTPStatus.BAD_REQUEST:
            logger.error(f"[_do_login_request] - error after login. {status}:{data!r}")
            raise excepton.LoginException(f"HTTP {status}: {data!r}")

        return data

    async def _login_and_save_session_id(self) -> str:
        login_response = await self._do_login_request()

        status_value = login_response.get(AuthResponseField.STATUS)
        if status_value not in ("ok", "success", True):
            logger.error(f"[_login_and_save_session_id] - login failed. {login_response!r}")
            raise excepton.LoginException(f"Login failed: {login_response}")

        session_id = login_response.get(AuthResponseField.SESSION_ID)
        if not session_id:
            logger.error(f"[_login_and_save_session_id] "
                         f"- login response does not contain session_id. {login_response!r}")
            raise excepton.LoginException("Login response does not contain session_id")

        logger.info(f"[_login_and_save_session_id] login success. session_id={session_id}")
        await self._save_session_id_to_cache(session_id=session_id)
        self._session_id = session_id
        return self._session_id

    async def _ensure_session_id(self, *, force: bool = False) -> str:
        if self._session_id and not force:
            logger.info("[ensure_session_id] - session_id received from instance")
            return self._session_id

        if not force and (session_id := await self._get_session_id_from_cache()):
            logger.info("[ensure_session_id] - session_id received from cache")
            self._session_id = session_id
            return self._session_id

        logger.info("[ensure_session_id] - session_id not found in cache")
        return await self._login_and_save_session_id()

    async def _do_request_once(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        cookies: dict[str, str],
        **kwargs: Any,
    ) -> tuple[int, Any]:
        async with ClientSession(base_url=URL.base_url) as session:
            response = await session.request(method, path, headers=headers, cookies=cookies, **kwargs)
            status = response.status
            try:
                data = await response.json()
            except Exception:
                data = await response.text()
        logger.info(f"[_do_request_once] - {method} : {path}")
        return status, data

    @staticmethod
    async def inject_session_id(cookies: dict, headers: dict, session_id: str) -> None:
        if session_id:
            cookies.setdefault("sid", session_id)

    async def _get_cookies_and_headers(self) -> tuple[dict[str, str], dict[str, str]]:
        return self.COOKIES_TEMPLATE.copy(), self.HEADERS_TEMPLATE.copy()

    async def request_json(self, method: str, path: str, **kwargs: Any) -> Any:
        session_id = await self._ensure_session_id(force=False)

        cookies, headers = await self._get_cookies_and_headers()
        if session_id:
            await self.inject_session_id(cookies=cookies, headers=headers, session_id=session_id)

        response_status, response_data = await self._do_request_once(
            method=method,
            path=path,
            headers=headers,
            cookies=cookies,
            **kwargs,
        )

        if response_status not in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN, HTTPStatus.PROXY_AUTHENTICATION_REQUIRED):
            return response_data

        return await self.request_json_with_relogin(method=method, path=path, **kwargs)

    async def request_json_with_relogin(self, method: str, path: str, **kwargs: Any) -> Any:
        session_id = await self._ensure_session_id(force=True)
        if not session_id:
            logger.error("[request_json_with_relogin] - relogin failed")
            raise excepton.LoginException("RELOGIN FAILED")

        cookies, headers = await self._get_cookies_and_headers()
        if session_id:
            await self.inject_session_id(cookies=cookies, headers=headers, session_id=session_id)

        response_status, response_data = await self._do_request_once(
            method=method,
            path=path,
            headers=headers,
            cookies=cookies,
            **kwargs,
        )

        if response_status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            self._session_id = None
            logger.error("[request_json_with_relogin] - error after success relogin")
            raise excepton.LoginException(f"UNAUTORIZED AFTER RELOGIN: status={response_status}, body={response_data}")

        return response_data
