import logging
import pathlib
import re

from astrbot.api.all import *
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.core.message.components import At, Reply
from astrbot.core.star.star_tools import StarTools
from astrbot.core.star.filter.command import GreedyStr

from .scripts.api import NCQQClient
from .scripts.health_check import do_health_check
from .scripts.html_renderer import cleanup_renderer, set_bg_dir
from .scripts.tools_admin import AdminToolsMixin
from .scripts.tools_backend import BackendToolsMixin
from .scripts.tools_instance import InstanceToolsMixin
from .scripts.workflows import run_ncqq_workflow, workflow_from_cli, workflow_from_tool

logger = logging.getLogger(__name__)


@register(
    "ncqq_manager", "AstrBot", "NapCatQQ 容器控制与后端路由插件", "2.0.1", "repo_url"
)
class NCQQManagerPlugin(Star, InstanceToolsMixin, BackendToolsMixin, AdminToolsMixin):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.client = NCQQClient(self.config)
        # plugin data 目录（AstrBot 标准持久化路径）
        data_dir = pathlib.Path(StarTools.get_data_dir("astrbot_plugin_ncqq_manager"))
        bg_dir = data_dir / "backgrounds"
        bg_dir.mkdir(parents=True, exist_ok=True)
        set_bg_dir(bg_dir)
        self._health_cron_job = None

    async def initialize(self):
        """Register health check cron job if enabled."""
        await self._register_health_cron()

    async def _register_health_cron(self):
        """(Re)register health check cron job based on current config."""
        # Clean up old job if any
        if self._health_cron_job:
            try:
                await self.context.cron_manager.delete_job(self._health_cron_job.job_id)
            except Exception:
                pass
            self._health_cron_job = None

        if not self.config.get("enable_offline_notify", True):
            return

        interval = max(1, int(self.config.get("health_check_interval", 5)))
        cron_expr = f"*/{interval} * * * *"
        try:
            self._health_cron_job = await self.context.cron_manager.add_basic_job(
                name="ncqq_health_check",
                cron_expression=cron_expr,
                handler=self._run_health_check,
                description=f"NapCatQQ 实例健康检测（每 {interval} 分钟）",
            )
            logger.info("Health check cron registered: %s", cron_expr)
        except Exception as e:
            logger.warning("Failed to register health check cron: %s", e)

    async def _run_health_check(self):
        """Cron callback — delegates to the health_check module."""
        try:
            await do_health_check(self)
        except Exception as e:
            logger.warning("Health check error: %s", e)

    async def terminate(self):
        """插件卸载/重载时清理资源。"""
        if self._health_cron_job:
            try:
                await self.context.cron_manager.delete_job(self._health_cron_job.job_id)
            except Exception:
                pass
        await self.client.close()
        await cleanup_renderer()

    # ------------------------------------------------------------------
    # Unified LLM tool (single narrow-scope entry point)
    # ------------------------------------------------------------------

    @llm_tool(name="ncqq_manager")
    async def ncqq_manager(
        self,
        event: AstrMessageEvent,
        workflow: str,
        target: str = "",
        params: str = "",
    ):
        """Run a compiled internal ncqq workflow.

        Use this tool only for ncqq / NapCatQQ instance and backend management.
        The model must choose one workflow scenario and fill slots; the plugin
        performs permission checks, target resolution, backend alias validation,
        approval routing, and API calls internally.

        Supported workflow scenarios:
            create_instance - create or resume an instance flow; branches on
                existence, permission, binding, backend injection, startup, and QR.
            relogin_instance - check login state; fetch QR code only when needed.
            control_instance - start/stop/restart/pause/unpause/kill with checks.
            connect_backend - validate endpoint alias and inject it into one instance.
            check_instance - admin-only existence/login/resource/log diagnosis.
            list_instances - show instance state and binding overview.
            check_backends - list configured backend endpoints.
            check_manager - admin-only ncqq-manager dependency health check.
            check_botshepherd - admin-only BotShepherd status check.
            check_bot_runtime - admin-only known Bot WS runtime status.
            read_bot_messages - admin-only recent messages for one Bot.
            audit_operations - admin-only recent operation audit summary.
            inspect_resources - admin-only image and node asset overview.
            read_instance_config - admin-only file tree and optional config preview.
            delete_instance - explicit-confirm delete flow.
            review_approvals - admin-only pending approval view.

        Args:
            workflow: One workflow scenario id from the list above.
            target: Target instance name when the scenario works on one instance.
                When omitted and the user has exactly one bound instance, the
                plugin resolves it automatically.
            params: Optional JSON object. Common fields:
                create_instance: {"backend_alias":"alias","bind_qq":"123","qrcode":true}
                control_instance: {"action":"restart","check_after":true}
                connect_backend: {"backend_alias":"alias"}
                read_bot_messages: {"limit":20}
                read_instance_config: {"file_name":"onebot11_uin.json","path":"config"}
                delete_instance: {"confirm":true,"delete_data":false}
        """
        request = workflow_from_tool(workflow, target, params)
        async for r in run_ncqq_workflow(self, event, request):
            yield r

    # ------------------------------------------------------------------
    # Workflow debug entry point: /ncqq <scenario> [args...]
    # ------------------------------------------------------------------

    _NCQQ_HELP = (
        "ncqq workflow 调试入口：\n"
        "ncqq create_instance <实例> [端点别名] - 创建流程\n"
        "ncqq relogin_instance [实例]           - 掉线重登流程\n"
        "ncqq control_instance <动作> [实例]    - 控制流程：start/stop/restart/pause/unpause/kill\n"
        "ncqq connect_backend <端点别名> [实例] - 后端接入流程\n"
        "ncqq check_instance [实例]             - 实例检测流程，管理员限定\n"
        "ncqq list_instances                    - 实例列表流程\n"
        "ncqq check_backends                     - 后端端点检测流程\n"
        "ncqq check_manager                      - 管理器健康检测流程，管理员限定\n"
        "ncqq check_botshepherd                  - BotShepherd 检测流程，管理员限定\n"
        "ncqq check_bot_runtime                  - Bot 运行态检测流程，管理员限定\n"
        "ncqq read_bot_messages <实例> [条数]   - Bot 消息读取流程，管理员限定\n"
        "ncqq audit_operations [条数]            - 操作审计流程，管理员限定\n"
        "ncqq inspect_resources                  - 资源检测流程，管理员限定\n"
        "ncqq read_instance_config <实例> [文件] [路径] - 配置读取流程，管理员限定\n"
        "ncqq delete_instance <实例> confirm [data] - 销毁流程；data 表示同时删数据\n"
        "ncqq review_approvals                   - 审批队列流程"
    )

    @filter.command("ncqq")
    async def cmd_ncqq(self, event: AstrMessageEvent, sub: str = "help", args: GreedyStr = ""):
        if sub in ("help", "h", ""):
            yield event.plain_result(self._NCQQ_HELP)
            return

        request = workflow_from_cli(sub, args)
        if request is None:
            yield event.plain_result(
                f"不支持的 ncqq workflow：{sub}。发送 /ncqq help 查看可用场景。"
            )
            return

        async for r in run_ncqq_workflow(self, event, request):
            yield r

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
        mapping = await self.get_user_mapping()
        if str(sender_id) in self.get_astrbot_admins():
            all_instances: list[str] = []
            for data in mapping.values():
                for inst in data.get("instances", []):
                    if inst not in all_instances:
                        all_instances.append(inst)
            return all_instances
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
    # Approval notice helpers (消除重复的审批通知模板)
    # ------------------------------------------------------------------

    def _approval_notice_single(self, action_label: str, approval_id: str) -> str:
        """生成单条审批通知文本。"""
        admins = self.get_astrbot_admins()
        at_parts = "".join(f"@{a} " for a in admins) if admins else "@管理员 "
        return (
            f"⚠️ {action_label}属于高权限操作，已提交审批。\n"
            f"审批 ID：{approval_id}\n"
            f"请 {at_parts}回复确认（引用本条消息或说'plana 批准 {approval_id}'）。"
        )

    def _approval_notice_batch(
        self, action_label: str, name_id_pairs: list[tuple[str, str]]
    ) -> str:
        """生成批量审批通知文本。name_id_pairs: [(instance_name, approval_id), ...]"""
        admins = self.get_astrbot_admins()
        at_parts = "".join(f"@{a} " for a in admins) if admins else "@管理员 "
        id_lines = "\n".join(f"  {n} → {aid}" for n, aid in name_id_pairs)
        return (
            f"⚠️ {action_label}属于高权限操作，已提交 {len(name_id_pairs)} 条审批。\n"
            f"{id_lines}\n"
            f"请 {at_parts}逐条批准。"
        )

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

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
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
        matches = re.findall(r"\b([A-Z][A-Z0-9]{5})\b", text)

        # 检查是否是拒绝操作
        is_reject = bool(re.search(r"拒绝|不|驳回|取消|REJECT|NO|CANCEL", text))

        # 允许管理员仅回复“同意/批准”等词，自动从引用的消息体中提取审批 ID
        if not matches and (is_reject or re.search(r"同意|批准|通过|确认|APPROVE|YES|OK|PLANA", text)):
            quoted_text = getattr(reply_comp, "message_str", "") or getattr(reply_comp, "text", "")
            if quoted_text:
                matches = re.findall(r"审批\s*ID[：:]?\s*([A-Z0-9]{6})\b", quoted_text.upper())
                if not matches and "审批" in quoted_text:
                    matches = re.findall(r"\b([A-Z][A-Z0-9]{5})\b", quoted_text.upper())

        if not matches:
            return

        from .scripts.approval import get_approval, remove_approval

        for candidate in matches:
            record = await get_approval(self, candidate)
            if record is None:
                continue

            if is_reject:
                await remove_approval(self, candidate)
                event.stop_event()
                yield event.plain_result(
                    f"❌ 已通过引用回复驳回审批 [{candidate}]：{record['description']}"
                )
                return

            action = record["action"]
            params = record["params"]
            result_msg = await self._dispatch_approved_action(action, params)
            await remove_approval(self, candidate)
            event.stop_event()
            yield event.plain_result(
                f"✅ 已通过引用回复批准审批 [{candidate}]：{record['description']}\n"
                f"执行结果：{result_msg}"
            )
            return
