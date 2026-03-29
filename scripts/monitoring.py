import json

from .api import NCQQClient


async def do_list_instances(
    client: NCQQClient, allowed_instances: list, is_admin: bool
) -> list | str:
    """Return containers list on success, or an error str on failure."""
    try:
        res = await client.make_request("GET", "/api/containers")
        containers = res.get("containers", [])

        if not is_admin:
            containers = [c for c in containers if c.get("name") in allowed_instances]

        if not containers:
            return "当前没有任何您有权限查看的协议端实例正在运行。"

        return containers
    except Exception as e:
        return f"发生网络或配置错误: {e}"


async def do_list_assets(client: NCQQClient) -> str:
    try:
        images_res = await client.make_request("GET", "/api/images")
        nodes_res = await client.make_request("GET", "/api/nodes")
        images = (
            images_res.get("images", []) if isinstance(images_res, dict) else images_res
        )
        nodes = nodes_res.get("nodes", []) if isinstance(nodes_res, dict) else nodes_res
        return (
            f"资产拉取成功。\n"
            f"【镜像列表】:\n{json.dumps(images, ensure_ascii=False)}\n\n"
            f"【集群节点】:\n{json.dumps(nodes, ensure_ascii=False)}"
        )
    except Exception as e:
        return f"资产拉取失败: {e}"


async def do_list_files(client: NCQQClient, instance_name: str, path: str = "") -> str:
    """列出容器数据目录下的文件和子目录。"""
    try:
        url = f"/api/containers/{instance_name}/files"
        if path:
            url += f"?path={path}"
        res = await client.make_request("GET", url)
        files = res.get("files", []) if isinstance(res, dict) else []
        folders = res.get("folders", []) if isinstance(res, dict) else []
        current = res.get("current_path", path) if isinstance(res, dict) else path
        return (
            f"实例 {instance_name} 路径 '{current}' 内容:\n"
            f"【目录】: {json.dumps([f['name'] for f in folders], ensure_ascii=False)}\n"
            f"【文件】: {json.dumps([{'name': f['name'], 'size': f.get('size', 0)} for f in files], ensure_ascii=False)}"
        )
    except Exception as e:
        return f"文件列表获取失败: {e}"


async def do_get_radar_endpoints(client: NCQQClient) -> list:
    """读取服务端雷达端点库，返回 [{alias, url, token}] 列表。"""
    try:
        res = await client.make_request("GET", "/api/botshepherd/radar/endpoints")
        return res.get("endpoints", []) if isinstance(res, dict) else []
    except Exception:
        return []


async def do_save_radar_endpoints(client: NCQQClient, endpoints: list) -> str:
    """全量覆写服务端雷达端点库。endpoints 格式: [{alias, url, token}]"""
    try:
        res = await client.make_request(
            "POST", "/api/botshepherd/radar/endpoints", json={"endpoints": endpoints}
        )
        count = (
            res.get("count", len(endpoints))
            if isinstance(res, dict)
            else len(endpoints)
        )
        return f"雷达端点库已更新，共 {count} 条记录。"
    except Exception as e:
        return f"端点库保存失败: {e}"


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
