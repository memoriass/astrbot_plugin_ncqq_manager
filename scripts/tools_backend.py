import re

from astrbot.api.all import AstrMessageEvent, At, llm_tool

from .actions import do_inject_by_alias
from .approval import create_approval
from .monitoring import do_get_radar_endpoints, do_save_radar_endpoints


class BackendToolsMixin:
    @llm_tool(name="bind_ncqq_instance")
    async def bind_instance(
        self, event: AstrMessageEvent, instance_names: str, nickname: str = ""
    ):
        """将一个或多个 ncqq 实例绑定给消息中被 @ 的目标用户。

        仅适用于管理员分配实例归属权的场景。
        必须依赖消息里的真实 @ 目标用户，不要在没有 At 组件时猜测绑定对象。
        不适用于实例启停、二维码获取、后端接入。

        Args:
            instance_names (string): 要绑定给目标用户的 ncqq 实例名，支持一次传入多个，用逗号分隔，例如 "bot1,bot2"。
            nickname (string): 可选昵称。若能从上下文确定目标用户称呼，可一并记录。
        """

        names = [n.strip() for n in re.split(r"[,，、\s]+", instance_names) if n.strip()]
        if not names:
            yield event.plain_result("没有识别到可绑定的实例名，请至少提供一个实例名。")
            return

        label = "、".join(names)

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
                    "instance_names": names,
                    "nickname": nickname,
                },
                requester_qq=sender_id,
                group_id=str(event.get_group_id() or ""),
                description=f"绑定实例 {label} → QQ {target_uid}（申请者: {sender_id}）",
            )
            yield event.plain_result(
                self._approval_notice_single("绑定实例", approval_id)
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

        added: list[str] = []
        for name in names:
            if name not in mapping[target_uid]["instances"]:
                mapping[target_uid]["instances"].append(name)
                added.append(name)

        if nickname:
            mapping[target_uid]["nickname"] = nickname

        await self.save_user_mapping(mapping)

        added_str = "、".join(added) if added else "本次没有新增实例"
        nickname_text = nickname or "未设置"
        yield event.plain_result(
            f"已完成绑定更新：目标用户 {target_uid}；新增实例：{added_str}；昵称：{nickname_text}。"
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
            yield event.plain_result("此功能仅限管理员修改昵称。")
            return
        mapping = await self.get_user_mapping()

        if qq_id not in mapping:
            mapping[qq_id] = {"nickname": "", "instances": []}

        mapping[qq_id]["nickname"] = nickname
        await self.save_user_mapping(mapping)
        yield event.plain_result(f"昵称已更新：{nickname}（QQ {qq_id}）。")

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
                description=f"后端端点{action}：{alias}（申请者: {sender_id}）",
            )
            yield event.plain_result(
                self._approval_notice_single("管理后端端点", approval_id)
            )
            return

        endpoints = await do_get_radar_endpoints(self.client)

        if action == "add":
            if not url:
                yield event.plain_result("添加失败，请补充后端地址。")
                return
            # 已存在则更新，否则追加
            existing = next((e for e in endpoints if e.get("alias") == alias), None)
            if existing:
                existing["url"] = url
                existing["token"] = token
            else:
                endpoints.append({"alias": alias, "url": url, "token": token})
            result = await do_save_radar_endpoints(self.client, endpoints)
            yield event.plain_result(f"后端端点 {alias} 已保存。{result}")

        elif action == "remove":
            new_endpoints = [e for e in endpoints if e.get("alias") != alias]
            if len(new_endpoints) == len(endpoints):
                yield event.plain_result(f"未找到名为 {alias} 的后端端点，暂未执行删除。")
                return
            result = await do_save_radar_endpoints(self.client, new_endpoints)
            yield event.plain_result(f"后端端点 {alias} 已删除。{result}")

        else:
            yield event.plain_result(
                f"不支持该操作：{action}。目前仅支持 add 或 remove。"
            )

    @llm_tool(name="inject_backend_to_instance")
    async def inject_backend(
        self,
        event: AstrMessageEvent,
        backend_alias: str,
        instance_names: str = "",
        instance_keyword: str = "",
    ):
        """将一个或多个 ncqq 实例接入指定 BotShepherd 后端端点。

        后端已由云端统一集成，本工具只负责将雷达端点库中的指定别名注入到目标实例的
        BotShepherd connection（热重载立即生效，无需重启容器）。
        适用场景：
        1. 直接指定实例名（可多个）：给 xxxx、bbbb 注入 gscore；
        2. @某用户，给他的实例接入后端（自动对该用户所有绑定实例执行）；
        3. 不 @ 用户，默认操作发送者自己绑定的实例。
        不适用于后端端点的新增删除，也不适用于实例绑定。

        Args:
            backend_alias (string): 雷达端点库中的后端别名关键字，如 'gscore'、'astrbot'、'trss'。
            instance_names (string): 直接指定要注入的实例名，支持多个用逗号分隔，例如 "bot1,bot2"。填写时跳过用户绑定查找，直接批量注入。
            instance_keyword (string): 通过 @用户 路径时用于从该用户的多个实例中过滤目标，仅 instance_names 为空时生效。为空时对该用户所有绑定实例全部注入。
        """

        sender_id = str(event.get_sender_id())
        is_admin = event.is_admin()

        # --- 公共：验证 backend_alias ---
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
                f"未找到名为 {backend_alias} 的后端端点，请先让管理员完成配置。"
            )
            return
        alias = matched["alias"]

        # --- 路径 A：直接指定实例名 ---
        direct_names = [
            n.strip() for n in re.split(r"[,，、\s]+", instance_names) if n.strip()
        ] if instance_names.strip() else []

        if direct_names:
            if not is_admin:
                # 非管理员走审批，为每个实例单独创建
                ids = []
                for n in direct_names:
                    aid = await create_approval(
                        self,
                        action="inject_backend",
                        params={"alias": alias, "instance_name": n},
                        requester_qq=sender_id,
                        group_id=str(event.get_group_id() or ""),
                        description=f"接入后端 {alias} → 实例 {n}（申请者: {sender_id}）",
                    )
                    ids.append(aid)
                yield event.plain_result(
                    self._approval_notice_batch("接入后端", list(zip(direct_names, ids)))
                )
                return
            results: list[str] = []
            for n in direct_names:
                msg = await do_inject_by_alias(
                    self.client, alias=alias, target="bs", conn_id=n
                )
                results.append(f"[{n}] {msg}")
            yield event.plain_result(
                f"已为后端端点 {alias} 完成批量接入：\n" + "\n".join(results)
            )
            return

        # --- 路径 B：通过 @用户 / 自身 查找实例 ---
        at_users = [
            comp.qq for comp in event.message_obj.message if isinstance(comp, At)
        ]
        target_uid = str(at_users[0]) if at_users else sender_id

        allowed = await self.get_allowed_instances(target_uid)
        if not allowed:
            if at_users:
                yield event.plain_result(
                    f"用户 {target_uid} 当前没有可操作的实例。"
                )
            else:
                yield event.plain_result(
                    "你当前还没有可操作的实例，请先联系管理员完成绑定。"
                )
            return

        # 确定目标实例列表
        if instance_keyword:
            # 模糊匹配筛选
            targets = [
                inst for inst in allowed
                if instance_keyword.lower() in inst.lower()
            ]
            if not targets:
                yield event.plain_result(
                    f"在该用户的实例中没有找到与“{instance_keyword}”对应的结果，请补充更准确的实例名。"
                )
                return
        else:
            # 无关键字 → 对该用户所有绑定实例执行
            targets = allowed

        if not is_admin:
            # 非管理员：为每个目标实例创建审批
            ids = []
            for n in targets:
                aid = await create_approval(
                    self,
                    action="inject_backend",
                    params={"alias": alias, "instance_name": n},
                    requester_qq=sender_id,
                    group_id=str(event.get_group_id() or ""),
                    description=f"接入后端 {alias} → 实例 {n}（归属: {target_uid}）",
                )
                ids.append(aid)
            yield event.plain_result(
                self._approval_notice_batch("接入后端", list(zip(targets, ids)))
            )
            return

        # 管理员直接执行
        results = []
        for n in targets:
            msg = await do_inject_by_alias(
                self.client, alias=alias, target="bs", conn_id=n
            )
            results.append(f"[{n}] {msg}")
        yield event.plain_result(
            f"已为用户 {target_uid} 完成后端接入：\n" + "\n".join(results)
        )


    @llm_tool(name="unbind_ncqq_instance")
    async def unbind_instance(
        self, event: AstrMessageEvent, instance_names: str
    ):
        """将一个或多个 ncqq 实例从消息中被 @ 的目标用户解绑。

        仅管理员可用。必须依赖消息里的真实 @ 目标用户。
        用于取消用户与实例的归属关系，不会删除实例本身。

        Args:
            instance_names (string): 要解绑的 ncqq 实例名，支持一次传入多个，用逗号分隔，例如 "bot1,bot2"。
        """

        if not event.is_admin():
            yield event.plain_result("解绑实例仅管理员可操作。")
            return

        names = [n.strip() for n in re.split(r"[,，、\s]+", instance_names) if n.strip()]
        if not names:
            yield event.plain_result("没有识别到可解绑的实例名，请至少提供一个实例名。")
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
        if target_uid not in mapping or not mapping[target_uid].get("instances"):
            yield event.plain_result(
                f"用户 {target_uid} 当前没有已绑定的实例，无需解绑。"
            )
            return

        current = mapping[target_uid]["instances"]
        removed: list[str] = []
        not_found: list[str] = []
        for name in names:
            if name in current:
                current.remove(name)
                removed.append(name)
            else:
                not_found.append(name)

        await self.save_user_mapping(mapping)

        parts: list[str] = [f"目标用户：{target_uid}"]
        if removed:
            parts.append(f"已解绑：{'、'.join(removed)}")
        if not_found:
            parts.append(f"未找到并已跳过：{'、'.join(not_found)}")
        remaining = current if current else ["无"]
        parts.append(f"剩余绑定：{'、'.join(remaining)}")

        yield event.plain_result("解绑已完成。" + "；".join(parts))