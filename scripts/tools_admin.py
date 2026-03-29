"""Admin tools for ncqq manager: approval management via AstrBot admins_id."""

from __future__ import annotations

import time

from astrbot.api.all import AstrMessageEvent, llm_tool

from .actions import do_create_instance, do_inject_by_alias, do_instance_action
from .approval import (
    get_approval,
    list_approvals,
    remove_approval,
)
from .config_manager import do_write_config
from .monitoring import do_get_radar_endpoints, do_save_radar_endpoints


class AdminToolsMixin:
    # ------------------------------------------------------------------
    # Approval management (admin = AstrBot admins_id)
    # ------------------------------------------------------------------

    @llm_tool(name="list_ncqq_pending_approvals")
    async def list_pending_approvals_tool(self, event: AstrMessageEvent):
        """列出所有待审批的高权限操作请求。

        仅 AstrBot 管理员可查看。适用于管理员集中处理积压的审批任务。
        """
        if not event.is_admin():
            yield event.plain_result("权限不足。仅限管理员查看待审批列表。")
            return

        records = await list_approvals(self)
        if not records:
            yield event.plain_result("当前无待审批请求。")
            return

        lines = ["📋 待审批操作列表："]
        for r in records:
            age_min = int((time.time() - r.get("created_at", 0)) / 60)
            lines.append(
                f"• [{r['approval_id']}] {r['description']}"
                f" | 申请者: {r['requester_qq']}"
                f" | {age_min} 分钟前"
            )
        yield event.plain_result("\n".join(lines))

    @llm_tool(name="approve_ncqq_request")
    async def approve_request(self, event: AstrMessageEvent, approval_id: str):
        """批准并执行指定的待审批高权限操作。

        仅 AstrBot 管理员可批准。执行后审批记录自动删除。
        适用于管理员收到审批通知后回复确认的场景。

        Args:
            approval_id (string): 六位审批 ID，如 'AB12CD'。
        """
        if not event.is_admin():
            yield event.plain_result("权限不足。仅限管理员批准审批请求。")
            return

        approval_id = approval_id.strip().upper()
        record = await get_approval(self, approval_id)
        if not record:
            yield event.plain_result(
                f"未找到审批 ID [{approval_id}] 的有效请求（可能已过期或不存在）。"
            )
            return

        yield event.plain_result(
            f"⚙️ 正在以 Owner 权限执行审批 [{approval_id}]：{record['description']}"
        )

        action = record["action"]
        params = record["params"]
        result_msg = await self._dispatch_approved_action(action, params)

        await remove_approval(self, approval_id)
        yield event.plain_result(f"✅ 审批 [{approval_id}] 执行完毕：\n{result_msg}")

    @llm_tool(name="reject_ncqq_request")
    async def reject_request(
        self, event: AstrMessageEvent, approval_id: str, reason: str = ""
    ):
        """拒绝并删除指定的待审批高权限操作。

        仅 AstrBot 管理员可拒绝。

        Args:
            approval_id (string): 六位审批 ID，如 'AB12CD'。
            reason (string): 可选拒绝原因，将反馈给申请者。
        """
        if not event.is_admin():
            yield event.plain_result("权限不足。仅限管理员拒绝审批请求。")
            return

        approval_id = approval_id.strip().upper()
        record = await get_approval(self, approval_id)
        if not record:
            yield event.plain_result(f"未找到审批 ID [{approval_id}] 的有效请求。")
            return

        await remove_approval(self, approval_id)
        msg = f"❌ 审批 [{approval_id}] 已拒绝：{record['description']}"
        if reason:
            msg += f"\n拒绝原因：{reason}"
        yield event.plain_result(msg)

    # ------------------------------------------------------------------
    # Internal dispatcher for approved actions
    # ------------------------------------------------------------------

    async def _dispatch_approved_action(self, action: str, params: dict) -> str:
        """Execute a previously approved high-privilege action and return result."""
        try:
            if action == "delete":
                return await do_instance_action(
                    self.client, params["instance_name"], "delete"
                )
            if action == "create":
                return await do_create_instance(self.client, params["instance_name"])
            if action == "write_config":
                return await do_write_config(
                    self.client,
                    params["instance_name"],
                    params["file_name"],
                    params["file_content"],
                )
            if action == "inject_backend":
                return await do_inject_by_alias(
                    self.client,
                    alias=params["alias"],
                    target="bs",
                    conn_id=params["instance_name"],
                )
            if action == "bind_instance":
                mapping = await self.get_user_mapping()
                target_uid = params["target_uid"]
                instance_name = params["instance_name"]
                nickname = params.get("nickname", "")
                if target_uid not in mapping:
                    mapping[target_uid] = {"nickname": "", "instances": []}
                if instance_name not in mapping[target_uid]["instances"]:
                    mapping[target_uid]["instances"].append(instance_name)
                if nickname:
                    mapping[target_uid]["nickname"] = nickname
                await self.save_user_mapping(mapping)
                return (
                    f"绑定完成。目标QQ: {target_uid}"
                    f" | 实例: {instance_name}"
                    f" | 昵称: {nickname or '无'}"
                )
            if action == "manage_backends_add":
                endpoints = await do_get_radar_endpoints(self.client)
                alias = params["alias"]
                url = params["url"]
                token = params.get("token", "")
                existing = next((e for e in endpoints if e.get("alias") == alias), None)
                if existing:
                    existing["url"] = url
                    existing["token"] = token
                else:
                    endpoints.append({"alias": alias, "url": url, "token": token})
                result = await do_save_radar_endpoints(self.client, endpoints)
                return f"端点已添加/更新: alias={alias} url={url}  {result}"
            if action == "manage_backends_remove":
                endpoints = await do_get_radar_endpoints(self.client)
                alias = params["alias"]
                new_endpoints = [e for e in endpoints if e.get("alias") != alias]
                result = await do_save_radar_endpoints(self.client, new_endpoints)
                return f"端点已删除: alias={alias}  {result}"
            return f"未知操作类型 '{action}'，请联系开发者。"
        except Exception as e:
            return f"执行失败: {e}"
