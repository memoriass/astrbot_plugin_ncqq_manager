import functools

from astrbot.api.all import *
from astrbot.core.message.components import At
from astrbot.core.provider.register import llm_tools
from astrbot.core.star.star_tools import StarTools

from .scripts.api import NCQQClient
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
        # Keep data dir for future use (user mapping, etc.)
        StarTools.get_data_dir("astrbot_plugin_ncqq_manager")

    async def initialize(self):
        """Bind Mixin llm_tool handlers to this instance.

        AstrBot only auto-binds handlers whose __module__ matches the main
        plugin file path. Methods defined in Mixin sub-files have a different
        __module__, so they are skipped. We manually bind them here.
        """
        plugin_pkg = __name__.rsplit(".", 1)[0]  # data.plugins.astrbot_plugin_ncqq_manager
        for func_tool in llm_tools.func_list:
            h = func_tool.handler
            if (
                h is not None
                and hasattr(h, "__module__")
                and not isinstance(h, functools.partial)
                and h.__module__ != __name__
                and h.__module__.startswith(plugin_pkg)
            ):
                func_tool.handler = functools.partial(h, self)
                func_tool.handler_module_path = __name__

    async def get_user_mapping(self) -> dict:
        """从原生 SQLite KV 数据库读取用户映射"""
        return await self.get_kv_data("user_mapping", {})

    async def save_user_mapping(self, mapping_dict: dict):
        """存入原生 SQLite KV 数据库"""
        await self.put_kv_data("user_mapping", mapping_dict)

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
