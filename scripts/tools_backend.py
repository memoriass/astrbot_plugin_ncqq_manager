from astrbot.api.all import AstrMessageEvent, At, llm_tool

from .actions import do_inject_by_alias
from .approval import create_approval
from .monitoring import do_get_radar_endpoints, do_save_radar_endpoints


class BackendToolsMixin:
    @llm_tool(name="bind_ncqq_instance")
    async def bind_instance(
        self, event: AstrMessageEvent, instance_name: str, nickname: str = ""
    ):
        """将 ncqq 实例绑定给消息中被 @ 的目标用户。

        仅适用于管理员分配实例归属权的场景。
        必须依赖消息里的真实 @ 目标用户，不要在没有 At 组件时猜测绑定对象。
        不适用于实例启停、二维码获取、后端接入。

        Args:
            instance_name (string): 要绑定给目标用户的 ncqq 实例名。
            nickname (string): 可选昵称。若能从上下文确定目标用户称呼，可一并记录。
        """
        if not event.is_admin():
            sender_id = str(event.get_sender_id())
            # Need @mention to know the target
            at_users = [
                comp.qq for comp in event.message_obj.message if isinstance(comp, At)
            ]
            target_uid = str(at_users[0]) if at_users else sender_id
            approval_id = await create_approval(
                self,
                action="bind_instance",
                params={
                    "target_uid": target_uid,
                    "instance_name": instance_name,
                    "nickname": nickname,
                },
                requester_qq=sender_id,
                group_id=str(event.get_group_id() or ""),
                description=f"绑定实例 {instance_name} → QQ {target_uid}（申请者: {sender_id}）",
            )
            admins = self.get_astrbot_admins()
            at_parts = "".join(f"@{a} " for a in admins) if admins else "@管理员 "
            yield event.plain_result(
                f"⚠️ 绑定实例属于高权限操作，已提交审批。\n"
                f"审批 ID：{approval_id}\n"
                f"请 {at_parts}回复确认（引用本条消息或说'plana 批准 {approval_id}'）。"
            )
            return

        at_users = [
            comp.qq for comp in event.message_obj.message if isinstance(comp, At)
        ]
        if not at_users:
            yield event.plain_result(
                "缺少被操作者目标，请在对话中使用 @ 提及目标用户。"
            )
            return

        target_uid = str(at_users[0])

        mapping = await self.get_user_mapping()
        if target_uid not in mapping:
            mapping[target_uid] = {"nickname": "", "instances": []}

        if instance_name not in mapping[target_uid]["instances"]:
            mapping[target_uid]["instances"].append(instance_name)

        if nickname:
            mapping[target_uid]["nickname"] = nickname

        await self.save_user_mapping(mapping)

        yield event.plain_result(
            f"绑定更新成功。目标QQ: {target_uid} | 实例: {instance_name} | 昵称: {nickname or '无'}"
        )

    @llm_tool(name="set_ncqq_nickname")
    async def set_ncqq_nickname(
        self, event: AstrMessageEvent, qq_id: str, nickname: str
    ):
        """为指定 QQ 号记录展示昵称。

        适用于管理员维护用户映射、昵称展示、友好名称时。
        不适用于绑定实例、后端接入、二维码获取。

        Args:
            qq_id (string): 要设置昵称的 QQ 号。
            nickname (string): 要保存的昵称。
        """
        if not event.is_admin():
            yield event.plain_result("权限不足。仅限管理员修改昵称。")
            return
        mapping = await self.get_user_mapping()

        if qq_id not in mapping:
            mapping[qq_id] = {"nickname": "", "instances": []}

        mapping[qq_id]["nickname"] = nickname
        await self.save_user_mapping(mapping)
        yield event.plain_result(f"昵称设置完毕。QQ {qq_id} -> {nickname}。")

    @llm_tool(name="manage_ncqq_backends")
    async def manage_backends(
        self,
        event: AstrMessageEvent,
        action: str,
        alias: str,
        url: str = "",
        token: str = "",
    ):
        """管理 ncqq 管理器中的后端雷达端点库（服务端存储）。

        仅适用于管理员新增或删除后端端点模板。
        不适用于把实例接入后端；真正执行接入应调用 inject_backend_to_instance。

        Args:
            action (string): 管理动作，只应为 add 或 remove。
            alias (string): 后端端点别名，用于唯一标识该端点。
            url (string): 当 action=add 时必填的后端 WebSocket 地址。
            token (string): 可选鉴权 token。
        """
        if not event.is_admin():
            sender_id = str(event.get_sender_id())
            approval_action = f"manage_backends_{action}"
            approval_id = await create_approval(
                self,
                action=approval_action,
                params={"alias": alias, "url": url, "token": token},
                requester_qq=sender_id,
                group_id=str(event.get_group_id() or ""),
                description=f"后端端点 {action}: alias={alias}（申请者: {sender_id}）",
            )
            admins = self.get_astrbot_admins()
            at_parts = "".join(f"@{a} " for a in admins) if admins else "@管理员 "
            yield event.plain_result(
                f"⚠️ 管理后端端点属于高权限操作，已提交审批。\n"
                f"审批 ID：{approval_id}\n"
                f"请 {at_parts}回复确认（引用本条消息或说'plana 批准 {approval_id}'）。"
            )
            return

        endpoints = await do_get_radar_endpoints(self.client)

        if action == "add":
            if not url:
                yield event.plain_result("添加失败。缺乏 url 参数。")
                return
            # 已存在则更新，否则追加
            existing = next((e for e in endpoints if e.get("alias") == alias), None)
            if existing:
                existing["url"] = url
                existing["token"] = token
            else:
                endpoints.append({"alias": alias, "url": url, "token": token})
            result = await do_save_radar_endpoints(self.client, endpoints)
            yield event.plain_result(
                f"端点已添加/更新: alias={alias} url={url}  {result}"
            )

        elif action == "remove":
            new_endpoints = [e for e in endpoints if e.get("alias") != alias]
            if len(new_endpoints) == len(endpoints):
                yield event.plain_result(f"未找到别名为 '{alias}' 的端点，无法删除。")
                return
            result = await do_save_radar_endpoints(self.client, new_endpoints)
            yield event.plain_result(f"端点已删除: alias={alias}  {result}")

        else:
            yield event.plain_result(
                f"不支持的 action='{action}'，仅支持 add 或 remove。"
            )

    @llm_tool(name="inject_backend_to_instance")
    async def inject_backend(
        self,
        event: AstrMessageEvent,
        backend_alias: str,
        instance_keyword: str = "",
    ):
        """将 ncqq 实例接入指定 BotShepherd 后端端点。

        后端已由云端统一集成，本工具只负责将雷达端点库中的指定别名注入到目标实例的
        BotShepherd connection（热重载立即生效，无需重启容器）。
        适用场景：@某用户，给他的实例接入 gscore / astrbot / trss 等后端别名；
        也可不 @ 用户，此时默认操作发送者自己绑定的实例。
        若用户拥有多个实例且无法唯一定位，不要猜测，必须要求补充实例名。
        不适用于后端端点的新增删除，也不适用于实例绑定。

        Args:
            backend_alias (string): 雷达端点库中的后端别名关键字，如 'gscore'、'astrbot'、'trss'。
            instance_keyword (string): 可选实例关键字。目标用户有多个实例时应提供，用于唯一定位实例。
        """
        sender_id = str(event.get_sender_id())
        is_admin = event.is_admin()

        at_users = [
            comp.qq for comp in event.message_obj.message if isinstance(comp, At)
        ]
        if at_users:
            target_uid = str(at_users[0])
        else:
            # No @mention — fall back to the sender's own instances.
            target_uid = sender_id

        # Non-admin injecting → approval required
        if not is_admin:
            allowed = await self.get_allowed_instances(target_uid)
            if not allowed:
                if at_users:
                    yield event.plain_result(
                        f"操作被拒绝。用户 {target_uid} 未绑定任何可操作实例，无法提交审批。"
                    )
                else:
                    yield event.plain_result(
                        "操作被拒绝。您未绑定任何可操作的 ncqq 实例，"
                        "请联系管理员完成实例绑定后重试。"
                    )
                return
            # Find endpoint first to validate alias
            endpoints = await do_get_radar_endpoints(self.client)
            matched = next(
                (
                    e
                    for e in endpoints
                    if backend_alias.lower() in e.get("alias", "").lower()
                ),
                None,
            )
            if not matched:
                yield event.plain_result(
                    f"雷达端点库中不存在与 '{backend_alias}' 关联的端点，"
                    f"请先通过 manage_ncqq_backends 添加。"
                )
                return
            # Determine target instance
            target_instance_name = ""
            if instance_keyword:
                for inst in allowed:
                    if instance_keyword.lower() in inst.lower():
                        target_instance_name = inst
                        break
                if not target_instance_name:
                    yield event.plain_result(
                        f"实例匹配失败。用户所控实例 {allowed} 均无匹配项 ('{instance_keyword}')。"
                    )
                    return
            elif len(allowed) == 1:
                target_instance_name = allowed[0]
            else:
                yield event.plain_result(
                    f"多实例冲突。该用户存在多个可用实例 {allowed}，"
                    f"请提供 instance_keyword 以明确目标。"
                )
                return

            alias = matched["alias"]
            approval_id = await create_approval(
                self,
                action="inject_backend",
                params={"alias": alias, "instance_name": target_instance_name},
                requester_qq=sender_id,
                group_id=str(event.get_group_id() or ""),
                description=f"接入后端 {alias} → 实例 {target_instance_name}（归属: {target_uid}）",
            )
            admins = self.get_astrbot_admins()
            at_parts = "".join(f"@{a} " for a in admins) if admins else "@管理员 "
            yield event.plain_result(
                f"⚠️ 接入后端属于高权限操作，已提交审批。\n"
                f"审批 ID：{approval_id}\n"
                f"请 {at_parts}回复确认（引用本条消息或说'plana 批准 {approval_id}'）。"
            )
            return

        allowed = await self.get_allowed_instances(target_uid)
        if not allowed:
            if at_users:
                yield event.plain_result(
                    f"执行失败。用户 {target_uid} 未绑定可操作的实例。"
                )
            else:
                yield event.plain_result(
                    "执行失败。您未绑定任何可操作的 ncqq 实例。请联系管理员执行绑定后重试。"
                )
            return

        target_instance_name = ""
        if instance_keyword:
            for inst in allowed:
                if instance_keyword.lower() in inst.lower():
                    target_instance_name = inst
                    break
            if not target_instance_name:
                yield event.plain_result(
                    f"实例匹配失败。用户所控实例 {allowed} 均无匹配项 ('{instance_keyword}')。"
                )
                return
        else:
            if len(allowed) == 1:
                target_instance_name = allowed[0]
            else:
                yield event.plain_result(
                    f"多实例冲突。该用户存在多个可用实例 {allowed}，请提供 instance_keyword 以明确目标。"
                )
                return

        # 从服务端雷达端点库中按别名匹配端点
        endpoints = await do_get_radar_endpoints(self.client)
        matched = next(
            (
                e
                for e in endpoints
                if backend_alias.lower() in e.get("alias", "").lower()
            ),
            None,
        )
        if not matched:
            yield event.plain_result(
                f"雷达端点库中不存在与 '{backend_alias}' 关联的端点，请先通过 manage_ncqq_backends 添加。"
            )
            return

        alias = matched["alias"]
        # 后端统一由 BotShepherd 集成，固定走 target="bs"，conn_id = 实例名
        msg = await do_inject_by_alias(
            self.client,
            alias=alias,
            target="bs",
            conn_id=target_instance_name,
        )

        yield event.plain_result(
            f"注入完成:\n目标 QQ: {target_uid}\n实例: {target_instance_name}\n后端别名: {alias}\n结果: {msg}"
        )
