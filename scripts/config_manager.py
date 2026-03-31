import logging
from urllib.parse import quote

from .api import NCQQClient

logger = logging.getLogger(__name__)


async def do_read_config(client: NCQQClient, instance_name: str, file_name: str) -> str:
    """Read a config file from the container data directory.

    New API GET /api/containers/{name}/config/{filename:path}
    Response: {status:"ok"|"not_found", content:"<raw string>"}
    """
    try:
        safe_name = quote(file_name, safe="/")
        res = await client.make_request(
            "GET", f"/api/containers/{instance_name}/config/{safe_name}"
        )
        if not isinstance(res, dict):
            return "配置读取失败，请稍后重试。"
        if res.get("status") == "not_found":
            return f"[{instance_name}] 中未找到文件 {file_name}，请确认路径是否正确。"
        content = res.get("content", "")
        lines = [line.rstrip() for line in str(content).splitlines() if line.strip()]
        preview = lines[:12]
        if not preview:
            return f"[{instance_name}] 中的 {file_name} 当前为空。"
        suffix = (
            "\n（内容较长，仅展示前 12 行）"
            if len(lines) > 12
            else ""
        )
        return (
            f"[{instance_name}] 中的 {file_name} 已读取，以下为摘要预览：\n"
            + "\n".join(preview)
            + suffix
        )
    except Exception as e:
        logger.warning("读取配置 %s/%s 失败: %s", instance_name, file_name, e)
        return "读取配置异常，请稍后重试。"


async def do_write_config(
    client: NCQQClient, instance_name: str, file_name: str, file_content: str
) -> str:
    """Write a config file into the container data directory.

    New API POST /api/containers/{name}/config/{filename:path}
    Request body: {content:"<raw string>"}  (plain string, not parsed JSON)
    Response: {status:"ok"}
    """
    try:
        safe_name = quote(file_name, safe="/")
        await client.make_request(
            "POST",
            f"/api/containers/{instance_name}/config/{safe_name}",
            json={"content": file_content},
        )
        return f"配置已保存，实例 {instance_name} 的 {file_name} 已更新。"
    except Exception as e:
        logger.warning("写入配置 %s/%s 失败: %s", instance_name, file_name, e)
        return "写入配置异常，请稍后重试。"
