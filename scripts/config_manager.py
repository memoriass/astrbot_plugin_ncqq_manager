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
            return f"读取配置异常：响应格式非预期 {res}"
        if res.get("status") == "not_found":
            return f"[{instance_name}] 中未找到文件 {file_name}，请确认路径是否正确。"
        content = res.get("content", "")
        return f"[{instance_name}] 中的 {file_name} 内容如下：\n{content}"
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
        return f"保存成功！[{instance_name}] 的 {file_name} 已在后台更新。"
    except Exception as e:
        logger.warning("写入配置 %s/%s 失败: %s", instance_name, file_name, e)
        return "写入配置异常，请稍后重试。"
