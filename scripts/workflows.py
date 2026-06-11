"""Flow-oriented internal workflows for ncqq manager.

The LLM-facing surface is intentionally small: it chooses a business flow,
fills slots, and this module runs deterministic branches with permission,
existence, backend, login, and approval checks inside the workflow.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator

from astrbot.api.all import AstrMessageEvent

from .approval import create_approval
from .interaction import do_check_login_status
from .monitoring import do_confirm_instance_action, do_get_radar_endpoints


@dataclass(slots=True)
class WorkflowRequest:
    workflow: str
    target: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    source: str = "tool"


@dataclass(frozen=True, slots=True)
class CompiledWorkflow:
    workflow: str
    title: str
    purpose: str
    admin_only: bool = False


COMPILED_WORKFLOWS: dict[str, CompiledWorkflow] = {
    "create_instance": CompiledWorkflow(
        workflow="create_instance",
        title="实例创建流程",
        purpose="创建或接续创建实例，按条件绑定用户、启动实例、接入后端、拉取二维码。",
    ),
    "relogin_instance": CompiledWorkflow(
        workflow="relogin_instance",
        title="掉线重登流程",
        purpose="检查登录状态，离线时按条件拉取二维码。",
    ),
    "control_instance": CompiledWorkflow(
        workflow="control_instance",
        title="实例控制流程",
        purpose="启动、停止、重启等生命周期操作，并按条件复查状态。",
    ),
    "connect_backend": CompiledWorkflow(
        workflow="connect_backend",
        title="后端接入流程",
        purpose="校验后端别名和目标实例后，把已有端点接入实例。",
    ),
    "check_instance": CompiledWorkflow(
        workflow="check_instance",
        title="实例检测流程",
        purpose="按实例存在、登录、资源、日志顺序排查问题。",
        admin_only=True,
    ),
    "list_instances": CompiledWorkflow(
        workflow="list_instances",
        title="实例列表流程",
        purpose="查看实例状态与绑定关系。",
    ),
    "check_backends": CompiledWorkflow(
        workflow="check_backends",
        title="后端端点检测流程",
        purpose="查看已配置后端端点，不显示 token 明文。",
    ),
    "check_manager": CompiledWorkflow(
        workflow="check_manager",
        title="管理器健康检测流程",
        purpose="检测 ncqq-manager、Docker、状态引擎和基础依赖状态。",
        admin_only=True,
    ),
    "check_botshepherd": CompiledWorkflow(
        workflow="check_botshepherd",
        title="BotShepherd 检测流程",
        purpose="检测 BotShepherd 进程、激活状态和心跳。",
        admin_only=True,
    ),
    "check_bot_runtime": CompiledWorkflow(
        workflow="check_bot_runtime",
        title="Bot 运行态检测流程",
        purpose="查看已知 Bot 的 WS 连接和账号运行态。",
        admin_only=True,
    ),
    "read_bot_messages": CompiledWorkflow(
        workflow="read_bot_messages",
        title="Bot 消息读取流程",
        purpose="读取指定 Bot 的最近消息缓存。",
        admin_only=True,
    ),
    "audit_operations": CompiledWorkflow(
        workflow="audit_operations",
        title="操作审计流程",
        purpose="读取最近操作日志，排查谁做过什么变更。",
        admin_only=True,
    ),
    "inspect_resources": CompiledWorkflow(
        workflow="inspect_resources",
        title="资源检测流程",
        purpose="查看管理器镜像和节点资产。",
        admin_only=True,
    ),
    "read_instance_config": CompiledWorkflow(
        workflow="read_instance_config",
        title="配置读取流程",
        purpose="查看实例文件树和指定配置文件摘要。",
        admin_only=True,
    ),
    "delete_instance": CompiledWorkflow(
        workflow="delete_instance",
        title="实例销毁流程",
        purpose="显式确认后删除实例，并复用审批与解绑逻辑。",
    ),
    "review_approvals": CompiledWorkflow(
        workflow="review_approvals",
        title="审批队列流程",
        purpose="查看待审批的高权限流程请求。",
        admin_only=True,
    ),
}

_ACTION_ALIASES: dict[str, str] = {
    "start": "start",
    "启动": "start",
    "stop": "stop",
    "停止": "stop",
    "restart": "restart",
    "reboot": "restart",
    "重启": "restart",
    "pause": "pause",
    "暂停": "pause",
    "unpause": "unpause",
    "resume": "unpause",
    "恢复运行": "unpause",
    "kill": "kill",
    "强杀": "kill",
}

_LIFECYCLE_ACTIONS = {"start", "stop", "restart", "pause", "unpause", "kill"}


def _canonical_key(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _split_words(value: str) -> list[str]:
    return [part for part in str(value or "").split() if part]


def _normalize_workflow(value: str) -> str:
    return _canonical_key(value)


def _normalize_action(value: Any) -> str:
    return _ACTION_ALIASES.get(_canonical_key(str(value or "")), _canonical_key(str(value or "")))


def _parse_kv_words(value: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for token in _split_words(value):
        if "=" not in token:
            continue
        key, raw = token.split("=", 1)
        key = key.strip()
        if key:
            payload[key] = raw.strip()
    return payload


def _parse_params(params: str | dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(params, dict):
        return dict(params)
    if not params:
        return {}
    text = str(params).strip()
    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        parsed = _parse_kv_words(text)
        if parsed:
            parsed["_raw"] = text
            return parsed
        return {"_raw": text}
    return payload if isinstance(payload, dict) else {}


def _first_text(params: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = params.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _get_bool(params: dict[str, Any], *keys: str, default: bool = False) -> bool:
    for key in keys:
        if key not in params:
            continue
        value = params.get(key)
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y", "on", "需要", "是"}:
            return True
        if text in {"0", "false", "no", "n", "off", "不", "否", "不需要"}:
            return False
    return default


def workflow_from_tool(
    workflow: str,
    target: str = "",
    params: str | dict[str, Any] | None = "",
) -> WorkflowRequest:
    """Build a workflow request from the LLM tool shape."""
    payload = _parse_params(params)
    selected = _normalize_workflow(workflow or str(payload.get("workflow") or ""))

    resolved_target = str(
        target
        or payload.get("target")
        or payload.get("instance_name")
        or payload.get("name")
        or ""
    ).strip()
    return WorkflowRequest(
        workflow=selected,
        target=resolved_target,
        params=payload,
        source="tool",
    )


def workflow_from_cli(sub: str, args: str = "") -> WorkflowRequest | None:
    """Build a workflow request from `/ncqq <flow> [args...]`."""
    workflow = _normalize_workflow(sub)
    if workflow not in COMPILED_WORKFLOWS:
        return None

    args = str(args or "").strip()
    parts = _split_words(args)
    params: dict[str, Any] = {}
    target = ""

    if workflow == "create_instance":
        target = parts[0] if parts else ""
        if len(parts) > 1:
            params["backend_alias"] = parts[1]
        params["qrcode"] = True
    elif workflow == "relogin_instance":
        target = args
    elif workflow == "control_instance":
        params["action"] = _normalize_action(parts[0] if parts else "")
        target = " ".join(parts[1:]) if len(parts) > 1 else ""
    elif workflow == "connect_backend":
        params["backend_alias"] = parts[0] if parts else ""
        target = " ".join(parts[1:]) if len(parts) > 1 else ""
    elif workflow == "check_instance":
        target = parts[0] if parts else args
    elif workflow in {
        "list_instances",
        "check_backends",
        "check_manager",
        "check_botshepherd",
        "check_bot_runtime",
        "inspect_resources",
        "review_approvals",
    }:
        target = ""
    elif workflow == "read_bot_messages":
        target = parts[0] if parts else ""
        params["limit"] = parts[1] if len(parts) > 1 else "20"
    elif workflow == "audit_operations":
        target = ""
        params["limit"] = parts[0] if parts else "10"
    elif workflow == "read_instance_config":
        target = parts[0] if parts else ""
        params["file_name"] = parts[1] if len(parts) > 1 else ""
        params["path"] = parts[2] if len(parts) > 2 else ""
    elif workflow == "delete_instance":
        target = parts[0] if parts else ""
        lowered = {p.lower() for p in parts[1:]}
        params["confirm"] = bool(lowered & {"confirm", "yes", "true", "确认"})
        params["delete_data"] = bool(lowered & {"data", "clean", "all", "彻底", "数据"})
    elif workflow == "review_approvals":
        target = ""

    return WorkflowRequest(workflow=workflow, target=target, params=params, source="cli")


async def _resolve_target(
    plugin: Any,
    event: AstrMessageEvent,
    request: WorkflowRequest,
    *,
    allow_single_bound: bool = True,
) -> tuple[bool, str]:
    target = str(
        request.target
        or request.params.get("target")
        or request.params.get("instance_name")
        or request.params.get("name")
        or ""
    ).strip()
    if target:
        return True, target
    if not allow_single_bound:
        return True, ""

    bound = await plugin.get_allowed_instances(str(event.get_sender_id()))
    if len(bound) == 1:
        return True, bound[0]
    if len(bound) > 1:
        return False, "你绑定了多个 ncqq 实例，请明确指定其中一个：" + ", ".join(bound)
    return True, ""


async def _ensure_instance_access(
    plugin: Any,
    event: AstrMessageEvent,
    instance_name: str,
) -> tuple[bool, str]:
    if event.is_admin():
        return True, ""
    allowed = await plugin.get_allowed_instances(str(event.get_sender_id()))
    if instance_name in allowed:
        return True, ""
    return False, f"实例 {instance_name} 不在你的可操作范围内。"


def _format_workflow_list() -> str:
    lines = ["可用 ncqq workflow："]
    for item in COMPILED_WORKFLOWS.values():
        suffix = "（管理员）" if item.admin_only else ""
        lines.append(f"- {item.workflow}: {item.title}{suffix} - {item.purpose}")
    lines.append("每个 workflow 只覆盖一个能力方向；底层 API 调用作为流程内部步骤。")
    return "\n".join(lines)


async def _manager_get(plugin: Any, endpoint: str) -> tuple[bool, Any]:
    try:
        return True, await plugin.client.make_request("GET", endpoint)
    except Exception as exc:
        return False, str(exc)


async def _list_containers(plugin: Any) -> tuple[bool, list[dict[str, Any]], str]:
    ok, payload = await _manager_get(plugin, "/api/containers")
    if not ok:
        return False, [], str(payload)
    if isinstance(payload, dict):
        containers = payload.get("containers", [])
    elif isinstance(payload, list):
        containers = payload
    else:
        containers = []
    if not isinstance(containers, list):
        return False, [], "容器列表返回格式异常。"
    return True, [item for item in containers if isinstance(item, dict)], ""


def _container_name(item: dict[str, Any]) -> str:
    return str(item.get("name") or item.get("container_name") or "").strip().lstrip("/")


def _find_container(containers: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    wanted = name.strip().lstrip("/")
    for item in containers:
        if _container_name(item) == wanted:
            return item
    return None


def _container_state(item: dict[str, Any] | None) -> str:
    if not isinstance(item, dict):
        return ""
    return str(item.get("status") or item.get("state") or item.get("container_status") or "").lower()


def _is_running(item: dict[str, Any] | None) -> bool:
    state = _container_state(item)
    return state == "running" or state.startswith("up")


def _format_container_brief(item: dict[str, Any]) -> str:
    name = _container_name(item) or "-"
    state = item.get("status") or item.get("state") or "-"
    online = item.get("bot_online")
    uin = item.get("bot_uin") or item.get("uin") or "-"
    return f"{name}: container={state}, bot_online={_fmt_bool(online)}, uin={uin}"


def _format_login_status(instance_name: str, payload: dict[str, Any]) -> str:
    if payload.get("status") == "error":
        msg = str(payload.get("msg") or "登录状态检查失败。")
        return f"{instance_name}: {msg}"
    if payload.get("logged_in"):
        uin = str(payload.get("uin") or "")
        nickname = str(payload.get("nickname") or "")
        label = f"{nickname}({uin})" if uin else nickname or "已登录"
        return f"{instance_name}: 当前在线，账号 {label}。"
    return f"{instance_name}: 当前未登录，可以继续获取二维码。"


def _format_backend_list(endpoints: list[dict[str, Any]]) -> str:
    if not endpoints:
        return "当前没有配置任何后端端点。"
    lines = [f"后端端点（{len(endpoints)}）："]
    for item in endpoints:
        alias = str(item.get("alias") or "-")
        url = str(item.get("url") or "-")
        token_state = "yes" if item.get("token") else "no"
        lines.append(f"- {alias}: {url} token={token_state}")
    return "\n".join(lines)


def _format_backend_aliases(endpoints: list[dict[str, Any]]) -> str:
    aliases = [str(item.get("alias") or "").strip() for item in endpoints]
    aliases = [alias for alias in aliases if alias]
    return ", ".join(aliases[:20]) if aliases else "无"


def _as_int(value: Any, default: int, minimum: int = 1, maximum: int = 200) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _fmt_bool(value: Any) -> str:
    return "yes" if bool(value) else "no"


def _fmt_ts(value: Any) -> str:
    try:
        ts = float(value)
    except (TypeError, ValueError):
        return "-"
    if ts <= 0:
        return "-"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _format_check_manager(payload: dict[str, Any]) -> str:
    botshepherd = payload.get("botshepherd") or {}
    state_engine = payload.get("state_engine") or {}
    metrics = payload.get("metrics") or {}
    reasons = payload.get("degraded_reasons") or []
    lines = [
        "管理器健康检查：",
        f"- status: {payload.get('status', '-')}",
        f"- degraded_reasons: {', '.join(map(str, reasons)) if reasons else 'none'}",
        f"- uptime: {payload.get('uptime', '-')}s",
        f"- docker: {_fmt_bool(payload.get('docker'))}",
        f"- async_docker: {_fmt_bool(payload.get('async_docker'))}",
        f"- state_engine: {_fmt_bool(state_engine.get('running'))}",
        f"- public_ws_connections: {payload.get('ws_public', '-')}",
        f"- operation_logger_buffer: {payload.get('operation_logger_buffer', '-')}",
        (
            "- botshepherd: "
            f"installed={_fmt_bool(botshepherd.get('installed'))}, "
            f"initialized={_fmt_bool(botshepherd.get('initialized'))}, "
            f"running={_fmt_bool(botshepherd.get('running'))}, "
            f"port={botshepherd.get('port', '-')}, pid={botshepherd.get('pid', '-')}"
        ),
    ]
    if isinstance(metrics, dict) and metrics:
        lines.append(f"- metrics_keys: {', '.join(list(metrics.keys())[:8])}")
    return "\n".join(lines)


def _format_check_botshepherd(
    status: dict[str, Any],
    activation: dict[str, Any],
    heartbeat: dict[str, Any],
) -> str:
    activation_payload = activation.get("activation") if isinstance(activation, dict) else {}
    if not isinstance(activation_payload, dict):
        activation_payload = {}
    bots = heartbeat.get("bots") if isinstance(heartbeat, dict) else {}
    bot_count = len(bots) if isinstance(bots, dict) else 0
    lines = [
        "BotShepherd 状态：",
        f"- installed: {_fmt_bool(status.get('installed'))}",
        f"- initialized: {_fmt_bool(status.get('initialized'))}",
        f"- running: {_fmt_bool(status.get('running'))}",
        f"- auto_start: {_fmt_bool(status.get('auto_start'))}",
        f"- port: {status.get('port', '-')}",
        f"- pid: {status.get('pid', '-')}",
        f"- webui_url: {status.get('webui_url') or status.get('webui_port') or '-'}",
        (
            "- activation: "
            f"running={_fmt_bool(activation_payload.get('running'))}, "
            f"connected={_fmt_bool(activation_payload.get('connected'))}, "
            f"active={activation_payload.get('active_connections', '-')}/"
            f"{activation_payload.get('total_connections', '-')}, "
            f"missing={len(activation_payload.get('missing_endpoints') or [])}"
        ),
        f"- heartbeat_bots: {bot_count}",
    ]
    return "\n".join(lines)


def _format_bot_runtime(bots: list[dict[str, Any]]) -> str:
    if not bots:
        return "当前没有已知 Bot 连接记录。"
    online = [item for item in bots if item.get("connected")]
    lines = [f"Bot 运行态概览：{len(online)}/{len(bots)} online"]
    for item in bots[:20]:
        name = str(item.get("name") or "-")
        uin = str(item.get("uin") or "-")
        nickname = str(item.get("nickname") or "")
        label = f"{nickname}({uin})" if nickname and uin != "-" else uin
        lines.append(
            f"- {name}: connected={_fmt_bool(item.get('connected'))}, "
            f"account={label}, last_seen={_fmt_ts(item.get('last_seen'))}"
        )
    if len(bots) > 20:
        lines.append(f"... 还有 {len(bots) - 20} 个 Bot 未显示")
    return "\n".join(lines)


def _message_text(message: dict[str, Any]) -> str:
    raw = str(message.get("raw_message") or message.get("message") or "")
    raw = " ".join(raw.split())
    return raw[:120] + ("..." if len(raw) > 120 else "")


def _format_recent_messages(payload: dict[str, Any]) -> str:
    messages = payload.get("messages") if isinstance(payload, dict) else []
    if not isinstance(messages, list) or not messages:
        return f"{payload.get('name', '-')}: 当前没有最近消息缓存。"
    name = str(payload.get("name") or "-")
    lines = [f"{name} 最近消息（{len(messages)} 条）："]
    for item in messages[:20]:
        if not isinstance(item, dict):
            continue
        msg_type = str(item.get("message_type") or "-")
        source = item.get("group_id") if msg_type == "group" else item.get("user_id")
        sender = item.get("sender") if isinstance(item.get("sender"), dict) else {}
        sender_name = sender.get("card") or sender.get("nickname") or item.get("user_id") or "-"
        lines.append(
            f"- [{_fmt_ts(item.get('time'))}] {msg_type} {source} {sender_name}: {_message_text(item)}"
        )
    return "\n".join(lines)


def _format_audit_operations(payload: dict[str, Any]) -> str:
    items = (
        payload.get("items")
        or payload.get("logs")
        or payload.get("records")
        or payload.get("data")
        or []
    )
    if not isinstance(items, list) or not items:
        return "最近没有操作审计记录。"
    total = payload.get("total", len(items))
    lines = [f"操作审计摘要：显示 {len(items)} / total={total}"]
    for item in items[:20]:
        if not isinstance(item, dict):
            continue
        op_type = item.get("type") or item.get("operation_type") or item.get("event") or "-"
        operator = item.get("operator_name") or item.get("operator") or item.get("user") or "-"
        level = item.get("level") or "-"
        ts = item.get("created_at") or item.get("time") or item.get("timestamp")
        target = (
            item.get("container_name")
            or item.get("name")
            or item.get("target")
            or item.get("details")
            or ""
        )
        lines.append(f"- [{_fmt_ts(ts)}] {level} {op_type} by {operator} {target}")
    return "\n".join(lines)


async def _resolve_backend_alias(
    plugin: Any,
    alias: str,
) -> tuple[str, str]:
    endpoints = await do_get_radar_endpoints(plugin.client)
    wanted = alias.strip().lower()
    if not wanted:
        return "", "请提供要接入的后端端点别名。当前可用：" + _format_backend_aliases(endpoints)

    exact = [
        item for item in endpoints
        if str(item.get("alias") or "").strip().lower() == wanted
    ]
    matches = exact or [
        item for item in endpoints
        if wanted in str(item.get("alias") or "").strip().lower()
    ]

    if not matches:
        return "", f"未找到包含 '{alias}' 的后端端点。当前可用：" + _format_backend_aliases(endpoints)
    if len(matches) > 1:
        names = ", ".join(str(item.get("alias") or "-") for item in matches[:10])
        return "", f"后端端点别名不唯一，请说得更精确。匹配到：{names}"
    return str(matches[0].get("alias") or alias), ""


def _resolve_bind_qq(plugin: Any, event: AstrMessageEvent, request: WorkflowRequest) -> str:
    explicit = ""
    for key in ("bind_qq", "qq_id", "user_id", "owner_qq", "bind_to_user"):
        value = request.params.get(key)
        if isinstance(value, bool):
            continue
        if value is not None and str(value).strip():
            explicit = str(value).strip()
            break
    if explicit:
        return explicit
    try:
        at_user = plugin.get_first_at_user_id(event)
    except Exception:
        at_user = None
    if at_user:
        return str(at_user)
    if _get_bool(request.params, "bind_to_sender", default=not event.is_admin()):
        return str(event.get_sender_id())
    return ""


async def _assign_instance_to_user(
    plugin: Any,
    qq_id: str,
    instance_name: str,
    nickname: str = "",
) -> str:
    if not qq_id:
        return ""
    mapping = await plugin.get_user_mapping()
    if qq_id not in mapping:
        mapping[qq_id] = {"nickname": "", "instances": []}
    instances = mapping[qq_id].setdefault("instances", [])
    added = instance_name not in instances
    if added:
        instances.append(instance_name)
    if nickname:
        mapping[qq_id]["nickname"] = nickname
    await plugin.save_user_mapping(mapping)
    state = "已新增绑定" if added else "绑定已存在"
    nick_part = f"，昵称：{nickname}" if nickname else ""
    return f"{state}：QQ {qq_id} -> {instance_name}{nick_part}。"


async def _run_backend_connect(
    plugin: Any,
    event: AstrMessageEvent,
    instance_name: str,
    backend_alias: str,
) -> AsyncIterator[Any]:
    resolved_alias, error = await _resolve_backend_alias(plugin, backend_alias)
    if error:
        yield event.plain_result(error)
        return
    async for item in plugin.ncqq_backend(
        event,
        action="inject",
        alias=resolved_alias,
        instance_names=instance_name,
    ):
        yield item


async def _run_create_instance(
    plugin: Any,
    event: AstrMessageEvent,
    request: WorkflowRequest,
) -> AsyncIterator[Any]:
    ok, instance_name = await _resolve_target(plugin, event, request, allow_single_bound=False)
    if not ok:
        yield event.plain_result(instance_name)
        return
    if not instance_name:
        yield event.plain_result("实例创建流程需要明确新实例名。")
        return

    backend_alias = _first_text(request.params, "backend_alias", "alias", "endpoint")
    need_qrcode = _get_bool(request.params, "qrcode", "need_qrcode", default=True)
    auto_start = _get_bool(request.params, "auto_start", "start", default=True)
    bind_qq = _resolve_bind_qq(plugin, event, request)
    nickname = _first_text(request.params, "nickname", "owner_name")

    resolved_backend_alias = ""
    if backend_alias:
        resolved_backend_alias, error = await _resolve_backend_alias(plugin, backend_alias)
        if error:
            yield event.plain_result(error)
            return

    list_ok, containers, list_error = await _list_containers(plugin)
    if not list_ok:
        yield event.plain_result(f"实例创建流程停止：无法读取容器列表。{list_error}")
        return

    current = _find_container(containers, instance_name)
    if current is not None:
        allowed, message = await _ensure_instance_access(plugin, event, instance_name)
        if not allowed:
            yield event.plain_result(
                f"实例 {instance_name} 已存在，但当前账号没有操作权限。{message}"
            )
            return
        yield event.plain_result(
            "实例创建流程：实例已存在，跳过创建。\n"
            + _format_container_brief(current)
        )
    else:
        if not event.is_admin():
            params = {
                "instance_name": instance_name,
                "backend_alias": resolved_backend_alias,
                "bind_qq": bind_qq or str(event.get_sender_id()),
                "nickname": nickname,
            }
            aid = await create_approval(
                plugin,
                action="create_instance",
                params=params,
                requester_qq=str(event.get_sender_id()),
                group_id=str(event.get_group_id() or ""),
                description=(
                    f"创建实例 {instance_name}"
                    + (f"，绑定 QQ {params['bind_qq']}" if params.get("bind_qq") else "")
                    + (f"，接入后端 {resolved_backend_alias}" if resolved_backend_alias else "")
                ),
            )
            notice = plugin._approval_notice_single("创建 ncqq 实例", aid)
            yield event.plain_result(
                notice
                + "\n审批通过后会执行：创建实例、绑定用户、接入后端（如有）。"
                + "\n登录二维码需要实例启动后再次执行登录恢复流程。"
            )
            return

        yield event.plain_result("实例创建流程：未发现同名实例，开始创建。")
        async for item in plugin.ncqq_action(
            event,
            action="create",
            instance_names=instance_name,
        ):
            yield item

        confirmed, confirm_message = await do_confirm_instance_action(
            plugin.client,
            instance_name,
            ["create", "start"],
            timeout=20,
        )
        yield event.plain_result(confirm_message)

        list_ok, containers, list_error = await _list_containers(plugin)
        current = _find_container(containers, instance_name) if list_ok else None
        if current is None:
            detail = "" if confirmed else "状态确认尚未完成。"
            yield event.plain_result(
                f"实例 {instance_name} 的创建请求已提交，但当前列表中尚未可见。"
                f"{detail}后端接入和二维码请稍后通过 connect/recover 流程继续。"
            )
            return

    if bind_qq and event.is_admin():
        bind_message = await _assign_instance_to_user(plugin, bind_qq, instance_name, nickname)
        if bind_message:
            yield event.plain_result(bind_message)

    if auto_start and current is not None and not _is_running(current):
        yield event.plain_result("实例创建流程：实例存在但未运行，进入启动分支。")
        async for item in plugin.ncqq_action(
            event,
            action="start",
            instance_names=instance_name,
        ):
            yield item

    if resolved_backend_alias:
        yield event.plain_result(
            f"实例创建流程：进入后端接入分支，端点 {resolved_backend_alias}。"
        )
        async for item in _run_backend_connect(
            plugin,
            event,
            instance_name,
            resolved_backend_alias,
        ):
            yield item

    payload = await do_check_login_status(plugin.client, instance_name)
    yield event.plain_result(_format_login_status(instance_name, payload))
    if need_qrcode and payload.get("status") != "error" and not payload.get("logged_in"):
        async for item in plugin.ncqq_qrcode(event, instance_name=instance_name):
            yield item


async def _run_relogin_instance(
    plugin: Any,
    event: AstrMessageEvent,
    request: WorkflowRequest,
) -> AsyncIterator[Any]:
    ok, instance_name = await _resolve_target(plugin, event, request)
    if not ok:
        yield event.plain_result(instance_name)
        return
    if not instance_name:
        yield event.plain_result("登录恢复流程需要明确目标实例。")
        return
    allowed, message = await _ensure_instance_access(plugin, event, instance_name)
    if not allowed:
        yield event.plain_result(message)
        return

    if _get_bool(request.params, "restart_first", default=False):
        yield event.plain_result("登录恢复流程：按参数要求先重启实例。")
        async for item in plugin.ncqq_action(
            event,
            action="restart",
            instance_names=instance_name,
        ):
            yield item

    payload = await do_check_login_status(plugin.client, instance_name)
    yield event.plain_result(_format_login_status(instance_name, payload))
    if payload.get("status") == "error":
        return

    force_qrcode = _get_bool(request.params, "force_qrcode", default=False)
    need_qrcode = _get_bool(request.params, "qrcode", "need_qrcode", default=True)
    if payload.get("logged_in") and not force_qrcode:
        return
    if not need_qrcode and not force_qrcode:
        yield event.plain_result("当前未自动拉取二维码，因为 qrcode=false。")
        return
    async for item in plugin.ncqq_qrcode(event, instance_name=instance_name):
        yield item


async def _run_control_instance(
    plugin: Any,
    event: AstrMessageEvent,
    request: WorkflowRequest,
) -> AsyncIterator[Any]:
    action = _normalize_action(_first_text(request.params, "action", "operation"))
    if action not in _LIFECYCLE_ACTIONS:
        yield event.plain_result("实例操作流程需要 action=start/stop/restart/pause/unpause/kill。")
        return

    ok, instance_name = await _resolve_target(plugin, event, request)
    if not ok:
        yield event.plain_result(instance_name)
        return
    if not instance_name:
        yield event.plain_result("实例操作流程需要明确目标实例。")
        return

    async for item in plugin.ncqq_action(
        event,
        action=action,
        instance_names=instance_name,
    ):
        yield item

    check_after = _get_bool(
        request.params,
        "check_after",
        "check_login",
        default=action in {"start", "restart", "unpause"},
    )
    if check_after:
        payload = await do_check_login_status(plugin.client, instance_name)
        yield event.plain_result(_format_login_status(instance_name, payload))


async def _run_connect_backend(
    plugin: Any,
    event: AstrMessageEvent,
    request: WorkflowRequest,
) -> AsyncIterator[Any]:
    backend_alias = _first_text(request.params, "backend_alias", "alias", "endpoint")
    if not backend_alias:
        endpoints = await do_get_radar_endpoints(plugin.client)
        yield event.plain_result(
            "后端接入流程需要 backend_alias。当前可用：" + _format_backend_aliases(endpoints)
        )
        return

    ok, instance_name = await _resolve_target(plugin, event, request)
    if not ok:
        yield event.plain_result(instance_name)
        return
    if not instance_name:
        yield event.plain_result("后端接入流程需要明确目标实例。")
        return

    resolved_alias, error = await _resolve_backend_alias(plugin, backend_alias)
    if error:
        yield event.plain_result(error)
        return
    async for item in _run_backend_connect(plugin, event, instance_name, resolved_alias):
        yield item


async def _run_check_instance(
    plugin: Any,
    event: AstrMessageEvent,
    request: WorkflowRequest,
) -> AsyncIterator[Any]:
    ok, instance_name = await _resolve_target(plugin, event, request)
    if not ok:
        yield event.plain_result(instance_name)
        return
    if not instance_name:
        yield event.plain_result("实例诊断流程需要明确目标实例。")
        return

    list_ok, containers, list_error = await _list_containers(plugin)
    if not list_ok:
        yield event.plain_result(f"实例诊断流程停止：无法读取容器列表。{list_error}")
        return
    current = _find_container(containers, instance_name)
    if current is None:
        yield event.plain_result(f"实例 {instance_name} 不存在，停止诊断。")
        return

    yield event.plain_result("实例诊断流程：\n" + _format_container_brief(current))
    payload = await do_check_login_status(plugin.client, instance_name)
    yield event.plain_result(_format_login_status(instance_name, payload))
    async for item in plugin.ncqq_query(event, query="monitor", instance_names=instance_name):
        yield item
    async for item in plugin.ncqq_query(event, query="logs", instance_names=instance_name):
        yield item

    file_name = _first_text(request.params, "file_name", "config_file")
    path = _first_text(request.params, "path")
    if path:
        async for item in plugin.ncqq_query(
            event,
            query="files",
            instance_names=instance_name,
            path=path,
        ):
            yield item
    if file_name:
        async for item in plugin.ncqq_query(
            event,
            query="config",
            instance_names=instance_name,
            file_name=file_name,
        ):
            yield item


async def _run_check_manager(
    plugin: Any,
    event: AstrMessageEvent,
) -> AsyncIterator[Any]:
    ok, payload = await _manager_get(plugin, "/api/health")
    if not ok or not isinstance(payload, dict):
        yield event.plain_result(f"管理器健康检查失败：{payload}")
        return
    yield event.plain_result(_format_check_manager(payload))


async def _run_check_botshepherd(
    plugin: Any,
    event: AstrMessageEvent,
) -> AsyncIterator[Any]:
    ok_status, status = await _manager_get(plugin, "/api/botshepherd/status")
    ok_activation, activation = await _manager_get(plugin, "/api/botshepherd/activation")
    ok_heartbeat, heartbeat = await _manager_get(plugin, "/api/botshepherd/bots/heartbeat")
    if not ok_status or not isinstance(status, dict):
        yield event.plain_result(f"BotShepherd 状态读取失败：{status}")
        return
    yield event.plain_result(
        _format_check_botshepherd(
            status,
            activation if ok_activation and isinstance(activation, dict) else {},
            heartbeat if ok_heartbeat and isinstance(heartbeat, dict) else {},
        )
    )


async def _run_check_bot_runtime(
    plugin: Any,
    event: AstrMessageEvent,
) -> AsyncIterator[Any]:
    ok, payload = await _manager_get(plugin, "/api/bots")
    if not ok or not isinstance(payload, list):
        yield event.plain_result(f"Bot 运行态读取失败：{payload}")
        return
    yield event.plain_result(_format_bot_runtime(payload))


async def _run_read_bot_messages(
    plugin: Any,
    event: AstrMessageEvent,
    request: WorkflowRequest,
) -> AsyncIterator[Any]:
    target = _first_text(request.params, "bot", "bot_name") or request.target
    if not target:
        yield event.plain_result("read_bot_messages 需要目标 Bot/实例名。")
        return
    limit = _as_int(request.params.get("limit"), default=20, maximum=50)
    ok, payload = await _manager_get(plugin, f"/api/bots/{target}/messages?limit={limit}")
    if not ok or not isinstance(payload, dict):
        yield event.plain_result(f"最近消息读取失败：{payload}")
        return
    yield event.plain_result(_format_recent_messages(payload))


async def _run_audit_operations(
    plugin: Any,
    event: AstrMessageEvent,
    request: WorkflowRequest,
) -> AsyncIterator[Any]:
    limit = _as_int(request.params.get("limit"), default=10, maximum=50)
    ok, payload = await _manager_get(plugin, f"/api/operation_logs?limit={limit}")
    if not ok or not isinstance(payload, dict):
        yield event.plain_result(f"操作审计读取失败：{payload}")
        return
    yield event.plain_result(_format_audit_operations(payload))


async def _run_inspect_resources(
    plugin: Any,
    event: AstrMessageEvent,
) -> AsyncIterator[Any]:
    async for item in plugin.ncqq_query(event, query="assets"):
        yield item


async def _run_read_instance_config(
    plugin: Any,
    event: AstrMessageEvent,
    request: WorkflowRequest,
) -> AsyncIterator[Any]:
    ok, instance_name = await _resolve_target(plugin, event, request)
    if not ok:
        yield event.plain_result(instance_name)
        return
    if not instance_name:
        yield event.plain_result("read_instance_config 需要目标实例。")
        return
    path = _first_text(request.params, "path")
    file_name = _first_text(request.params, "file_name", "config_file")
    async for item in plugin.ncqq_query(
        event,
        query="files",
        instance_names=instance_name,
        path=path,
    ):
        yield item
    if file_name:
        async for item in plugin.ncqq_query(
            event,
            query="config",
            instance_names=instance_name,
            file_name=file_name,
        ):
            yield item


async def _run_delete_instance(
    plugin: Any,
    event: AstrMessageEvent,
    request: WorkflowRequest,
) -> AsyncIterator[Any]:
    ok, instance_name = await _resolve_target(plugin, event, request)
    if not ok:
        yield event.plain_result(instance_name)
        return
    if not instance_name:
        yield event.plain_result("实例销毁流程需要明确目标实例。")
        return
    if not _get_bool(request.params, "confirm", "confirmed", default=False):
        yield event.plain_result(
            "实例销毁流程需要显式确认：params.confirm=true。"
            "如需同时删除数据目录，设置 params.delete_data=true。"
        )
        return
    delete_data = _get_bool(request.params, "delete_data", "clean_data", default=False)
    async for item in plugin.ncqq_action(
        event,
        action="delete",
        instance_names=instance_name,
        delete_data=delete_data,
    ):
        yield item


async def run_ncqq_workflow(
    plugin: Any,
    event: AstrMessageEvent,
    request: WorkflowRequest,
) -> AsyncIterator[Any]:
    request.workflow = _normalize_workflow(request.workflow)
    spec = COMPILED_WORKFLOWS.get(request.workflow)
    if spec is None:
        yield event.plain_result("未知 ncqq workflow。\n" + _format_workflow_list())
        return

    if spec.admin_only and not event.is_admin():
        yield event.plain_result(f"{spec.title} 仅限 AstrBot 管理员使用。")
        return

    if request.workflow == "create_instance":
        async for item in _run_create_instance(plugin, event, request):
            yield item
        return

    if request.workflow == "relogin_instance":
        async for item in _run_relogin_instance(plugin, event, request):
            yield item
        return

    if request.workflow == "control_instance":
        async for item in _run_control_instance(plugin, event, request):
            yield item
        return

    if request.workflow == "connect_backend":
        async for item in _run_connect_backend(plugin, event, request):
            yield item
        return

    if request.workflow == "check_instance":
        async for item in _run_check_instance(plugin, event, request):
            yield item
        return

    if request.workflow == "list_instances":
        async for item in plugin.ncqq_query(event, query="instances"):
            yield item
        return

    if request.workflow == "check_backends":
        endpoints = await do_get_radar_endpoints(plugin.client)
        yield event.plain_result(_format_backend_list(endpoints))
        return

    if request.workflow == "check_manager":
        async for item in _run_check_manager(plugin, event):
            yield item
        return

    if request.workflow == "check_botshepherd":
        async for item in _run_check_botshepherd(plugin, event):
            yield item
        return

    if request.workflow == "check_bot_runtime":
        async for item in _run_check_bot_runtime(plugin, event):
            yield item
        return

    if request.workflow == "read_bot_messages":
        async for item in _run_read_bot_messages(plugin, event, request):
            yield item
        return

    if request.workflow == "audit_operations":
        async for item in _run_audit_operations(plugin, event, request):
            yield item
        return

    if request.workflow == "inspect_resources":
        async for item in _run_inspect_resources(plugin, event):
            yield item
        return

    if request.workflow == "read_instance_config":
        async for item in _run_read_instance_config(plugin, event, request):
            yield item
        return

    if request.workflow == "delete_instance":
        async for item in _run_delete_instance(plugin, event, request):
            yield item
        return

    if request.workflow == "review_approvals":
        async for item in plugin.ncqq_approval(event, action="list"):
            yield item
        return

    yield event.plain_result("workflow 已注册但尚未实现，请检查插件版本。")
