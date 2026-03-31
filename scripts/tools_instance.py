import base64
import re

from astrbot.api.all import AstrMessageEvent, Image, llm_tool

from .actions import do_create_instance, do_instance_action
from .approval import create_approval
from .config_manager import do_read_config, do_write_config
from .html_renderer import render_instances
from .interaction import (
    do_check_login_status,
    do_get_qrcode,
    is_qrcode_available_status,
)
from .monitoring import (
    do_confirm_instance_action,
    do_get_monitor,
    do_list_assets,
    do_list_files,
    do_list_instances,
)


class InstanceToolsMixin:
    _ACTION_EVENT_MAP = {
        "start": ["start"],
        "stop": ["stop", "die"],
        "restart": ["restart", "start"],
        "pause": ["pause"],
        "unpause": ["unpause", "start"],
        "kill": ["kill", "die"],
        "delete": ["destroy", "die"],
    }

    @llm_tool(name="list_ncqq_instances")
    async def list_instances(self, event: AstrMessageEvent):
        """列出 ncqq 管理器中的实例状态列表。

        适用于用户询问实例清单、运行状态、归属信息、在线情况时。
        不适用于执行启停、删除、配置写入。
        注意：如果用户请求"获取二维码""拉二维码""扫码"，不要调用此工具，应调用 get_ncqq_qrcode。
        """
        sender_id = str(event.get_sender_id())
        is_admin = event.is_admin()

        allowed = await self.get_allowed_instances(sender_id)

        result = await do_list_instances(self.client, allowed, is_admin)

        # Error string returned directly
        if isinstance(result, str):
            yield event.plain_result(result)
            return

        mapping = await self.get_user_mapping()
        nickname_count = sum(1 for data in mapping.values() if data.get("nickname"))

        rendered = await render_instances(result)

        if isinstance(rendered, bytes):
            b64 = base64.b64encode(rendered).decode()
            yield event.chain_result([Image.fromBase64(b64)])
            if nickname_count:
                yield event.plain_result(f"（含 {nickname_count} 条昵称记录）")
        else:
            prefix = (
                f"（含 {nickname_count} 条昵称记录）\n"
                if nickname_count
                else ""
            )
            yield event.plain_result(prefix + rendered)

    @llm_tool(name="ncqq_instance_action")
    async def instance_action(
        self,
        event: AstrMessageEvent,
        instance_names: str,
        action: str,
        delete_data: bool = False,
    ):
        """执行 ncqq 实例的基础管理动作，支持一次操作多个实例。

        仅在用户明确表达 start、stop、restart、pause、unpause、kill、delete 这类动作意图时调用。
        不要把查看状态、获取二维码、查询配置误判为实例动作。
        注意：如果用户请求"获取二维码""拉二维码""扫码"，不要调用此工具，应调用 get_ncqq_qrcode。

        Args:
            instance_names (string): 要操作的 ncqq 实例名，支持一次传入多个，用逗号分隔，例如 "bot1,bot2"。必须是明确的实例标识，不是用户昵称。
            action (string): 管理动作。只应为 start、stop、restart、pause、unpause、kill、delete 之一。pause/unpause 暂停/恢复容器进程；kill 强制终止；delete 销毁容器。
            delete_data (boolean): 仅在 action 为 delete 时有效。为 true 时同时删除该实例在管理器上的本地数据目录（QQ数据、配置、插件、缓存），不可恢复；为 false 时仅移除容器但保留数据。请根据用户意图判断：用户说"彻底删除""清除所有数据""删干净"等表达时设为 true；仅说"删除实例""移除容器"时设为 false。默认为 false。
        """

        names = [n.strip() for n in re.split(r"[,，、\s]+", instance_names) if n.strip()]
        if not names:
            yield event.plain_result("没有识别到可操作的实例名，请至少提供一个实例名。")
            return

        sender_id = str(event.get_sender_id())
        is_admin = event.is_admin()

        # delete is a destructive high-privilege action — requires admin or approval
        if action == "delete":
            if not is_admin:
                allowed = await self.get_allowed_instances(sender_id)
                rejected = [n for n in names if n not in allowed]
                if rejected:
                    yield event.plain_result(
                        f"以下实例不在你的可操作范围内：{'、'.join(rejected)}。如需删除，请联系管理员处理。"
                    )
                    return
                # 为每个实例单独创建审批记录
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
                yield event.plain_result(
                    self._approval_notice_batch("销毁实例", list(zip(names, ids)))
                )
                return
            # Admin executes directly
            results: list[str] = []
            cleaned: list[str] = []
            for n in names:
                msg = await do_instance_action(
                    self.client, n, action, delete_data=delete_data
                )
                if "失败" not in msg:
                    confirm = await do_confirm_instance_action(
                        self.client,
                        n,
                        self._ACTION_EVENT_MAP.get(action, [action]),
                    )
                    msg = f"{msg}\n{confirm}"
                results.append(msg)
                # 删除成功后自动清理 user_mapping 中对该实例的残留引用
                if "失败" not in msg:
                    cleaned.append(n)
            if cleaned:
                mapping = await self.get_user_mapping()
                changed = False
                for uid, data in mapping.items():
                    for inst_name in cleaned:
                        insts = data.get("instances", [])
                        if inst_name in insts:
                            insts.remove(inst_name)
                            changed = True
                if changed:
                    await self.save_user_mapping(mapping)
                    results.append(f"已自动解除所有用户与实例 {'、'.join(cleaned)} 的绑定。")
            yield event.plain_result("\n".join(results))
            return

        # Non-destructive actions: check binding
        if not is_admin:
            allowed = await self.get_allowed_instances(sender_id)
            rejected = [n for n in names if n not in allowed]
            if rejected:
                yield event.plain_result(
                    f"以下实例暂时不能由你操作：{'、'.join(rejected)}。请先联系管理员完成绑定。"
                )
                return

        results = []
        for n in names:
            msg = await do_instance_action(self.client, n, action)
            if "失败" not in msg:
                confirm = await do_confirm_instance_action(
                    self.client,
                    n,
                    self._ACTION_EVENT_MAP.get(action, [action]),
                )
                msg = f"{msg}\n{confirm}"
            results.append(msg)
        yield event.plain_result("\n".join(results))

    @llm_tool(name="get_ncqq_qrcode")
    async def get_qrcode(self, event: AstrMessageEvent, instance_name: str = ""):
        """获取 ncqq 实例的登录二维码图片。

        用户说"获取二维码""拉二维码""帮XX扫码""帮@用户获取二维码""给XX拉个码"
        等任何包含"二维码""扫码""登录码"关键词的请求时，必须直接调用此工具。
        本工具内部会自动检查实例是否需要扫码，无需先调用 check_login_status 或 list_instances。
        若消息中 @ 了某个用户，优先从该用户绑定实例中定位目标；候选唯一时自动选择。
        当存在多个候选实例时，不要猜测，必须要求用户补充实例名。

        Args:
            instance_name (string): 目标 ncqq 实例名。可为空；当消息里包含 @目标用户 且可唯一定位实例时允许省略。
        """
        sender_id = str(event.get_sender_id())
        is_admin = event.is_admin()

        target_user_id = self.get_first_at_user_id(event)
        if target_user_id:
            if not is_admin:
                yield event.plain_result(
                    "只有管理员才可以通过 @用户 的方式代为获取二维码。"
                )
                return
            candidate_instances = await self.get_instances_for_user(target_user_id)
            if not candidate_instances:
                yield event.plain_result("目标用户当前还没有绑定可用实例。")
                return
        else:
            candidate_instances = await self.get_allowed_instances(sender_id)
            if is_admin and instance_name:
                candidate_instances = []

        target_instance_name = instance_name.strip()
        if target_user_id and target_instance_name:
            matched = [
                inst
                for inst in candidate_instances
                if target_instance_name.lower() in inst.lower()
            ]
            if len(matched) == 1:
                target_instance_name = matched[0]
            elif len(matched) > 1:
                yield event.plain_result(
                    f"实例名匹配到多个候选：{'、'.join(matched)}。请补充更完整的实例名。"
                )
                return
            else:
                yield event.plain_result(
                    f"未在该用户的实例中找到与“{target_instance_name}”对应的结果，请确认实例名后重试。"
                )
                return

        if target_user_id and not target_instance_name:
            eligible_instances = []
            for inst in candidate_instances:
                status_payload = await do_check_login_status(self.client, inst)
                available, reason = is_qrcode_available_status(status_payload)
                if available:
                    login_label = (
                        "离线/待登录" if not status_payload.get("logged_in") else "在线"
                    )
                    eligible_instances.append((inst, login_label, reason))
            if len(eligible_instances) == 1:
                target_instance_name = eligible_instances[0][0]
            elif len(eligible_instances) > 1:
                summary = [name for name, _, _ in eligible_instances]
                yield event.plain_result(
                    f"目标用户有多个实例都可能需要扫码：{'、'.join(summary)}。请补充实例名后再试。"
                )
                return
            else:
                yield event.plain_result(
                    "目标用户当前没有可直接拉取二维码的掉线/待登录实例。"
                )
                return

        if not target_instance_name:
            yield event.plain_result(
                "请直接提供实例名；如果你是管理员，也可以在消息中 @目标用户 让我帮你定位实例。"
            )
            return

        if not is_admin and not target_user_id:
            if target_instance_name not in candidate_instances:
                yield event.plain_result("该实例不在你的可操作范围内，请确认实例名或联系管理员。")
                return

        status_payload = await do_check_login_status(self.client, target_instance_name)
        available, reason = is_qrcode_available_status(status_payload)
        if not available:
            yield event.plain_result(
                f"实例 {target_instance_name} 当前不需要重新扫码。{reason or '如仍有异常，请稍后再检查登录状态。'}"
            )
            return

        results = await do_get_qrcode(self.client, target_instance_name)
        for item in results:
            if isinstance(item, str):
                yield event.plain_result(item)
            else:
                yield event.chain_result([item])

    @llm_tool(name="check_ncqq_login_status")
    async def check_login_status(self, event: AstrMessageEvent, instance_names: str):
        """刷新并检查 ncqq 实例的实时登录状态，支持一次检查多个实例。

        适用于用户询问某实例是否在线、是否掉线、是否扫码成功、是否仍需登录时。
        此工具只返回状态文字信息，不返回二维码图片。
        注意：如果用户请求"获取二维码""拉二维码""扫码"，不要调用此工具，应调用 get_ncqq_qrcode。

        Args:
            instance_names (string): 要检查登录状态的 ncqq 实例名，支持一次传入多个，用逗号分隔，例如 "bot1,bot2"。
        """

        names = [n.strip() for n in re.split(r"[,，、\s]+", instance_names) if n.strip()]
        if not names:
            yield event.plain_result("没有识别到可操作的实例名，请至少提供一个实例名。")
            return

        sender_id = str(event.get_sender_id())
        is_admin = event.is_admin()

        if not is_admin:
            allowed = await self.get_allowed_instances(sender_id)
            rejected = [n for n in names if n not in allowed]
            if rejected:
                yield event.plain_result(
                    f"你暂时不能查看这些实例的登录状态：{'、'.join(rejected)}。"
                )
                return

        lines: list[str] = []
        for name in names:
            payload = await do_check_login_status(self.client, name)
            logged_in = payload.get("logged_in", False)
            uin = payload.get("uin", "")
            nickname = payload.get("nickname", "")
            if payload.get("status") == "error":
                status_text = "登录状态暂时获取失败，请稍后重试。"
            elif logged_in:
                label = f"{nickname}({uin})" if uin else nickname or "已登录"
                status_text = f"已在线，当前账号：{label}"
            else:
                status_text = "当前未登录，可能需要重新扫码。"
            lines.append(f"[{name}] 登录状态：{status_text}")
        yield event.plain_result("\n".join(lines))

    @llm_tool(name="monitor_ncqq_usage")
    async def get_monitor(
        self, event: AstrMessageEvent, instance_name: str, fetch_logs: bool = False
    ):
        """读取 ncqq 实例的监控信息或尾部日志。

        适用于管理员查看资源占用、运行监控、容器日志。
        不适用于普通状态问答、二维码获取、实例启停。

        Args:
            instance_name (string): 要查看监控信息的 ncqq 实例名。
            fetch_logs (boolean): 为 true 时返回尾部日志；为 false 时返回监控摘要。
        """
        if not event.is_admin():
            yield event.plain_result("此功能仅限管理员查看监控与日志。")
            return

        msg = await do_get_monitor(self.client, instance_name, fetch_logs)
        yield event.plain_result(msg)

    @llm_tool(name="create_ncqq_instance")
    async def create_instance(self, event: AstrMessageEvent, instance_names: str):
        """创建新的 ncqq 实例，支持一次创建多个。

        仅在用户明确要求创建、初始化、生成实例时调用。
        不要把绑定用户、接入后端、拉取二维码误判为创建实例。
        管理员直接执行；其他用户提交审批由管理员确认后执行。

        Args:
            instance_names (string): 要创建的 ncqq 实例名。支持一次传入多个，用逗号分隔，例如 "bot1,bot2,bot3"。
        """

        names = [n.strip() for n in re.split(r"[,，、\s]+", instance_names) if n.strip()]
        if not names:
            yield event.plain_result("没有识别到可操作的实例名，请至少提供一个实例名。")
            return

        if not event.is_admin():
            sender_id = str(event.get_sender_id())
            label = "、".join(names)
            approval_id = await create_approval(
                self,
                action="create",
                params={"instance_names": names},
                requester_qq=sender_id,
                group_id=str(event.get_group_id() or ""),
                description=f"创建实例 {label}（申请者: {sender_id}）",
            )
            yield event.plain_result(
                self._approval_notice_single("创建实例", approval_id)
            )
            return

        results: list[str] = []
        for name in names:
            msg = await do_create_instance(self.client, name)
            results.append(msg)
        yield event.plain_result("\n".join(results))

    @llm_tool(name="list_ncqq_assets")
    async def list_assets(self, event: AstrMessageEvent):
        """列出 ncqq 管理节点上的基础资产。

        适用于管理员查询宿主机中的镜像、容器等基础资产清单。
        不适用于具体实例状态、二维码、后端接入。
        """
        if not event.is_admin():
            yield event.plain_result("此功能仅限管理员使用。")
            return

        msg = await do_list_assets(self.client)
        yield event.plain_result(msg)

    @llm_tool(name="read_ncqq_config")
    async def read_config(
        self,
        event: AstrMessageEvent,
        instance_name: str,
        file_name: str = "onebot11_uin.json",
    ):
        """只读查看 ncqq 实例容器内的配置文件内容。

        适用于管理员排查配置、核对文件内容、读取实例内部配置。
        不会修改文件内容。

        Args:
            instance_name (string): 要读取配置的 ncqq 实例名。
            file_name (string): 容器内要读取的文件名。默认值为 onebot11_uin.json。
        """
        if not event.is_admin():
            yield event.plain_result("此功能仅限管理员使用。")
            return

        msg = await do_read_config(self.client, instance_name, file_name)
        yield event.plain_result(msg)

    @llm_tool(name="write_ncqq_config")
    async def write_config(
        self,
        event: AstrMessageEvent,
        instance_name: str,
        file_name: str,
        file_content: str,
    ):
        """覆写 ncqq 实例容器内的配置文件。

        高风险操作，不适用于读取配置、查看状态、普通问答。
        管理员直接执行；绑定用户可对自己绑定的实例提交审批，由管理员确认后执行。
        未绑定该实例的用户无法提交此操作。

        Args:
            instance_name (string): 要写入配置的 ncqq 实例名。
            file_name (string): 容器内要写入的目标文件名。
            file_content (string): 要完整写入的文件内容，应为最终内容而不是增量片段。
        """
        if not event.is_admin():
            sender_id = str(event.get_sender_id())
            # Verify the requester has binding access to this instance
            allowed = await self.get_allowed_instances(sender_id)
            if instance_name not in allowed:
                yield event.plain_result(
                    f"实例 {instance_name} 当前不在你的可操作范围内，暂时不能提交配置修改申请。"
                )
                return
            approval_id = await create_approval(
                self,
                action="write_config",
                params={
                    "instance_name": instance_name,
                    "file_name": file_name,
                    "file_content": file_content,
                },
                requester_qq=sender_id,
                group_id=str(event.get_group_id() or ""),
                description=f"覆写配置 {instance_name}/{file_name}（申请者: {sender_id}）",
            )
            yield event.plain_result(
                self._approval_notice_single("覆写配置", approval_id)
            )
            return

        msg = await do_write_config(self.client, instance_name, file_name, file_content)
        yield event.plain_result(msg)

    @llm_tool(name="list_ncqq_files")
    async def list_files(
        self,
        event: AstrMessageEvent,
        instance_name: str,
        path: str = "",
    ):
        """列出 ncqq 实例数据目录下的文件和子目录。

        适用于管理员排查文件、查看配置目录结构、核对数据文件。
        不适用于读取文件内容（应使用 read_ncqq_config）或执行实例动作。

        Args:
            instance_name (string): 要查看文件目录的 ncqq 实例名。
            path (string): 相对于实例数据根目录的路径，留空表示根目录。例如 'config' 或 'qq_data'。
        """
        if not event.is_admin():
            yield event.plain_result("此功能仅限管理员使用。")
            return

        msg = await do_list_files(self.client, instance_name, path)
        yield event.plain_result(msg)
