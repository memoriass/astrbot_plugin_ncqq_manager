import json
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

    async def stream_events(self, instance_name: str, timeout: int = 60) -> list[dict]:
        """短时订阅单实例 SSE 事件流。"""
        base_url = self.config.get("manager_url", "")
        if base_url:
            base_url = base_url.rstrip("/")
        api_key = self.config.get("api_key", "")

        if not base_url or not api_key:
            raise Exception(
                "Manager URL 或 API Key 未配置，请在 AstrBot 控制台设置面板中完成配置。"
            )

        session = await self._get_session()
        url = f"{base_url}/api/containers/{instance_name}/events"
        started = False
        events: list[dict] = []
        stream_timeout = aiohttp.ClientTimeout(total=None, sock_read=timeout + 5)

        async with session.get(
            url,
            headers={"Accept": "text/event-stream"},
            timeout=stream_timeout,
        ) as resp:
            if resp.status >= 400:
                text_content = await resp.text()
                logger.warning(
                    "SSE %s → %s: %s", url, resp.status, text_content
                )
                raise Exception(f"SSE 请求失败（HTTP {resp.status}）。")

            async with aiohttp.ClientTimeout(total=timeout):
                pass

            buffer: list[str] = []
            loop = aiohttp.helpers.get_running_loop()
            deadline = loop.time() + timeout
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                try:
                    raw = await resp.content.readline()
                except Exception as e:
                    logger.warning("SSE 读取异常 %s: %s", instance_name, e)
                    break
                if raw == b"":
                    break
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    payload = self._parse_sse_payload(buffer)
                    buffer.clear()
                    if payload:
                        events.append(payload)
                        started = True
                    continue
                if line.startswith(":"):
                    continue
                buffer.append(line)
                if started and len(events) >= 8:
                    break

            payload = self._parse_sse_payload(buffer)
            if payload:
                events.append(payload)
        return events

    @staticmethod
    def _parse_sse_payload(lines: list[str]) -> dict | None:
        if not lines:
            return None
        data_lines: list[str] = []
        event_name = "message"
        for line in lines:
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip() or "message"
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].strip())
        if not data_lines:
            return None
        raw = "\n".join(data_lines)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("SSE payload 解析失败: %s", raw)
            return None
        if isinstance(payload, dict):
            payload.setdefault("event", event_name)
            return payload
        return {"event": event_name, "data": payload}
