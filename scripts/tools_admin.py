"""Admin tools for ncqq manager: approval management via AstrBot admins_id."""

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
    # ------------------------------------------------------------------
    # Approval management (admin = AstrBot admins_id)
    # ------------------------------------------------------------------

    @llm_tool(name="list_ncqq_pending_approvals")
    async def list_pending_approvals_tool(self, event: AstrMessageEvent):
        """列出所有待审批的高权限操作请求。

        仅 AstrBot 管理员可查看。适用于管理员集中处理积压的审批任务。
        """
        if not event.is_admin():
            yield event.plain_result("此功能仅限管理员查看待审批请求。")
            return

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

    @llm_tool(name="approve_ncqq_request")
    async def approve_request(self, event: AstrMessageEvent, approval_id: str):
        """批准并执行指定的待审批高权限操作。

        仅 AstrBot 管理员可批准。执行后审批记录自动删除。
        适用于管理员收到审批通知后回复确认的场景。

        Args:
            approval_id (string): 六位审批 ID，如 'AB12CD'。
        """
        if not event.is_admin():
            yield event.plain_result("此功能仅限管理员处理审批请求。")
            return

        approval_id = approval_id.strip().upper()
        record = await get_approval(self, approval_id)
        if not record:
            yield event.plain_result(
                f"未找到编号为 [{approval_id}] 的审批请求，可能已处理或已过期。"
            )
            return

        yield event.plain_result(
            f"开始处理审批 [{approval_id}]：{record['description']}"
        )

        action = record["action"]
        params = record["params"]
        result_msg = await self._dispatch_approved_action(action, params)

        await remove_approval(self, approval_id)
        yield event.plain_result(
            f"审批 [{approval_id}] 已处理完成。\n{result_msg}"
        )

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
            yield event.plain_result("此功能仅限管理员拒绝审批请求。")
            return

        approval_id = approval_id.strip().upper()
        record = await get_approval(self, approval_id)
        if not record:
            yield event.plain_result(
                f"未找到编号为 [{approval_id}] 的审批请求，可能已处理或已过期。"
            )
            return

        await remove_approval(self, approval_id)
        msg = f"审批 [{approval_id}] 已拒绝：{record['description']}"
        if reason:
            msg += f"\n拒绝原因：{reason}"
        yield event.plain_result(msg)

    # ------------------------------------------------------------------
    # Internal dispatcher for approved actions (dict-based)
    # ------------------------------------------------------------------

    async def _dispatch_approved_action(self, action: str, params: dict) -> str:
        """Execute a previously approved high-privilege action and return result."""
        handlers = {
            "delete": self._handle_delete,
            "create": self._handle_create,
            "write_config": self._handle_write_config,
            "inject_backend": self._handle_inject_backend,
            "switch_account": self._handle_switch_account,
            "bind_instance": self._handle_bind_instance,
            "manage_backends_add": self._handle_manage_backends_add,
            "manage_backends_remove": self._handle_manage_backends_remove,
        }
        handler = handlers.get(action)
        if handler is None:
            return f"暂不支持处理该审批类型：{action}。请联系管理员检查配置。"
        try:
            return await handler(params)
        except Exception:
            return "审批执行过程中出现异常，请稍后重试或检查后台日志。"

    # --- 以下为各 action 的具体处理方法 ---

    async def _handle_delete(self, params: dict) -> str:
        inst_name = params["instance_name"]
        result = await do_instance_action(
            self.client,
            inst_name,
            "delete",
            delete_data=params.get("delete_data", False),
        )
        # 删除成功后自动清理 user_mapping 中对该实例的残留引用
        if "失败" not in result:
            mapping = await self.get_user_mapping()
            changed = False
            for uid, data in mapping.items():
                insts = data.get("instances", [])
                if inst_name in insts:
                    insts.remove(inst_name)
                    changed = True
            if changed:
                await self.save_user_mapping(mapping)
                result += f"\n已自动解除所有用户与实例 {inst_name} 的绑定。"
        return result

    async def _handle_create(self, params: dict) -> str:
        # 兼容旧审批记录（instance_name 单值）和新格式（instance_names 列表）
        names = params.get("instance_names") or [params["instance_name"]]
        results = []
        for n in names:
            results.append(await do_create_instance(self.client, n))
        return "\n".join(results)

    async def _handle_write_config(self, params: dict) -> str:
        return await do_write_config(
            self.client,
            params["instance_name"],
            params["file_name"],
            params["file_content"],
        )

    async def _handle_inject_backend(self, params: dict) -> str:
        return await do_inject_by_alias(
            self.client,
            alias=params["alias"],
            target="bs",
            conn_id=params["instance_name"],
        )
    async def _handle_switch_account(self, params: dict) -> str:
        inst_name = params["instance_name"]
        msg = await do_recreate_container(
            self.client, inst_name, clean_data=True, keep_config=True
        )
        return f"{msg}\n审批已通过，账号重置完毕。请申请者稍后自行发送“获取二维码”来登录新账号。"

    async def _handle_bind_instance(self, params: dict) -> str:
        mapping = await self.get_user_mapping()
        target_uid = params["target_uid"]
        # 兼容旧审批记录（instance_name 单值）和新格式（instance_names 列表）
        names = params.get("instance_names") or [params["instance_name"]]
        nickname = params.get("nickname", "")
        if target_uid not in mapping:
            mapping[target_uid] = {"nickname": "", "instances": []}
        added = []
        for n in names:
            if n not in mapping[target_uid]["instances"]:
                mapping[target_uid]["instances"].append(n)
                added.append(n)
        if nickname:
            mapping[target_uid]["nickname"] = nickname
        await self.save_user_mapping(mapping)
        added_str = "、".join(added) if added else "（均已存在，无新增）"
        return (
            f"绑定完成。目标QQ: {target_uid}"
            f" | 新增实例: {added_str}"
            f" | 昵称: {nickname or '无'}"
        )

    async def _handle_manage_backends_add(self, params: dict) -> str:
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
        return f"后端端点 {alias} 已保存。{result}"

    async def _handle_manage_backends_remove(self, params: dict) -> str:
        endpoints = await do_get_radar_endpoints(self.client)
        alias = params["alias"]
        new_endpoints = [e for e in endpoints if e.get("alias") != alias]
        result = await do_save_radar_endpoints(self.client, new_endpoints)
        return f"后端端点 {alias} 已删除。{result}"
