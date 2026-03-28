import json

from .api import NCQQClient


async def do_list_instances(
    client: NCQQClient, allowed_instances: list, is_admin: bool
) -> str:
    try:
        res = await client.make_request("GET", "/api/containers")
        containers = res.get("containers", [])

        if not is_admin:
            containers = [c for c in containers if c.get("name") in allowed_instances]

        if not containers:
            return "当前没有任何您有权限查看的协议端实例正在运行。"

        return f"你的实例列表获取成功，请将其转化为友好的文本展示:\n{json.dumps(containers, ensure_ascii=False)}"
    except Exception as e:
        return f"发生网络或配置错误: {e}"


async def do_list_assets(client: NCQQClient) -> str:
    try:
        images = await client.make_request("GET", "/api/images")
        nodes = await client.make_request("GET", "/api/nodes")
        return f"资产拉取成功。\n【镜像列表】:\n{json.dumps(images, ensure_ascii=False)}\n\n【集群节点】:\n{json.dumps(nodes, ensure_ascii=False)}"
    except Exception as e:
        return f"资产拉取失败: {e}"


async def do_get_monitor(
    client: NCQQClient, instance_name: str, fetch_logs: bool
) -> str:
    try:
        if fetch_logs:
            res = await client.make_request(
                "GET", f"/api/containers/{instance_name}/logs?lines=30"
            )
            logs = res.get("logs", "") if isinstance(res, dict) else str(res)
            return f"抓取到最近30行核心日志供分析：\n{logs}"
        else:
            res = await client.make_request(
                "GET", f"/api/containers/{instance_name}/stats"
            )
            return f"Docker底层性能数据：\n{json.dumps(res, ensure_ascii=False)}"
    except Exception as e:
        return f"监控调用失败: {e}"
