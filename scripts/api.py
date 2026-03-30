import logging

import aiohttp

logger = logging.getLogger(__name__)


class NCQQClient:
    """HTTP client for ncqq-manager API.

    持有一个长期复用的 ``aiohttp.ClientSession``，避免每次请求都创建/销毁
    TCP 连接。插件卸载/重载时需调用 :meth:`close` 释放资源。
    """

    def __init__(self, config: dict):
        self.config = config
        self._session: aiohttp.ClientSession | None = None

    # -- session lifecycle --------------------------------------------------

    def _build_session(self) -> aiohttp.ClientSession:
        api_key = self.config.get("api_key", "")
        return aiohttp.ClientSession(
            headers={"x-request-api-key": api_key},
            timeout=aiohttp.ClientTimeout(total=15),
        )

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = self._build_session()
        return self._session

    async def close(self) -> None:
        """关闭底层 HTTP 会话。由插件 terminate() 调用。"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    # -- request ------------------------------------------------------------

    async def make_request(self, method: str, endpoint: str, **kwargs):
        base_url = self.config.get("manager_url", "")
        if base_url:
            base_url = base_url.rstrip("/")
        api_key = self.config.get("api_key", "")

        if not base_url or not api_key:
            raise Exception(
                "Manager URL 或 API Key 未配置，请在 AstrBot 控制台设置面板中完成配置。"
            )

        session = await self._get_session()
        url = f"{base_url}{endpoint}"

        async with session.request(method, url, **kwargs) as resp:
            if resp.status >= 400:
                text_content = await resp.text()
                logger.warning("API %s %s → %s: %s", method, endpoint, resp.status, text_content)
                raise Exception(f"请求失败（HTTP {resp.status}），请稍后重试或联系管理员。")
            return await resp.json()
