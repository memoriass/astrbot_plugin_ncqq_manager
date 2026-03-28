import aiohttp


class NCQQClient:
    def __init__(self, config: dict):
        self.config = config

    async def make_request(self, method, endpoint, **kwargs):
        base_url = self.config.get("manager_url", "")
        if base_url:
            base_url = base_url.rstrip("/")
        api_key = self.config.get("api_key", "")

        if not base_url or not api_key:
            raise Exception(
                "Manager URL 或 API Key 未配置，请在 AstrBot 控制台设置面板中完成配置。"
            )

        headers = {"x-request-api-key": api_key}
        url = f"{base_url}{endpoint}"

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.request(
                method, url, timeout=aiohttp.ClientTimeout(total=15), **kwargs
            ) as resp:
                if resp.status >= 400:
                    text_content = await resp.text()
                    raise Exception(f"API Error: {resp.status} - {text_content}")
                return await resp.json()
