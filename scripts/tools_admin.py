"""Admin approval tools for ncqq manager."""

from __future__ import annotations

import time

from astrbot.api.all import AstrMessageEvent, llm_tool

from .actions import do_create_instance, do_inject_by_alias, do_instance_action, do_recreate_container
from .approval import (
    get_approval,
    list_approvals,
    remove_approval,
)
from .config_manager import do_write_config
from .monitoring import do_get_radar_endpoints, do_save_radar_endpoints


class AdminToolsMixin:
    @llm_tool(name="ncqq_approval")
    async def ncqq_approval(
        self,
        event: AstrMessageEvent,
        action: str,
        approval_id: str = "",
        reason: str = "",
    ):
        """查看、批准或拒绝 ncqq 高权限操作的待审批请求。

        当管理员要处理积压审批、批准或驳回某条申请时调用。
        仅 AstrBot 管理员可使用；普通用户提交的高权限操作（删除实例、创建实例、覆写配置等）会生成审批记录，等待管理员在此处理。

        Args:
            action (string): 操作类型，必须是以下之一：
                "list"    — 列出所有未过期的待审批请求（含申请描述、ID、等待时长）。
                "approve" — 批准并立即执行指定审批请求，执行后记录自动删除。
                "reject"  — 拒绝并删除指定审批请求，可附带拒绝原因。
            approval_id (string): approve/reject 时必填，六位审批 ID（大小写不敏感），例如 'AB12CD'。
            reason (string): 仅 action=reject 时有效，可选拒绝原因。
        """
        if not event.is_admin():
            yield event.plain_result("此功能仅限 AstrBot 管理员使用。")
            return

        # ── list ──────────────────────────────────────────────────────────────
        if action == "list":
            records = await list_approvals(self)
            if not records:
                yield event.plain_result("当前没有待处理的审批请求。")
                return
            lines = ["⏳ 待审批请求列表："]
            for r in records:
                age_min = int((time.time() - r.get("created_at", 0)) / 60)
                lines.append(
                    f"• [{r['approval_id']}] {r['description']}\n"
                    f"   申请者: {r['requester_qq']} | 已等待 {age_min} 分钟"
                )
            yield event.plain_result("\n\n".join(lines))
            return

        # ── approve ───────────────────────────────────────────────────────────
        if action == "approve":
            aid = approval_id.strip().upper()
            if not aid:
                yield event.plain_result("请提供审批 ID（approval_id）。")
                return
            record = await get_approval(self, aid)
            if not record:
                yield event.plain_result(f"未找到编号 [{aid}] 的审批请求，可能已处理或已过期。")
                return
            yield event.plain_result(f"开始处理审批 [{aid}]：{record['description']}")
            result_msg = await self._dispatch_approved_action(record["action"], record["params"])
            await remove_approval(self, aid)
            yield event.plain_result(f"审批 [{aid}] 已处理完成。\n{result_msg}")
            return

        # ── reject ────────────────────────────────────────────────────────────
        if action == "reject":
            aid = approval_id.strip().upper()
            if not aid:
                yield event.plain_result("请提供审批 ID（approval_id）。")
                return
            record = await get_approval(self, aid)
            if not record:
                yield event.plain_result(f"未找到编号 [{aid}] 的审批请求，可能已处理或已过期。")
                return
            await remove_approval(self, aid)
            msg = f"审批 [{aid}] 已拒绝：{record['description']}"
            if reason:
                msg += f"\n拒绝原因：{reason}"
            yield event.plain_result(msg)
            return

        yield event.plain_result(f"不支持的操作 '{action}'，支持：list / approve / reject。")


    # ------------------------------------------------------------------
    # Internal dispatcher for approved actions
    # ------------------------------------------------------------------

    async def _dispatch_approved_action(self, action: str, params: dict) -> str:
        """将已批准的审批记录分发到对应 handler 执行并返回结果文本。

        支持的 action 键：delete / create / write_config / inject_backend /
        switch_account / bind_instance / manage_backends_add / manage_backends_remove。
        """
        handlers = {
            "delete":                self._handle_delete,
            "create":                self._handle_create,
            "write_config":          self._handle_write_config,
            "inject_backend":        self._handle_inject_backend,
            "switch_account":        self._handle_switch_account,
            "bind_instance":         self._handle_bind_instance,
            "manage_backends_add":   self._handle_manage_backends_add,
            "manage_backends_remove": self._handle_manage_backends_remove,
        }
        handler = handlers.get(action)
        if handler is None:
            return f"暂不支持处理该审批类型：{action}。请联系管理员检查配置。"
        try:
            return await handler(params)
        except Exception:
            return "审批执行过程中出现异常，请稍后重试或检查后台日志。"

    # --- 各 action 的具体处理方法 ---

    async def _handle_delete(self, params: dict) -> str:
        inst_name = params["instance_name"]
        ok, msg = await do_instance_action(
            self.client, inst_name, "delete", delete_data=params.get("delete_data", False)
        )
        if ok:
            mapping = await self.get_user_mapping()
            changed = False
            for data in mapping.values():
                insts = data.get("instances", [])
                if inst_name in insts:
                    insts.remove(inst_name)
                    changed = True
            if changed:
                await self.save_user_mapping(mapping)
                msg += f"\n已自动解除所有用户与实例 {inst_name} 的绑定。"
        return msg

    async def _handle_create(self, params: dict) -> str:
        # 兼容旧格式（instance_name 单值）和新格式（instance_names 列表）
        names = params.get("instance_names") or [params["instance_name"]]
        results = []
        for n in names:
            _, msg = await do_create_instance(self.client, n)
            results.append(msg)
        return "\n".join(results)

    async def _handle_write_config(self, params: dict) -> str:
        return await do_write_config(
            self.client, params["instance_name"], params["file_name"], params["file_content"]
        )

    async def _handle_inject_backend(self, params: dict) -> str:
        _, msg = await do_inject_by_alias(
            self.client, alias=params["alias"], target="bs", conn_id=params["instance_name"]
        )
        return msg

    async def _handle_switch_account(self, params: dict) -> str:
        inst_name = params["instance_name"]
        _, msg = await do_recreate_container(
            self.client, inst_name, clean_data=True, keep_config=True
        )
        return f"{msg}\n审批已通过，账号重置完毕。请申请者稍后自行发送「获取二维码」来登录新账号。"

    async def _handle_bind_instance(self, params: dict) -> str:
        mapping = await self.get_user_mapping()
        target_uid = params["target_uid"]
        # 兼容旧格式（instance_name 单值）和新格式（instance_names 列表）
        names = params.get("instance_names") or [params["instance_name"]]
        nickname = params.get("nickname", "")
        if target_uid not in mapping:
            mapping[target_uid] = {"nickname": "", "instances": []}
        added = [n for n in names if n not in mapping[target_uid]["instances"]]
        mapping[target_uid]["instances"].extend(added)
        if nickname:
            mapping[target_uid]["nickname"] = nickname
        await self.save_user_mapping(mapping)
        added_str = "、".join(added) if added else "（均已存在，无新增）"
        return f"绑定完成。目标QQ: {target_uid} | 新增实例: {added_str} | 昵称: {nickname or '无'}"

    async def _handle_manage_backends_add(self, params: dict) -> str:
        endpoints = await do_get_radar_endpoints(self.client)
        alias, url, token = params["alias"], params["url"], params.get("token", "")
        existing = next((e for e in endpoints if e.get("alias") == alias), None)
        if existing:
            existing["url"] = url
            existing["token"] = token
        else:
            endpoints.append({"alias": alias, "url": url, "token": token})
        result = await do_save_radar_endpoints(self.client, endpoints)
        return f"后端端点 {alias} 已保存。{result}"

    async def _handle_manage_backends_remove(self, params: dict) -> str:
        endpoints = await do_get_radar_endpoints(self.client)
        alias = params["alias"]
        new_eps = [e for e in endpoints if e.get("alias") != alias]
        result = await do_save_radar_endpoints(self.client, new_eps)
        return f"后端端点 {alias} 已删除。{result}"

