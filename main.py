import json
import os

from astrbot.api.all import *
from astrbot.core.message.components import At
from astrbot.core.star.star_tools import StarTools

from .scripts.tools_backend import BackendToolsMixin
from .scripts.tools_instance import InstanceToolsMixin


@register(
    "ncqq_manager", "AstrBot", "NapCatQQ 容器控制与后端路由插件", "1.0.0", "repo_url"
)
class NCQQManagerPlugin(Star, InstanceToolsMixin, BackendToolsMixin):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.client = NCQQClient(self.config)
        plugin_data_dir = StarTools.get_data_dir("astrbot_plugin_ncqq_manager")
        self.backends_file = os.path.join(plugin_data_dir, "backends.json")

    async def get_user_mapping(self) -> dict:
        """从原生 SQLite KV 数据库读取用户映射"""
        return await self.get_kv_data("user_mapping", {})

    async def save_user_mapping(self, mapping_dict: dict):
        """存入原生 SQLite KV 数据库"""
        await self.put_kv_data("user_mapping", mapping_dict)

    async def get_backends_registry(self) -> dict:
        """从本地 JSON 文件读取后端配置以便用户手动直接修改"""
        try:
            with open(self.backends_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    async def save_backends_registry(self, registry: dict):
        """将后端的最新模板列表存回 JSON 文件"""
        with open(self.backends_file, "w", encoding="utf-8") as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)

    async def get_allowed_instances(self, sender_id: str) -> list:
        mapping = await self.get_user_mapping()
        return mapping.get(sender_id, {}).get("instances", [])

    def get_first_at_user_id(self, event: AstrMessageEvent) -> str | None:
        for comp in event.get_messages():
            if isinstance(comp, At) and str(comp.qq) != "all":
                return str(comp.qq)
        return None

    async def get_instances_for_user(self, user_id: str) -> list[str]:
        mapping = await self.get_user_mapping()
        return mapping.get(str(user_id), {}).get("instances", [])
