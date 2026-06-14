"""Periodic health check and offline notification for ncqq instances."""
from __future__ import annotations

import base64
import datetime
import html
import pathlib
from typing import TYPE_CHECKING

from astrbot.api import logger
from astrbot.api.all import Image
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.star.star_tools import StarTools

from .monitoring import do_list_instances

if TYPE_CHECKING:
    from ..main import NCQQManagerPlugin

# Alert HTML template
_ALERT_TEMPLATE_PATH = pathlib.Path(__file__).parent.parent / "templates" / "alert.html"
_alert_template_cache: str | None = None
_alert_template_mtime: float = 0.0

_BODY_WIDTH = 420


def _get_alert_template() -> str:
    global _alert_template_cache, _alert_template_mtime
    try:
        mtime = _ALERT_TEMPLATE_PATH.stat().st_mtime
    except OSError:
        if _alert_template_cache:
            return _alert_template_cache
        raise
    if _alert_template_cache and mtime == _alert_template_mtime:
        return _alert_template_cache
    _alert_template_cache = _ALERT_TEMPLATE_PATH.read_text(encoding="utf-8")
    _alert_template_mtime = mtime
    return _alert_template_cache


def _build_alert_item(name: str, dot_class: str, detail: str, owner: str = "") -> str:
    safe_name = html.escape(str(name or ""))
    safe_detail = html.escape(str(detail or ""))
    safe_owner = html.escape(str(owner or ""))
    owner_html = f'<span class="owner-tag">{safe_owner}</span>' if owner else ""
    return (
        f'<div class="alert-item">'
        f'<span class="dot {dot_class}"></span>'
        f'<div class="inst-info">'
        f'<div class="inst-name">{safe_name}</div>'
        f'<div class="inst-detail">{safe_detail}</div>'
        f'</div>'
        f'{owner_html}'
        f'</div>'
    )


async def render_alert_card(
    title: str,
    icon: str,
    items_html: str,
    summary: str,
    accent_color: str = "#e74c3c",
) -> bytes | str:
    """Render an alert card to PNG bytes. Falls back to plain text summary."""
    try:
        template = _get_alert_template()
    except Exception:
        return summary

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = (
        template
        .replace("__BODY_WIDTH__", str(_BODY_WIDTH))
        .replace("__ACCENT_COLOR__", accent_color)
        .replace("__ALERT_ICON__", icon)
        .replace("__ALERT_TITLE__", title)
        .replace("__ALERT_TIME__", now_str)
        .replace("__ALERT_ITEMS__", items_html)
        .replace("__ALERT_SUMMARY__", summary)
    )

    try:
        from ..rendering.html_renderer import _screenshot_html
        return await _screenshot_html(html, _BODY_WIDTH)
    except Exception as e:
        logger.warning("Alert card render failed: %s", e)
        return summary


def _find_owners(
    plugin: "NCQQManagerPlugin",
    mapping: dict,
    manager_id: str,
    instance_name: str,
) -> list[tuple[str, str]]:
    """Return [(qq_id, nickname), ...] for owners of an instance ref."""
    owners = []
    instance_ref = plugin.format_instance_ref(manager_id, instance_name)
    for qq_id, data in mapping.items():
        instances = data.get("instances", [])
        legacy_match = (
            manager_id == plugin.default_manager_id()
            and instance_name in instances
        )
        if instance_ref in instances or legacy_match:
            owners.append((qq_id, data.get("nickname", "")))
    return owners


