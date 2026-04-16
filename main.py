import json
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

logger = logging.getLogger(__name__)


@register(
    "ncqq_manager", "AstrBot", "NapCatQQ 容器控制与后端路由插件", "2.0.0", "repo_url"
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
        command: str,
        target: str = "",
        extra: str = "",
    ):
        """管理 NapCatQQ 机器人实例（Docker 容器）。当用户提及 ncqq、NapCat、QQ机器人、机器人实例、bot实例、容器实例 的查询或操控时调用。与系统状态、skill管理、其他插件无关。若用户未指定实例名（target 为空），系统会自动使用该用户唯一绑定的实例。

        Args:
            command (string): 操作指令，必须是以下之一：
                "list"             — 列出所有实例及运行状态。
                "login"            — 检查实例登录状态（target=实例名，逗号分隔多个）。
                "monitor"          — 查看实例资源占用（target=实例名，仅管理员）。
                "logs"             — 查看实例日志（target=实例名，仅管理员）。
                "assets"           — 列出镜像与节点资产（仅管理员）。
                "config"           — 读取实例配置文件（target=实例名，extra可含file_name）。
                "files"            — 列出实例文件目录（target=实例名，extra可含path）。
                "qrcode"           — 获取登录二维码（target=实例名）。
                "start"            — 启动实例（target=实例名）。
                "stop"             — 停止实例（target=实例名）。
                "restart"          — 重启实例（target=实例名）。
                "pause"            — 暂停实例（target=实例名）。
                "unpause"          — 恢复实例（target=实例名）。
                "kill"             — 强杀实例（target=实例名）。
                "delete"           — 销毁实例（target=实例名，extra可含delete_data布尔值）。
                "create"           — 创建新实例（target=实例名，逗号分隔多个）。
                "switch"           — 重置登录账号（target=实例名）。
                "write_config"     — 覆写配置文件（target=实例名，extra含file_name和file_content）。
                "bind"             — 绑定实例到@用户（target=实例名，extra可含nickname）。
                "unbind"           — 解绑实例（target=实例名）。
                "bindings"         — 查看所有绑定关系。
                "nickname"         — 设置用户昵称（extra含qq_id和nickname）。
                "backend_add"      — 添加后端端点（target=别名，extra含url和可选token）。
                "backend_remove"   — 删除后端端点（target=别名）。
                "backend_inject"   — 注入后端到实例（target=别名，extra可含instance_names或instance_keyword）。
                "approval_list"    — 查看待审批请求。
                "approval_approve" — 批准审批（target=审批ID）。
                "approval_reject"  — 拒绝审批（target=审批ID，extra可含reason）。
            target (string): 主要目标。实例操作为实例名，审批操作为审批ID，后端操作为别名。逗号分隔支持多个。
            extra (string): 附加参数，JSON格式。可选键：file_name, file_content, path, delete_data, url, token, nickname, instance_names, instance_keyword, reason, qq_id。
        """
        params = {}
        if extra:
            try:
                params = json.loads(extra)
            except (json.JSONDecodeError, TypeError):
                pass

        # --- auto-resolve target when user has exactly one bound instance ---
        _needs_target = {
            "login", "monitor", "logs", "config", "files", "qrcode",
            "start", "stop", "restart", "pause", "unpause", "kill",
            "delete", "switch", "write_config",
        }
        if command in _needs_target and not target.strip():
            sender_id = str(event.get_sender_id())
            bound = await self.get_allowed_instances(sender_id)
            if len(bound) == 1:
                target = bound[0]
            elif len(bound) > 1:
                yield event.plain_result(
                    f"你绑定了 {len(bound)} 个实例，请指定目标实例名：{'、'.join(bound)}"
                )
                return
            # bound == 0 → 继续走原逻辑，由子方法报错

        # --- query commands ---
        if command == "list":
            async for r in self.ncqq_query(event, query="instances"):
                yield r
            return
        if command in ("login", "monitor", "logs", "config", "files"):
            async for r in self.ncqq_query(
                event,
                query=command,
                instance_names=target,
                file_name=params.get("file_name", "onebot11_uin.json"),
                path=params.get("path", ""),
            ):
                yield r
            return
        if command == "assets":
            async for r in self.ncqq_query(event, query="assets"):
                yield r
            return
        # --- qrcode ---
        if command == "qrcode":
            async for r in self.ncqq_qrcode(event, instance_name=target):
                yield r
            return
        # --- action commands ---
        _actions = {
            "start", "stop", "restart", "pause", "unpause", "kill",
            "delete", "create", "switch", "write_config",
        }
        if command in _actions:
            async for r in self.ncqq_action(
                event,
                action=command,
                instance_names=target,
                delete_data=params.get("delete_data", False),
                file_name=params.get("file_name", ""),
                file_content=params.get("file_content", ""),
            ):
                yield r
            return
        # --- binding commands ---
        if command in ("bind", "unbind", "bindings", "nickname"):
            action = "list" if command == "bindings" else command
            async for r in self.ncqq_binding(
                event,
                action=action,
                instance_names=target,
                qq_id=params.get("qq_id", ""),
                nickname=params.get("nickname", ""),
            ):
                yield r
            return
        # --- backend commands ---
        if command.startswith("backend_"):
            action = command[len("backend_"):]
            async for r in self.ncqq_backend(
                event,
                action=action,
                alias=target,
                url=params.get("url", ""),
                token=params.get("token", ""),
                instance_names=params.get("instance_names", ""),
                instance_keyword=params.get("instance_keyword", ""),
            ):
                yield r
            return
        # --- approval commands ---
        if command.startswith("approval_"):
            action = command[len("approval_"):]
            async for r in self.ncqq_approval(
                event,
                action=action,
                approval_id=target,
                reason=params.get("reason", ""),
            ):
                yield r
            return
        yield event.plain_result(
            f"未知命令 '{command}'。支持：list / login / qrcode / start / stop / restart / "
            f"create / delete / bind / unbind / bindings / backend_add / approval_list 等。"
        )

    # ------------------------------------------------------------------
    # Fixed command entry point: /ncqq <sub> [args...]
    # ------------------------------------------------------------------

    _NCQQ_HELP = (
        "NapCatQQ 管理命令（绑定单实例时可省略名称）：\n"
        "ncqq list                      — 列出所有实例\n"
        "ncqq login [名称]              — 查看登录状态\n"
        "ncqq qrcode [名称]             — 获取登录二维码\n"
        "ncqq start|stop|restart [名称] — 生命周期管理\n"
        "ncqq create <名称>             — 创建实例\n"
        "ncqq delete [名称] [purge]     — 销毁实例\n"
        "ncqq switch [名称]             — 重置账号\n"
        "ncqq monitor [名称]            — 资源监控（管理员）\n"
        "ncqq logs [名称]               — 查看日志（管理员）\n"
        "ncqq config [名称] [文件名]    — 读取配置（管理员）\n"
        "ncqq files [名称] [路径]       — 列出文件（管理员）\n"
        "ncqq assets                    — 查看资产（管理员）\n"
        "ncqq bind <实例名>             — 绑定实例（@目标用户）\n"
        "ncqq unbind <实例名>           — 解绑实例（@目标用户）\n"
        "ncqq bindings                  — 查看绑定\n"
        "ncqq nick <QQ号> <昵称>        — 设置昵称\n"
        "ncqq backend add <别名> <地址> — 添加后端\n"
        "ncqq backend remove <别名>     — 删除后端\n"
        "ncqq backend inject <别名>     — 注入后端到实例\n"
        "ncqq approvals                 — 查看审批\n"
        "ncqq approve <ID>              — 批准审批\n"
        "ncqq reject <ID> [原因]        — 拒绝审批"
    )

    @filter.command("ncqq")
    async def cmd_ncqq(self, event: AstrMessageEvent, sub: str = "help", args: GreedyStr = ""):
        parts = str(args).split() if args else []

        if sub in ("help", "h"):
            yield event.plain_result(self._NCQQ_HELP)
            return

        # --- auto-resolve instance name for commands that need one ---
        _needs_inst = {
            "login", "monitor", "logs", "config", "files", "qrcode",
            "start", "stop", "restart", "pause", "unpause", "kill",
            "delete", "switch",
        }
        args_str = str(args).strip()
        if sub in _needs_inst and not args_str:
            sender_id = str(event.get_sender_id())
            bound = await self.get_allowed_instances(sender_id)
            if len(bound) == 1:
                args_str = bound[0]
                parts = [args_str]
            elif len(bound) > 1:
                yield event.plain_result(
                    f"你绑定了 {len(bound)} 个实例，请指定目标实例名：{'、'.join(bound)}"
                )
                return
            # bound == 0 → 继续走原逻辑，由子方法报错

        # --- query ---
        if sub == "list":
            async for r in self.ncqq_query(event, query="instances"):
                yield r
            return
        if sub == "login":
            async for r in self.ncqq_query(event, query="login", instance_names=args_str):
                yield r
            return
        if sub in ("monitor", "logs"):
            name = parts[0] if parts else args_str
            async for r in self.ncqq_query(event, query=sub, instance_names=name):
                yield r
            return
        if sub == "assets":
            async for r in self.ncqq_query(event, query="assets"):
                yield r
            return
        if sub == "config":
            name = parts[0] if parts else args_str
            file_name = parts[1] if len(parts) > 1 else "onebot11_uin.json"
            async for r in self.ncqq_query(event, query="config", instance_names=name, file_name=file_name):
                yield r
            return
        if sub == "files":
            name = parts[0] if parts else args_str
            path = parts[1] if len(parts) > 1 else ""
            async for r in self.ncqq_query(event, query="files", instance_names=name, path=path):
                yield r
            return

        # --- qrcode ---
        if sub == "qrcode":
            async for r in self.ncqq_qrcode(event, instance_name=args_str):
                yield r
            return

        # --- lifecycle actions ---
        _lifecycle = {"start", "stop", "restart", "pause", "unpause", "kill"}
        if sub in _lifecycle:
            async for r in self.ncqq_action(event, action=sub, instance_names=args_str):
                yield r
            return
        if sub == "create":
            async for r in self.ncqq_action(event, action="create", instance_names=str(args)):
                yield r
            return
        if sub == "delete":
            name = parts[0] if parts else args_str
            purge = len(parts) > 1 and parts[1].lower() in ("purge", "true", "彻底")
            async for r in self.ncqq_action(event, action="delete", instance_names=name, delete_data=purge):
                yield r
            return
        if sub == "switch":
            async for r in self.ncqq_action(event, action="switch", instance_names=args_str):
                yield r
            return

        # --- bindings ---
        if sub == "bind":
            async for r in self.ncqq_binding(event, action="bind", instance_names=str(args)):
                yield r
            return
        if sub == "unbind":
            async for r in self.ncqq_binding(event, action="unbind", instance_names=str(args)):
                yield r
            return
        if sub == "bindings":
            async for r in self.ncqq_binding(event, action="list"):
                yield r
            return
        if sub == "nick":
            qq_id = parts[0] if parts else ""
            nickname = " ".join(parts[1:]) if len(parts) > 1 else ""
            async for r in self.ncqq_binding(event, action="nickname", qq_id=qq_id, nickname=nickname):
                yield r
            return

        # --- backend ---
        if sub == "backend":
            bsub = parts[0] if parts else ""
            if bsub == "add":
                alias = parts[1] if len(parts) > 1 else ""
                url = parts[2] if len(parts) > 2 else ""
                token = parts[3] if len(parts) > 3 else ""
                async for r in self.ncqq_backend(event, action="add", alias=alias, url=url, token=token):
                    yield r
                return
            if bsub == "remove":
                alias = parts[1] if len(parts) > 1 else ""
                async for r in self.ncqq_backend(event, action="remove", alias=alias):
                    yield r
                return
            if bsub == "inject":
                alias = parts[1] if len(parts) > 1 else ""
                inst = " ".join(parts[2:]) if len(parts) > 2 else ""
                async for r in self.ncqq_backend(event, action="inject", alias=alias, instance_names=inst):
                    yield r
                return
            yield event.plain_result("用法：/ncqq backend add|remove|inject <参数>")
            return

        # --- approvals ---
        if sub == "approvals":
            async for r in self.ncqq_approval(event, action="list"):
                yield r
            return
        if sub == "approve":
            async for r in self.ncqq_approval(event, action="approve", approval_id=str(args).strip()):
                yield r
            return
        if sub == "reject":
            aid = parts[0] if parts else ""
            reason = " ".join(parts[1:]) if len(parts) > 1 else ""
            async for r in self.ncqq_approval(event, action="reject", approval_id=aid, reason=reason):
                yield r
            return

        yield event.plain_result(f"未知子命令 '{sub}'。发送 ncqq help 查看帮助。")

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
