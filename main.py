import functools
import re

from astrbot.api.all import *
from astrbot.core.message.components import At, Reply
from astrbot.core.provider.register import llm_tools
from astrbot.core.star.star_tools import StarTools

from .scripts.api import NCQQClient
from .scripts.tools_admin import AdminToolsMixin
from .scripts.tools_backend import BackendToolsMixin
from .scripts.tools_instance import InstanceToolsMixin


@register(
    "ncqq_manager", "AstrBot", "NapCatQQ 容器控制与后端路由插件", "1.0.0", "repo_url"
)
class NCQQManagerPlugin(Star, InstanceToolsMixin, BackendToolsMixin, AdminToolsMixin):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.client = NCQQClient(self.config)
        StarTools.get_data_dir("astrbot_plugin_ncqq_manager")

    async def initialize(self):
        """Bind Mixin llm_tool handlers to this instance.

        AstrBot only auto-binds handlers whose __module__ matches the main
        plugin file path. Methods defined in Mixin sub-files have a different
        __module__, so they are skipped. We manually bind them here.
        """
        plugin_pkg = __name__.rsplit(".", 1)[0]
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

    # ------------------------------------------------------------------
    # User mapping KV helpers
    # ------------------------------------------------------------------

    async def get_user_mapping(self) -> dict:
        """从原生 SQLite KV 数据库读取用户映射"""
        return await self.get_kv_data("user_mapping", {})

    async def save_user_mapping(self, mapping_dict: dict):
        """存入原生 SQLite KV 数据库"""
        await self.put_kv_data("user_mapping", mapping_dict)

    def get_astrbot_admins(self) -> list[str]:
        """Return AstrBot global admin QQ list from config admins_id."""
        return [str(a) for a in self.context.get_config().get("admins_id", [])]

    async def get_allowed_instances(self, sender_id: str) -> list:
        """Return instances for sender_id.

        AstrBot admins (admins_id) are treated as super-owners and have
        access to all instances across all bound users.
        """
        if str(sender_id) in self.get_astrbot_admins():
            mapping = await self.get_user_mapping()
            all_instances: list[str] = []
            for data in mapping.values():
                for inst in data.get("instances", []):
                    if inst not in all_instances:
                        all_instances.append(inst)
            return all_instances
        mapping = await self.get_user_mapping()
        return mapping.get(str(sender_id), {}).get("instances", [])

    def get_first_at_user_id(self, event: AstrMessageEvent) -> str | None:
        for comp in event.get_messages():
            if isinstance(comp, At) and str(comp.qq) != "all":
                return str(comp.qq)
        return None

    async def get_instances_for_user(self, user_id: str) -> list[str]:
        mapping = await self.get_user_mapping()
        return mapping.get(str(user_id), {}).get("instances", [])

    # ------------------------------------------------------------------
    # Pending approvals KV helpers
    # ------------------------------------------------------------------

    async def get_pending_approvals(self) -> dict:
        return await self.get_kv_data("pending_approvals", {})

    async def save_pending_approvals(self, approvals: dict) -> None:
        await self.put_kv_data("pending_approvals", approvals)

    # ------------------------------------------------------------------
    # Reply-based approval shortcut listener
    # ------------------------------------------------------------------

    @filter.event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_group_message_reply(self, event: AstrMessageEvent):
        """Detect AstrBot admin quoting an approval notice and auto-approve it."""
        # event.role may not be set for non-wake messages (waking_check is skipped),
        # so compare directly against admins_id config instead of event.is_admin().
        if str(event.get_sender_id()) not in self.get_astrbot_admins():
            return

        reply_comp = next(
            (c for c in event.get_messages() if isinstance(c, Reply)), None
        )
        if reply_comp is None:
            return

        text = event.message_str.strip().upper()
        matches = re.findall(r"\b([A-Z0-9]{6})\b", text)
        if not matches:
            return

        from .scripts.approval import get_approval, remove_approval

        for candidate in matches:
            record = await get_approval(self, candidate)
            if record is None:
                continue
            action = record["action"]
            params = record["params"]
            result_msg = await self._dispatch_approved_action(action, params)
            await remove_approval(self, candidate)
            yield event.plain_result(
                f"✅ 已通过引用回复批准审批 [{candidate}]：{record['description']}\n"
                f"执行结果：{result_msg}"
            )
            return
