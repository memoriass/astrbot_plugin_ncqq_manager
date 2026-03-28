from astrbot.api.all import AstrMessageEvent, At, llm_tool

from .actions import do_inject_backend


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
        role = await self.context.get_user_role(event.get_sender_id())
        if role not in ["admin", "owner"]:
            yield event.plain_result("权限不足。仅限管理员执行分配操作。")
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
        role = await self.context.get_user_role(event.get_sender_id())
        if role not in ["admin", "owner"]:
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
        name: str,
        url: str = "",
        aliases: str = "",
    ):
        """管理 ncqq 管理器中的后端模板注册表。

        仅适用于管理员新增或删除后端模板。
        不适用于把实例接入后端；真正执行接入应调用 inject_backend_to_instance。

        Args:
            action (string): 管理动作，只应为 add 或 remove。
            name (string): 后端模板名称。
            url (string): 当 action=add 时必填的后端地址。
            aliases (string): 可选别名列表，使用英文逗号分隔。
        """
        role = await self.context.get_user_role(event.get_sender_id())
        if role not in ["admin", "owner"]:
            yield event.plain_result("权限不足。仅限管理员管理后端配置。")
            return

        registry = await self.get_backends_registry()
        if action == "add":
            if not url:
                yield event.plain_result("添加失败。缺乏 url 参数。")
                return
            registry[name] = {
                "url": url,
                "aliases": [a.strip() for a in aliases.split(",") if a.strip()]
                if aliases
                else [],
            }
            await self.save_backends_registry(registry)
            yield event.plain_result(f"配置保存成功。模板: {name}。")
        elif action == "remove":
            if name in registry:
                del registry[name]
                await self.save_backends_registry(registry)
                yield event.plain_result(f"配置删除成功。模板: {name}。")
            else:
                yield event.plain_result("配置不存在，无法删除。")

    @llm_tool(name="inject_backend_to_instance")
    async def inject_backend(
        self, event: AstrMessageEvent, backend_keyword: str, instance_keyword: str = ""
    ):
        """将消息中被 @ 用户绑定的 ncqq 实例接入指定后端模板。

        适用于管理员执行接入、对接、入网、挂后端等操作。
        必须依赖消息中的真实 @ 目标用户；若用户拥有多个实例且无法唯一定位，不要猜测，必须要求补充实例名。
        不适用于后端模板的新增删除，也不适用于实例绑定。

        Args:
            backend_keyword (string): 后端模板名称或别名关键字。
            instance_keyword (string): 可选实例关键字。目标用户有多个实例时应提供，用于唯一定位实例。
        """
        role = await self.context.get_user_role(event.get_sender_id())
        if role not in ["admin", "owner"]:
            yield event.plain_result("权限不足。仅限管理员执运维路由对接。")
            return

        at_users = [
            comp.qq for comp in event.message_obj.message if isinstance(comp, At)
        ]
        if not at_users:
            yield event.plain_result("无作用目标。请在会话中 @提及 对应用户。")
            return
        target_uid = str(at_users[0])

        mapping = await self.get_user_mapping()
        allowed = mapping.get(target_uid, {}).get("instances", [])
        if not allowed:
            yield event.plain_result(
                f"执行失败。用户 {target_uid} 未绑定可操作的实例。"
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

        registry = await self.get_backends_registry()
        matched_backend = None
        for b_name, b_info in registry.items():
            if (
                backend_keyword.lower() in b_name.lower()
                or backend_keyword.lower() == b_name.lower()
            ):
                matched_backend = (b_name, b_info)
                break
            for alias in b_info.get("aliases", []):
                if (
                    backend_keyword.lower() in alias.lower()
                    or backend_keyword.lower() == alias.lower()
                ):
                    matched_backend = (b_name, b_info)
                    break

        if not matched_backend:
            yield event.plain_result(
                f"注册表中不存在与 '{backend_keyword}' 关联的后端模板。"
            )
            return

        b_name, b_info = matched_backend

        msg = await do_inject_backend(
            self.client, target_instance_name, b_name, b_info["url"]
        )

        yield event.plain_result(
            f"对接动作流完成反馈:\n目标 QQ: {target_uid}\n选配实例: {target_instance_name}\n应用模板: {b_name}\n结果: {msg}"
        )
