import base64
import re

from astrbot.api.all import AstrMessageEvent, Image, llm_tool

from .actions import do_create_instance, do_instance_action, do_recreate_container
from .approval import create_approval
from .config_manager import do_read_config, do_write_config
from .html_renderer import render_bindings, render_instances
from .interaction import do_check_login_status, do_get_qrcode
from .monitoring import (
    do_confirm_instance_action,
    do_get_monitor,
    do_list_assets,
    do_list_files,
    do_list_instances,
)


class InstanceToolsMixin:
    # 动作 → 期望 SSE 事件映射（用于操作后确认）
    _ACTION_EVENT_MAP: dict[str, list[str]] = {
        "start":   ["start"],
        "stop":    ["stop", "die"],
        "restart": ["restart", "start"],
        "pause":   ["pause"],
        "unpause": ["unpause", "start"],
        "kill":    ["kill", "die"],
        "delete":  ["destroy", "die"],
    }

    @llm_tool(name="ncqq_query")
    async def ncqq_query(
        self,
        event: AstrMessageEvent,
        query: str,
        instance_names: str = "",
        file_name: str = "onebot11_uin.json",
        path: str = "",
    ):
        """查询 ncqq 实例信息，涵盖列表、登录状态、监控、日志、资产、配置、文件目录。

        当用户想了解"有哪些实例""谁在线谁掉线""资源占用""看日志""读配置文件""查目录"时使用。
        本工具只读，不执行任何写入或控制操作。

        Args:
            query (string): 查询类型，必须是以下之一：
                "instances" — 列出所有实例及运行状态（含头像、心跳、QQ号）。
                "login"     — 检查指定实例的实时登录状态（是否在线、账号信息）。
                "monitor"   — 读取指定实例的资源占用摘要（CPU/内存/网络）。
                "logs"      — 读取指定实例的容器尾部日志（最近 8 行，已脱敏）。
                "assets"    — 列出管理节点上的镜像与节点资产（仅管理员）。
                "config"    — 读取实例容器内的配置文件内容（仅管理员）。
                "files"     — 列出实例数据目录下的文件与子目录（仅管理员）。
            instance_names (string): 实例名，login/monitor/logs/config/files 时必填；支持逗号分隔多个（login 支持批量）。
            file_name (string): 仅 query=config 时有效，容器内目标文件名，默认 onebot11_uin.json。
            path (string): 仅 query=files 时有效，相对于实例数据根目录的路径，留空表示根目录。
        """
        sender_id = str(event.get_sender_id())
        is_admin = event.is_admin()

        # --- instances ---
        if query == "instances":
            allowed = await self.get_allowed_instances(sender_id)
            result = await do_list_instances(self.client, allowed, is_admin)
            if isinstance(result, str):
                yield event.plain_result(result)
                return
            base_url = self.client.config.get("manager_url", "").rstrip("/")
            for inst in result:
                if inst.get("bot_avatar") and inst["bot_avatar"].startswith("/"):
                    inst["bot_avatar"] = f"{base_url}{inst['bot_avatar']}"
            rendered = await render_instances(result)
            if isinstance(rendered, bytes):
                yield event.chain_result([Image.fromBase64(base64.b64encode(rendered).decode())])
            else:
                yield event.plain_result(rendered)
            mapping = await self.get_user_mapping()
            if any(d.get("nickname") for d in mapping.values()):
                rb = await render_bindings(mapping)
                if isinstance(rb, bytes):
                    yield event.chain_result([Image.fromBase64(base64.b64encode(rb).decode())])
                else:
                    yield event.plain_result(rb)
            return

        # --- login ---
        if query == "login":
            names = [n.strip() for n in re.split(r"[,，、\s]+", instance_names) if n.strip()]
            if not names:
                yield event.plain_result("请补充实例名（instance_names）。")
                return
            if not is_admin:
                allowed = await self.get_allowed_instances(sender_id)
                bad = [n for n in names if n not in allowed]
                if bad:
                    yield event.plain_result(f"无权查看以下实例：{'、'.join(bad)}。")
                    return
            lines: list[str] = []
            for name in names:
                p = await do_check_login_status(self.client, name)
                if p.get("status") == "error":
                    lines.append(f"• {name}：⚠️ 获取失败，请稍后重试")
                elif p.get("logged_in"):
                    uin = p.get("uin", "")
                    nick = p.get("nickname", "")
                    label = f"{nick}({uin})" if uin else nick or "已登录"
                    lines.append(f"• {name}：🟢 在线（{label}）")
                else:
                    lines.append(f"• {name}：🔴 未登录（可能需重新扫码）")
            yield event.plain_result("\n".join(lines))
            return

        # --- monitor / logs ---
        if query in ("monitor", "logs"):
            if not is_admin:
                yield event.plain_result("监控与日志查询仅限管理员。")
                return
            name = instance_names.strip()
            if not name:
                yield event.plain_result("请补充实例名（instance_names）。")
                return
            yield event.plain_result(await do_get_monitor(self.client, name, fetch_logs=(query == "logs")))
            return

        # --- assets ---
        if query == "assets":
            if not is_admin:
                yield event.plain_result("资产查询仅限管理员。")
                return
            yield event.plain_result(await do_list_assets(self.client))
            return

        # --- config ---
        if query == "config":
            if not is_admin:
                yield event.plain_result("配置读取仅限管理员。")
                return
            name = instance_names.strip()
            if not name:
                yield event.plain_result("请补充实例名（instance_names）。")
                return
            yield event.plain_result(await do_read_config(self.client, name, file_name))
            return

        # --- files ---
        if query == "files":
            if not is_admin:
                yield event.plain_result("文件目录查询仅限管理员。")
                return
            name = instance_names.strip()
            if not name:
                yield event.plain_result("请补充实例名（instance_names）。")
                return
            yield event.plain_result(await do_list_files(self.client, name, path))
            return

        yield event.plain_result(
            f"未知查询类型 '{query}'，支持：instances / login / monitor / logs / assets / config / files。"
        )

    @llm_tool(name="ncqq_action")
    async def ncqq_action(
        self,
        event: AstrMessageEvent,
        action: str,
        instance_names: str = "",
        delete_data: bool = False,
        file_name: str = "",
        file_content: str = "",
    ):
        """对 ncqq 实例执行控制或写入操作，涵盖生命周期管理、创建、账号重置、配置覆写。

        当用户明确要求启动、停止、重启、删除、创建实例，或要求切换账号、覆写配置文件时调用。
        纯查询场景（查状态、看日志、读配置）请使用 ncqq_query；扫码请使用 ncqq_qrcode。

        Args:
            action (string): 操作类型，必须是以下之一：
                "start"        — 启动容器。
                "stop"         — 停止容器。
                "restart"      — 重启容器。
                "pause"        — 暂停容器进程。
                "unpause"      — 恢复容器进程。
                "kill"         — 强制终止容器。
                "delete"       — 销毁容器（delete_data 控制是否同时删除数据目录）。
                "create"       — 创建新实例，支持一次传入多个名称。
                "switch"       — 重置登录账号（保留配置、清空数据、重建容器）。完成后请再调 ncqq_qrcode 拉取新二维码。
                "write_config" — 覆写实例容器内配置文件，需同时提供 file_name 和 file_content。
            instance_names (string): 目标实例名，支持逗号分隔多个（create/start/stop 等均支持批量）。
            delete_data (boolean): 仅 action=delete 时有效。true 时同时删除本地数据目录（QQ数据/配置/插件/缓存，不可恢复）；false 时仅移除容器保留数据。用户说"彻底删除""删干净"时为 true，仅说"删除"时为 false。
            file_name (string): 仅 action=write_config 时必填，容器内目标文件名。
            file_content (string): 仅 action=write_config 时必填，要完整写入的文件内容（非增量）。
        """
        sender_id = str(event.get_sender_id())
        is_admin = event.is_admin()

        names = [n.strip() for n in re.split(r"[,，、\s]+", instance_names) if n.strip()]

        # ── create ──────────────────────────────────────────────────────────
        if action == "create":
            if not names:
                yield event.plain_result("请补充实例名（instance_names）。")
                return
            if not is_admin:
                aid = await create_approval(
                    self,
                    action="create",
                    params={"instance_names": names},
                    requester_qq=sender_id,
                    group_id=str(event.get_group_id() or ""),
                    description=f"创建实例 {'、'.join(names)}（申请者: {sender_id}）",
                )
                yield event.plain_result(self._approval_notice_single("创建实例", aid))
                return
            results: list[str] = []
            for n in names:
                ok, msg = await do_create_instance(self.client, n)
                results.append(msg)
            yield event.plain_result("\n".join(results))
            return

        # ── switch ──────────────────────────────────────────────────────────
        if action == "switch":
            name = (names[0] if names else "").strip()
            if not name:
                yield event.plain_result("请补充实例名（instance_names）。")
                return
            if not is_admin:
                allowed = await self.get_allowed_instances(sender_id)
                if name not in allowed:
                    yield event.plain_result(f"实例 {name} 不在你的可操作范围内。")
                    return
                aid = await create_approval(
                    self,
                    action="switch_account",
                    params={"instance_name": name},
                    requester_qq=sender_id,
                    group_id=str(event.get_group_id() or ""),
                    description=f"切换实例 {name} 账号（申请者: {sender_id}）",
                )
                yield event.plain_result(self._approval_notice_single("切换账号", aid))
                return
            yield event.plain_result(f"⏳ 正在重置 {name} 的登录态（保留配置），请稍候…")
            ok, msg = await do_recreate_container(self.client, name, clean_data=True, keep_config=True)
            if not ok:
                yield event.plain_result(f"重置失败：{msg}")
                return
            yield event.plain_result(f"✅ {msg}\n容器已重建，请调用 ncqq_qrcode 拉取新登录二维码。")
            return

        # ── write_config ─────────────────────────────────────────────────────
        if action == "write_config":
            name = (names[0] if names else "").strip()
            if not name or not file_name or not file_content:
                yield event.plain_result("write_config 需要同时提供 instance_names、file_name、file_content。")
                return
            if not is_admin:
                allowed = await self.get_allowed_instances(sender_id)
                if name not in allowed:
                    yield event.plain_result(f"实例 {name} 不在你的可操作范围内，无法提交配置修改申请。")
                    return
                aid = await create_approval(
                    self,
                    action="write_config",
                    params={"instance_name": name, "file_name": file_name, "file_content": file_content},
                    requester_qq=sender_id,
                    group_id=str(event.get_group_id() or ""),
                    description=f"覆写配置 {name}/{file_name}（申请者: {sender_id}）",
                )
                yield event.plain_result(self._approval_notice_single("覆写配置", aid))
                return
            yield event.plain_result(await do_write_config(self.client, name, file_name, file_content))
            return

        # ── lifecycle: start/stop/restart/pause/unpause/kill/delete ──────────
        _lifecycle = {"start", "stop", "restart", "pause", "unpause", "kill", "delete"}
        if action not in _lifecycle:
            yield event.plain_result(
                f"不支持的操作 '{action}'。支持：start / stop / restart / pause / unpause / kill / delete / create / switch / write_config。"
            )
            return

        if not names:
            yield event.plain_result("请补充实例名（instance_names）。")
            return

        if action == "delete":
            if not is_admin:
                allowed = await self.get_allowed_instances(sender_id)
                bad = [n for n in names if n not in allowed]
                if bad:
                    yield event.plain_result(f"以下实例不在你的可操作范围内：{'、'.join(bad)}。如需删除请联系管理员。")
                    return
                ids = []
                for n in names:
                    aid = await create_approval(
                        self,
                        action="delete",
                        params={"instance_name": n, "delete_data": delete_data},
                        requester_qq=sender_id,
                        group_id=str(event.get_group_id() or ""),
                        description=f"销毁实例 {n}{'（含本地数据）' if delete_data else ''}（申请者: {sender_id}）",
                    )
                    ids.append(aid)
                yield event.plain_result(self._approval_notice_batch("销毁实例", list(zip(names, ids))))
                return
            # Admin delete
            results = []
            cleaned: list[str] = []
            for n in names:
                ok, msg = await do_instance_action(self.client, n, "delete", delete_data=delete_data)
                if ok:
                    _, confirm = await do_confirm_instance_action(self.client, n, self._ACTION_EVENT_MAP["delete"])
                    msg = f"{msg}\n{confirm}"
                    cleaned.append(n)
                results.append(msg)
            if cleaned:
                mapping = await self.get_user_mapping()
                changed = False
                for data in mapping.values():
                    for inst in cleaned:
                        lst = data.get("instances", [])
                        if inst in lst:
                            lst.remove(inst)
                            changed = True
                if changed:
                    await self.save_user_mapping(mapping)
                    results.append(f"已自动解除所有用户与实例 {'、'.join(cleaned)} 的绑定。")
            yield event.plain_result("\n".join(results))
            return

        # Non-destructive lifecycle
        if not is_admin:
            allowed = await self.get_allowed_instances(sender_id)
            bad = [n for n in names if n not in allowed]
            if bad:
                yield event.plain_result(f"以下实例不在你的可操作范围内：{'、'.join(bad)}。请联系管理员完成绑定。")
                return

        results = []
        for n in names:
            ok, msg = await do_instance_action(self.client, n, action)
            if ok:
                _, confirm = await do_confirm_instance_action(self.client, n, self._ACTION_EVENT_MAP.get(action, [action]))
                msg = f"{msg}\n{confirm}"
            results.append(msg)
        yield event.plain_result("\n".join(results))

    @llm_tool(name="ncqq_qrcode")
    async def ncqq_qrcode(self, event: AstrMessageEvent, instance_name: str):
        """获取指定 ncqq 实例的登录二维码图片。

        当用户说"获取二维码""拉码""扫码登录""帮我拉个码"等含"二维码/扫码/登录码"关键词时调用。
        本工具直接拉取并返回二维码，不再内部自动检查登录状态——如需确认是否需要扫码，
        请先调用 ncqq_query(query="login") 确认实例处于未登录状态后再调用本工具。
        若二维码即将过期，本工具会直接告知，不会自动等待重取；请用户稍候后再次发起请求。

        Args:
            instance_name (string): 目标 ncqq 实例名，必须明确提供。
        """
        sender_id = str(event.get_sender_id())
        is_admin = event.is_admin()
        name = instance_name.strip()

        if not name:
            yield event.plain_result("请提供实例名（instance_name）。")
            return

        if not is_admin:
            allowed = await self.get_allowed_instances(sender_id)
            if name not in allowed:
                yield event.plain_result(f"实例 {name} 不在你的可操作范围内，请确认实例名或联系管理员。")
                return

        results = await do_get_qrcode(self.client, name)

        for item in results:
            if isinstance(item, str) and item.startswith("__qr_soon__:"):
                secs = int(item.split(":", 1)[1])
                yield event.plain_result(
                    f"⚠️ 当前二维码仅剩约 {secs} 秒有效期，即将过期，请稍候几秒后重新发送请求。"
                )
            elif isinstance(item, str):
                yield event.plain_result(item)
            else:
                yield event.chain_result([item])

