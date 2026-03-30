import json
import logging

from .api import NCQQClient

logger = logging.getLogger(__name__)


async def do_create_instance(client: NCQQClient, instance_name: str) -> str:
    try:
        res = await client.make_request(
            "POST", "/api/containers", json={"name": instance_name}
        )
        return (
            f"创建实例指令已发送！管理器返回：\n{json.dumps(res, ensure_ascii=False)}"
        )
    except Exception as e:
        logger.warning("创建实例 %s 失败: %s", instance_name, e)
        return f"创建失败，请稍后重试或联系管理员。"


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
        return f"管理器底层回报：针对 {instance_name} 执行动作 {action}{suffix} 成功。"
    except Exception as e:
        logger.warning("实例 %s 执行 %s 失败: %s", instance_name, action, e)
        return f"操作执行失败，请稍后重试或联系管理员。"


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
            return f"注入成功。别名={alias} target={target} {'conn_id=' + (conn_id or container_name) if target == 'bs' else 'container=' + container_name}  {msg}".strip()
        return f"注入返回异常状态，请联系管理员排查。"
    except Exception as e:
        logger.warning("注入 alias=%s target=%s 失败: %s", alias, target, e)
        return f"注入失败，请稍后重试或联系管理员。"
