"""HTML → Image renderer for ncqq instance list.

Priority chain:
  1. playwright (headless chromium) → PNG bytes → Image.fromBase64
  2. plain-text fallback (always available)
"""
from __future__ import annotations

import base64
import datetime
import logging
import os
import pathlib
import tempfile
from typing import Union

logger = logging.getLogger(__name__)

_TEMPLATE_PATH = pathlib.Path(__file__).parent.parent / "templates" / "instances.html"

# ------------------------------------------------------------------ #
#  Data helpers                                                        #
# ------------------------------------------------------------------ #

def _ts_to_str(ts: float) -> str:
    if not ts:
        return "—"
    try:
        return datetime.datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
    except Exception:
        return str(ts)


def _login_label(c: dict) -> str:
    stage = c.get("login_stage", "")
    method = c.get("login_method", "")
    stage_map = {
        "logged_in": "已登录",
        "qr_waiting": "待扫码",
        "offline": "离线",
        "initializing": "初始化",
    }
    label = stage_map.get(stage, stage or "未知")
    method_map = {"sdk_ws": "SDK-WS", "filesystem": "文件系统"}
    method_label = method_map.get(method, method or "")
    return f"{label} / {method_label}" if method_label else label


# ------------------------------------------------------------------ #
#  HTML card builder                                                   #
# ------------------------------------------------------------------ #

def _build_card(c: dict, rank: int) -> str:
    online: bool = bool(c.get("bot_online", False))
    status: str = str(c.get("status", "unknown")).lower()

    # 状态判定
    if not online:
        state = "offline"
        badge_text = "OFFLINE"
    elif status == "paused":
        state = "paused"
        badge_text = "PAUSED"
    else:
        state = "online"
        badge_text = "ONLINE"

    name        = c.get("name", "—")
    uin         = c.get("uin", "")
    heartbeat   = _ts_to_str(c.get("bot_heartbeat_ts", 0))
    login_info  = _login_label(c)
    # 管理器直接提供的头像（base64 data-URI 或 https URL 均可）
    bot_avatar  = c.get("bot_avatar", "")

    avatars = ["🤖", "🐾", "🌸", "⚡", "🎮", "🔥", "🌙", "⭐"]
    fallback_emoji = avatars[(rank - 1) % len(avatars)]
    uin_display = uin or "—"

    if bot_avatar:
        # 有头像：img 铺满，onerror 降级到 emoji
        bg_inner = (
            f'<img src="{bot_avatar}" alt="avatar" '
            f'onerror="this.style.display=\'none\';'
            f'this.parentNode.querySelector(\'.card-bg-emoji\').style.display=\'flex\'">'
            f'<span class="card-bg-emoji" style="display:none">{fallback_emoji}</span>'
        )
        no_avatar_hint = ""
    else:
        # 无头像：emoji 占位 + 提示用户检查管理器
        bg_inner = f'<span class="card-bg-emoji">{fallback_emoji}</span>'
        no_avatar_hint = (
            '<div class="no-avatar-hint">'
            '⚠️ 管理器未返回头像数据，请检查 ncqq 管理器版本或配置。'
            '</div>'
        )

    return (
        f'<div class="card">'
        f'<div class="card-bg">{bg_inner}</div>'
        f'<div class="card-hero">'
        f'<span class="live-badge {state}">{badge_text}</span>'
        f'</div>'
        f'<div class="card-body">'
        f'<div class="inst-name">{name}</div>'
        f'<div class="inst-uin">QQ: <span>{uin_display}</span></div>'
        + (f'{no_avatar_hint}' if no_avatar_hint else '')
        + f'<hr class="divider">'
        f'<div class="meta-row">'
        f'<div class="meta-item"><span class="emoji">🔑</span>'
        f'<span class="val">{login_info}</span></div>'
        f'<div class="meta-item"><span class="emoji">⏱</span>'
        f'<span class="val hi">{heartbeat}</span></div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )


def _render_html(containers: list[dict]) -> str:
    """Fill template placeholders and return final HTML string."""
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    total = len(containers)
    online = sum(1 for c in containers if c.get("bot_online"))
    offline = total - online
    cards_html = "".join(_build_card(c, i + 1) for i, c in enumerate(containers))
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (
        template
        .replace("__GENERATED_AT__", now_str)
        .replace("__TOTAL__", str(total))
        .replace("__ONLINE__", str(online))
        .replace("__OFFLINE__", str(offline))
        .replace("__CARDS__", cards_html)
    )


# ------------------------------------------------------------------ #
#  Playwright screenshot (optional)                                    #
# ------------------------------------------------------------------ #

async def _screenshot_html(html: str) -> bytes | None:
    """Render HTML to PNG bytes via playwright. Returns None if unavailable."""
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except ImportError:
        return None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".html", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(html)
            tmp_path = f.name

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(args=["--no-sandbox"])
            page = await browser.new_page(viewport={"width": 560, "height": 800})
            await page.goto(f"file://{tmp_path}")
            await page.wait_for_load_state("networkidle")
            content_box = await page.query_selector("body")
            png = await content_box.screenshot() if content_box else await page.screenshot()
            await browser.close()

        os.unlink(tmp_path)
        return png
    except Exception as e:
        logger.warning("playwright screenshot failed: %s", e)
        return None


# ------------------------------------------------------------------ #
#  Plain-text fallback                                                 #
# ------------------------------------------------------------------ #

def _plain_text(containers: list[dict]) -> str:
    """Always-available plain-text rendering."""
    total = len(containers)
    online = sum(1 for c in containers if c.get("bot_online"))
    lines = [
        f"📋 NapCat 实例列表  共{total}个 | 在线{online} / 离线{total - online}",
        "─" * 36,
    ]
    for c in containers:
        is_online = c.get("bot_online", False)
        status_icon = "🟢" if is_online else "🔴"
        uin = c.get("uin", "—")
        name = c.get("name", "—")
        heartbeat = _ts_to_str(c.get("bot_heartbeat_ts", 0))
        login_info = _login_label(c)
        lines.append(
            f"{status_icon} [{name}]  QQ: {uin}\n"
            f"   状态: {login_info}  | 心跳: {heartbeat}"
        )
    lines.append("─" * 36)
    return "\n".join(lines)


# ------------------------------------------------------------------ #
#  Public entry                                                        #
# ------------------------------------------------------------------ #

async def render_instances(containers: list[dict]) -> Union[str, bytes]:
    """Return PNG bytes (playwright) or plain-text str (fallback)."""
    if not containers:
        return "当前没有任何实例。"
    html = _render_html(containers)
    png = await _screenshot_html(html)
    if png:
        return png
    return _plain_text(containers)

