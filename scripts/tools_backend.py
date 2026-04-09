import base64
import re

from astrbot.api.all import AstrMessageEvent, At, Image, llm_tool

from .actions import do_inject_by_alias
from .approval import create_approval
from .monitoring import do_get_radar_endpoints, do_save_radar_endpoints


class BackendToolsMixin:
    @llm_tool(name="ncqq_backend")
    async def ncqq_backend(
        self,
        event: AstrMessageEvent,
        action: str,
        alias: str = "",
        url: str = "",
        token: str = "",
        instance_names: str = "",
        instance_keyword: str = "",
    ):
        """管理 ncqq 后端雷达端点库，以及将端点注入到实例。

        当用户要添加/删除后端端点模板，或要把某个后端接入指定实例时调用。
        查看绑定关系、设置昵称、绑定/解绑实例归属请使用 ncqq_binding。

        Args:
            action (string): 操作类型，必须是以下之一：
                "add"    — 向雷达端点库新增或更新一条端点（需提供 alias 和 url）。
                "remove" — 从雷达端点库删除指定别名的端点（需提供 alias）。
                "inject" — 将端点库中的指定别名注入到目标实例的后端连接（热重载立即生效）。
                           目标实例来源优先级：instance_names 直接指定 > @用户绑定实例（配合 instance_keyword 过滤）> 发送者自身绑定实例。
            alias (string): 端点别名，add/remove/inject 均需提供。inject 时支持模糊匹配（含 alias 子串即可）。
            url (string): 仅 action=add 时必填的后端 WebSocket 地址。
            token (string): 可选鉴权 token，仅 action=add 时有效。
            instance_names (string): 仅 action=inject 时有效，直接指定要注入的实例名，逗号分隔多个；填写后跳过用户绑定查找。
            instance_keyword (string): 仅 action=inject 且走 @用户 路径时有效，用于从该用户实例列表中模糊过滤目标；为空则注入该用户所有绑定实例。
        """
        sender_id = str(event.get_sender_id())
        is_admin = event.is_admin()

        # ── add ──────────────────────────────────────────────────────────────
        if action == "add":
            if not is_admin:
                aid = await create_approval(
                    self, action="manage_backends_add",
                    params={"alias": alias, "url": url, "token": token},
                    requester_qq=sender_id,
                    group_id=str(event.get_group_id() or ""),
                    description=f"后端端点 add：{alias}（申请者: {sender_id}）",
                )
                yield event.plain_result(self._approval_notice_single("添加后端端点", aid))
                return
            if not url:
                yield event.plain_result("添加失败：请补充后端地址（url）。")
                return
            endpoints = await do_get_radar_endpoints(self.client)
            existing = next((e for e in endpoints if e.get("alias") == alias), None)
            if existing:
                existing["url"] = url
                existing["token"] = token
            else:
                endpoints.append({"alias": alias, "url": url, "token": token})
            result = await do_save_radar_endpoints(self.client, endpoints)
            yield event.plain_result(f"后端端点 {alias} 已保存。{result}")
            return

        # ── remove ────────────────────────────────────────────────────────────
        if action == "remove":
            if not is_admin:
                aid = await create_approval(
                    self, action="manage_backends_remove",
                    params={"alias": alias},
                    requester_qq=sender_id,
                    group_id=str(event.get_group_id() or ""),
                    description=f"后端端点 remove：{alias}（申请者: {sender_id}）",
                )
                yield event.plain_result(self._approval_notice_single("删除后端端点", aid))
                return
            endpoints = await do_get_radar_endpoints(self.client)
            new_eps = [e for e in endpoints if e.get("alias") != alias]
            if len(new_eps) == len(endpoints):
                yield event.plain_result(f"未找到名为 {alias} 的端点，未执行删除。")
                return
            result = await do_save_radar_endpoints(self.client, new_eps)
            yield event.plain_result(f"后端端点 {alias} 已删除。{result}")
            return

        # ── inject ────────────────────────────────────────────────────────────
        if action == "inject":
            endpoints = await do_get_radar_endpoints(self.client)
            matched = next(
                (e for e in endpoints if alias.lower() in e.get("alias", "").lower()), None
            )
            if not matched:
                yield event.plain_result(f"未找到别名含 '{alias}' 的后端端点，请先添加或确认别名。")
                return
            resolved_alias = matched["alias"]

            # 路径 A：直接指定实例名
            direct = [n.strip() for n in re.split(r"[,，、\s]+", instance_names) if n.strip()]
            if direct:
                if not is_admin:
                    ids = []
                    for n in direct:
                        aid = await create_approval(
                            self, action="inject_backend",
                            params={"alias": resolved_alias, "instance_name": n},
                            requester_qq=sender_id,
                            group_id=str(event.get_group_id() or ""),
                            description=f"接入后端 {resolved_alias} → 实例 {n}（申请者: {sender_id}）",
                        )
                        ids.append(aid)
                    yield event.plain_result(self._approval_notice_batch("接入后端", list(zip(direct, ids))))
                    return
                results: list[str] = []
                for n in direct:
                    ok, msg = await do_inject_by_alias(self.client, alias=resolved_alias, target="bs", conn_id=n)
                    results.append(f"[{n}] {msg}")
                yield event.plain_result(f"批量接入后端 {resolved_alias}：\n" + "\n".join(results))
                return

            # 路径 B：通过 @用户 / 发送者自身
            at_users = [comp.qq for comp in event.message_obj.message if isinstance(comp, At)]
            target_uid = str(at_users[0]) if at_users else sender_id
            allowed = await self.get_allowed_instances(target_uid)
            if not allowed:
                tip = f"用户 {target_uid} 没有可操作的实例。" if at_users else "你还没有可操作的实例，请先联系管理员完成绑定。"
                yield event.plain_result(tip)
                return
            targets = (
                [i for i in allowed if instance_keyword.lower() in i.lower()]
                if instance_keyword else allowed
            )
            if not targets:
                yield event.plain_result(f"在该用户实例中未找到含 '{instance_keyword}' 的结果，请补充更准确的实例名。")
                return
            if not is_admin:
                ids = []
                for n in targets:
                    aid = await create_approval(
                        self, action="inject_backend",
                        params={"alias": resolved_alias, "instance_name": n},
                        requester_qq=sender_id,
                        group_id=str(event.get_group_id() or ""),
                        description=f"接入后端 {resolved_alias} → 实例 {n}（归属: {target_uid}）",
                    )
                    ids.append(aid)
                yield event.plain_result(self._approval_notice_batch("接入后端", list(zip(targets, ids))))
                return
            results = []
            for n in targets:
                ok, msg = await do_inject_by_alias(self.client, alias=resolved_alias, target="bs", conn_id=n)
                results.append(f"[{n}] {msg}")
            yield event.plain_result(f"已为用户 {target_uid} 接入后端 {resolved_alias}：\n" + "\n".join(results))
            return

        yield event.plain_result(f"不支持的操作 '{action}'，支持：add / remove / inject。")

    @llm_tool(name="ncqq_binding")
    async def ncqq_binding(
        self,
        event: AstrMessageEvent,
        action: str,
        instance_names: str = "",
        qq_id: str = "",
        nickname: str = "",
    ):
        """管理 ncqq 实例的用户归属绑定及昵称。

        当用户要绑定/解绑实例归属、查看绑定列表、设置用户昵称时调用。
        后端端点的添加/删除/注入请使用 ncqq_backend。

        Args:
            action (string): 操作类型，必须是以下之一：
                "bind"     — 将一个或多个实例绑定给消息中被 @的目标用户（仅管理员；非管理员提交审批）。
                "unbind"   — 将一个或多个实例从 @的目标用户解绑（仅管理员）。
                "list"     — 以图片形式展示所有用户与实例的绑定对照表。
                "nickname" — 为指定 QQ 号设置展示昵称（仅管理员）。
            instance_names (string): bind/unbind 时必填，实例名列表，逗号分隔多个。
            qq_id (string): 仅 action=nickname 时必填，要设置昵称的目标 QQ 号。
            nickname (string): bind 时可选（顺带记录昵称）；nickname 时必填。
        """
        sender_id = str(event.get_sender_id())
        is_admin = event.is_admin()

        # ── list ──────────────────────────────────────────────────────────────
        if action == "list":
            mapping = await self.get_user_mapping()
            if not mapping:
                yield event.plain_result("当前没有任何用户绑定记录。")
                return
            from .html_renderer import render_bindings
            rendered = await render_bindings(mapping)
            if isinstance(rendered, bytes):
                b64 = base64.b64encode(rendered).decode()
                yield event.chain_result([Image.fromBase64(b64)])
            else:
                yield event.plain_result(rendered)
            return

        # ── nickname ──────────────────────────────────────────────────────────
        if action == "nickname":
            if not is_admin:
                yield event.plain_result("设置昵称仅限管理员。")
                return
            target = qq_id.strip() or sender_id
            if not nickname:
                yield event.plain_result("请补充昵称（nickname）。")
                return
            mapping = await self.get_user_mapping()
            if target not in mapping:
                mapping[target] = {"nickname": "", "instances": []}
            mapping[target]["nickname"] = nickname
            await self.save_user_mapping(mapping)
            yield event.plain_result(f"昵称已更新：{nickname}（QQ {target}）。")
            return

        # ── bind ──────────────────────────────────────────────────────────────
        if action == "bind":
            names = [n.strip() for n in re.split(r"[,，、\s]+", instance_names) if n.strip()]
            if not names:
                yield event.plain_result("请补充实例名（instance_names）。")
                return
            label = "、".join(names)
            at_users = [comp.qq for comp in event.message_obj.message if isinstance(comp, At)]
            if not is_admin:
                target_uid = str(at_users[0]) if at_users else sender_id
                aid = await create_approval(
                    self, action="bind_instance",
                    params={"target_uid": target_uid, "instance_names": names, "nickname": nickname},
                    requester_qq=sender_id,
                    group_id=str(event.get_group_id() or ""),
                    description=f"绑定实例 {label} → QQ {target_uid}（申请者: {sender_id}）",
                )
                yield event.plain_result(self._approval_notice_single("绑定实例", aid))
                return
            if not at_users:
                yield event.plain_result("请在对话中 @ 目标用户以确定绑定对象。")
                return
            target_uid = str(at_users[0])
            mapping = await self.get_user_mapping()
            if target_uid not in mapping:
                mapping[target_uid] = {"nickname": "", "instances": []}
            added = [n for n in names if n not in mapping[target_uid]["instances"]]
            mapping[target_uid]["instances"].extend(added)
            if nickname:
                mapping[target_uid]["nickname"] = nickname
            await self.save_user_mapping(mapping)
            yield event.plain_result(
                f"绑定完成：目标 {target_uid} | 新增：{'、'.join(added) if added else '无新增'} | 昵称：{nickname or '未设置'}"
            )
            return

        # ── unbind ────────────────────────────────────────────────────────────
        if action == "unbind":
            if not is_admin:
                yield event.plain_result("解绑实例仅管理员可操作。")
                return
            names = [n.strip() for n in re.split(r"[,，、\s]+", instance_names) if n.strip()]
            if not names:
                yield event.plain_result("请补充实例名（instance_names）。")
                return
            at_users = [comp.qq for comp in event.message_obj.message if isinstance(comp, At)]
            if not at_users:
                yield event.plain_result("请在对话中 @ 目标用户以确定解绑对象。")
                return
            target_uid = str(at_users[0])
            mapping = await self.get_user_mapping()
            if target_uid not in mapping or not mapping[target_uid].get("instances"):
                yield event.plain_result(f"用户 {target_uid} 当前没有已绑定的实例。")
                return
            current: list[str] = mapping[target_uid]["instances"]
            removed = [n for n in names if n in current]
            not_found = [n for n in names if n not in current]
            for n in removed:
                current.remove(n)
            await self.save_user_mapping(mapping)
            parts = [f"目标：{target_uid}"]
            if removed:
                parts.append(f"已解绑：{'、'.join(removed)}")
            if not_found:
                parts.append(f"未找到（已跳过）：{'、'.join(not_found)}")
            parts.append(f"剩余绑定：{'、'.join(current) if current else '无'}")
            yield event.plain_result("解绑完成。" + "；".join(parts))
            return

        yield event.plain_result(f"不支持的操作 '{action}'，支持：bind / unbind / list / nickname。")