async def do_health_check(plugin: "NCQQManagerPlugin") -> None:
    """Core health check logic. Called by cron job."""
    if not plugin.config.get("enable_offline_notify", True):
        return

    notify_group = str(plugin.config.get("notify_group", "")).strip()

    current: dict[str, bool] = {}
    instance_meta: dict[str, tuple[str, str]] = {}
    any_success = False
    for manager_id in plugin.manager_ids():
        try:
            result = await do_list_instances(
                plugin.client_for_manager(manager_id), [], True
            )
            if isinstance(result, str):
                logger.debug(
                    "Health check %s: no instances or error: %s", manager_id, result
                )
                continue
            any_success = True
            for c in result:
                name = c.get("name", "")
                if not name:
                    continue
                ref = plugin.format_instance_ref(manager_id, name)
                current[ref] = bool(c.get("bot_online", False))
                instance_meta[ref] = (manager_id, name)
        except Exception as e:
            logger.warning("Health check failed to list instances on %s: %s", manager_id, e)

    if not any_success:
        return

    # Load previous snapshot
    prev: dict[str, bool] = await plugin.get_kv_data("health_snapshot", {})

    # Diff: find newly offline and newly recovered
    newly_offline: list[str] = []
    newly_online: list[str] = []

    for name, online in current.items():
        was_online = prev.get(name)
        if was_online is True and not online:
            newly_offline.append(name)
        elif was_online is False and online:
            newly_online.append(name)
        # was_online is None → first seen, skip notification

    # Save current snapshot
    await plugin.put_kv_data("health_snapshot", current)

    if not newly_offline and not newly_online:
        return

    mapping = await plugin.get_user_mapping()

    # --- Notify for newly offline instances ---
    if newly_offline:
        items_html_parts = []
        text_lines = ["🔴 以下实例掉线："]
        notified_owners: set[str] = set()

        for ref in newly_offline:
            manager_id, name = instance_meta.get(ref, plugin.split_instance_ref(ref))
            owners = _find_owners(plugin, mapping, manager_id, name)
            owner_label = ", ".join(
                f"{nick or qq}" for qq, nick in owners
            ) if owners else "未绑定"
            items_html_parts.append(
                _build_alert_item(ref, "offline", "已掉线", owner_label)
            )
            text_lines.append(f"  • {ref}（归属: {owner_label}）")

            # Private notify each owner
            for qq_id, nick in owners:
                if qq_id in notified_owners:
                    continue
                notified_owners.add(qq_id)
                try:
                    mc = MessageChain()
                    mc.message(
                        f"⚠️ 你的实例 {ref} 已掉线，请及时检查。\n"
                        f"可发送「ncqq login {ref}」查看状态或「ncqq qrcode {ref}」重新扫码。"
                    )
                    await StarTools.send_message_by_id(
                        type="PrivateMessage", id=qq_id, message_chain=mc
                    )
                except Exception as e:
                    logger.warning("Failed to notify owner %s for %s: %s", qq_id, name, e)

        # Group notification with image card
        if notify_group:
            summary = f"共 {len(newly_offline)} 个实例变为离线"
            items_html = "\n".join(items_html_parts)
            rendered = await render_alert_card(
                title="实例掉线告警",
                icon="🔴",
                items_html=items_html,
                summary=summary,
                accent_color="#e74c3c",
            )
            try:
                mc = MessageChain()
                if isinstance(rendered, bytes):
                    mc.chain.append(Image.fromBase64(base64.b64encode(rendered).decode()))
                else:
                    mc.message(rendered)
                await StarTools.send_message_by_id(
                    type="GroupMessage", id=notify_group, message_chain=mc
                )
            except Exception as e:
                logger.warning("Failed to send offline alert to group %s: %s", notify_group, e)

    # --- Notify for newly recovered instances ---
    if newly_online:
        items_html_parts = []
        text_lines = ["🟢 以下实例已恢复："]
        notified_owners: set[str] = set()

        for ref in newly_online:
            manager_id, name = instance_meta.get(ref, plugin.split_instance_ref(ref))
            owners = _find_owners(plugin, mapping, manager_id, name)
            owner_label = ", ".join(
                f"{nick or qq}" for qq, nick in owners
            ) if owners else "未绑定"
            items_html_parts.append(
                _build_alert_item(ref, "recover", "已恢复上线", owner_label)
            )
            text_lines.append(f"  • {ref}（归属: {owner_label}）")

            # Private notify each owner
            for qq_id, nick in owners:
                if qq_id in notified_owners:
                    continue
                notified_owners.add(qq_id)
                try:
                    mc = MessageChain()
                    mc.message(f"✅ 你的实例 {ref} 已恢复上线。")
                    await StarTools.send_message_by_id(
                        type="PrivateMessage", id=qq_id, message_chain=mc
                    )
                except Exception as e:
                    logger.warning("Failed to notify owner %s for %s: %s", qq_id, name, e)

        # Group notification with image card
        if notify_group:
            summary = f"共 {len(newly_online)} 个实例恢复上线"
            items_html = "\n".join(items_html_parts)
            rendered = await render_alert_card(
                title="实例恢复通知",
                icon="🟢",
                items_html=items_html,
                summary=summary,
                accent_color="#2ecc71",
            )
            try:
                mc = MessageChain()
                if isinstance(rendered, bytes):
                    mc.chain.append(Image.fromBase64(base64.b64encode(rendered).decode()))
                else:
                    mc.message(rendered)
                await StarTools.send_message_by_id(
                    type="GroupMessage", id=notify_group, message_chain=mc
                )
            except Exception as e:
                logger.warning("Failed to send recover alert to group %s: %s", notify_group, e)
