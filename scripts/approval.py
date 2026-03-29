"""Approval workflow for high-privilege ncqq operations.

Pending approvals are stored in the plugin KV under the key
``pending_approvals`` as a dict keyed by a short approval_id.
Each record:
{
    "approval_id": str,
    "action": str,          # tool/action name, e.g. "inject_backend"
    "params": dict,         # kwargs to re-run the action
    "requester_qq": str,
    "group_id": str,
    "description": str,     # human-readable summary for @Owner message
    "created_at": float,    # unix timestamp
}
"""

from __future__ import annotations

import random
import string
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import NCQQManagerPlugin

# Actions that require Owner approval when triggered by a non-owner.
APPROVAL_REQUIRED_ACTIONS: set[str] = {
    "delete",  # ncqq_instance_action with action=delete
    "create",  # create_ncqq_instance
    "write_config",  # write_ncqq_config
    "inject_backend",  # inject_backend_to_instance
    "bind_instance",  # bind_ncqq_instance
    "manage_backends",  # manage_ncqq_backends
}

# Seconds before a pending approval expires.
APPROVAL_TTL = 3600  # 1 hour


def _gen_approval_id() -> str:
    """Return a 6-character uppercase alphanumeric approval ID."""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=6))


async def create_approval(
    plugin: "NCQQManagerPlugin",
    action: str,
    params: dict,
    requester_qq: str,
    group_id: str,
    description: str,
) -> str:
    """Persist a pending approval and return the approval_id."""
    approvals = await plugin.get_pending_approvals()

    # Purge expired entries first.
    now = time.time()
    approvals = {
        k: v
        for k, v in approvals.items()
        if now - v.get("created_at", 0) < APPROVAL_TTL
    }

    # Collision-free ID generation.
    approval_id = _gen_approval_id()
    while approval_id in approvals:
        approval_id = _gen_approval_id()

    approvals[approval_id] = {
        "approval_id": approval_id,
        "action": action,
        "params": params,
        "requester_qq": requester_qq,
        "group_id": group_id,
        "description": description,
        "created_at": now,
    }
    await plugin.save_pending_approvals(approvals)
    return approval_id


async def get_approval(plugin: "NCQQManagerPlugin", approval_id: str) -> dict | None:
    """Return the approval record or None if not found / expired."""
    approvals = await plugin.get_pending_approvals()
    record = approvals.get(approval_id)
    if record is None:
        return None
    if time.time() - record.get("created_at", 0) > APPROVAL_TTL:
        return None
    return record


async def remove_approval(plugin: "NCQQManagerPlugin", approval_id: str) -> None:
    """Delete a pending approval record."""
    approvals = await plugin.get_pending_approvals()
    approvals.pop(approval_id, None)
    await plugin.save_pending_approvals(approvals)


async def list_approvals(plugin: "NCQQManagerPlugin") -> list[dict]:
    """Return all non-expired pending approvals sorted by creation time."""
    approvals = await plugin.get_pending_approvals()
    now = time.time()
    valid = [
        v for v in approvals.values() if now - v.get("created_at", 0) < APPROVAL_TTL
    ]
    return sorted(valid, key=lambda x: x.get("created_at", 0))
