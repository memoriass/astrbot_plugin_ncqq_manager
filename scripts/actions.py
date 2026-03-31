import logging

from .api import NCQQClient

logger = logging.getLogger(__name__)


def _action_label(action: str) -> str:
    return {
        "start": "启动",
        "stop": "停止",
        "restart": "重启",
        "pause": "暂停",
        "unpause": "恢复运行",
        "kill": "强制结束",
        "delete": "删除",
        "recreate": "重建",
    }.get(action, action)


async def do_create_instance(client: NCQQClient, instance_name: str) -> str:
    try:
        await client.make_request("POST", "/api/containers", json={"name": instance_name})
        return f"实例 {instance_name} 的创建请求已提交，请稍后再查看运行状态。"
    except Exception as e:
        logger.warning("创建实例 %s 失败: %s", instance_name, e)
        return f"实例 {instance_name} 创建失败，请稍后重试或联系管理员。"


async def do_instance_action(
    client: NCQQClient,
    instance_name: str,
    action: str,
    delete_data: bool = False,
) -> str:
    try:
        url = f"/api/containers/{instance_name}/action?action={action}"
        if action == "delete" and delete_data:
            url += "&delete_data=true"
        await client.make_request("POST", url)
        suffix = "（含本地数据）" if action == "delete" and delete_data else ""
        return f"实例 {instance_name} 的{_action_label(action)}请求已提交{suffix}。"
    except Exception as e:
        logger.warning("实例 %s 执行 %s 失败: %s", instance_name, action, e)
        return f"实例 {instance_name} 的{_action_label(action)}失败，请稍后重试或联系管理员。"


async def do_clear_instance_data(
    client: NCQQClient,
    instance_name: str,
    scope: str = "all",
    node_id: str = "local",
) -> str:
    """调用管理器 DELETE /api/containers/{name}/data 清理实例数据目录。

    scope: all | config | cache | logs
    """
    try:
        url = f"/api/containers/{instance_name}/data?scope={scope}&node_id={node_id}"
        res = await client.make_request("DELETE", url)
        cleared = res.get("cleared", []) if isinstance(res, dict) else []
        restarted = res.get("restarted", False) if isinstance(res, dict) else False
        parts = [f"实例 {instance_name} 数据清理完成。"]
        if cleared:
            parts.append(f"已清除：{'、'.join(cleared)}")
        if restarted:
            parts.append("容器已自动重启。")
        return " ".join(parts)
    except Exception as e:
        logger.warning("清理实例 %s 数据失败: %s", instance_name, e)
        return "数据清理失败，请稍后重试或联系管理员。"


async def do_recreate_container(
    client: NCQQClient,
    instance_name: str,
    clean_data: bool = False,
    keep_config: bool = False,
    node_id: str = "local",
    docker_image: str | None = None,
) -> str:
    """调用管理器 POST /api/containers/{name}/recreate 重建容器。

    自动快照原容器参数（端口/镜像/内存/重启策略），删除旧容器后原参重建。
    clean_data=True 时同时清空数据目录；keep_config=True 则保留 config 子目录。
    """
    try:
        payload: dict = {
            "node_id": node_id,
            "clean_data": clean_data,
            "keep_config": keep_config,
        }
        if docker_image:
            payload["docker_image"] = docker_image
        res = await client.make_request(
            "POST", f"/api/containers/{instance_name}/recreate", json=payload
        )
        if not isinstance(res, dict) or res.get("status") != "ok":
            return "重建请求已发出，但结果暂时无法确认，请稍后查看实例状态。"
        ports = res.get("ports", {})
        cleared = res.get("cleared", [])
        parts = [f"实例 {instance_name} 重建完成。"]
        if ports:
            parts.append(
                f"分配端口：WebUI {ports.get('webui', '-')}、HTTP {ports.get('http', '-')}、WS {ports.get('ws', '-')}"
            )
        if cleared:
            parts.append(f"已清除：{'、'.join(cleared)}")
        return " ".join(parts)
    except Exception as e:
        logger.warning("重建实例 %s 失败: %s", instance_name, e)
        return "重建失败，请稍后重试或联系管理员。"


async def do_inject_by_alias(
    client: NCQQClient,
    alias: str,
    target: str,
    container_name: str = "",
    conn_id: str = "",
    uin: str = "default",
) -> str:
    """通过雷达端点别名执行注入。

    target='bs': 将别名对应端点追加到指定 BS connection 的 target_endpoints（热重载立即生效）。
    target='nc': 将别名对应端点注入指定容器的 websocketClients（需重载 NapCat 配置生效）。
    """
    try:
        payload: dict = {"alias": alias, "target": target, "uin": uin}
        if target == "bs":
            payload["conn_id"] = conn_id or container_name
        else:
            payload["container_name"] = container_name
        res = await client.make_request(
            "POST", "/api/botshepherd/radar/inject-by-alias", json=payload
        )
        status = res.get("status", "unknown") if isinstance(res, dict) else "unknown"
        msg = res.get("message", "") if isinstance(res, dict) else str(res)
        if status == "ok":
            detail = msg.strip()
            if detail:
                return f"接入成功。{detail}"
            return "接入成功。"
        logger.warning(
            "注入失败 alias=%s target=%s conn_id=%s status=%s message=%s",
            alias, target, conn_id or container_name, status, msg,
        )
        hint = f"原因：{msg.strip()}" if msg.strip() else "后端未返回具体原因，请检查 BotShepherd 连接是否已注册。"
        return f"接入失败，{hint}"
    except Exception as e:
        logger.warning("注入 alias=%s target=%s 失败: %s", alias, target, e)
        return "接入失败，请稍后重试或联系管理员。"
