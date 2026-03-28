from astrbot.api.all import Image

from .api import NCQQClient


async def do_check_login_status(client: NCQQClient, instance_name: str) -> dict:
    """Call POST /api/containers/{name}/refresh-login.

    New API response: {status:"ok", logged_in:bool, uin:"", nickname:"", method:""}
    On error returns: {status:"error", logged_in:False, msg:"..."}
    """
    try:
        res = await client.make_request(
            "POST", f"/api/containers/{instance_name}/refresh-login"
        )
        return res if isinstance(res, dict) else {"status": "ok", "logged_in": False}
    except Exception as e:
        return {"status": "error", "logged_in": False, "msg": f"接口故障: {e}"}


def is_qrcode_available_status(status_payload: dict) -> tuple[bool, str]:
    """Determine whether the instance is eligible for QR code retrieval.

    New API refresh-login returns {logged_in:bool, ...}.
    - logged_in=True  → already online, QR not needed
    - status=="error" → interface failure, QR not available
    - otherwise       → offline/waiting, QR available
    """
    if status_payload.get("status") == "error":
        msg = str(status_payload.get("msg", "接口故障"))
        return False, msg
    logged_in = status_payload.get("logged_in", False)
    if logged_in:
        uin = status_payload.get("uin", "")
        nickname = status_payload.get("nickname", "")
        label = f"{nickname}({uin})" if uin else "已登录"
        return False, f"实例当前在线（{label}），无需扫码。"
    return True, ""


async def do_get_qrcode(client: NCQQClient, instance_name: str) -> list:
    """Fetch QR code for an instance. Returns a list of str / Image items.

    New API GET /api/containers/{name}/qrcode response variants:
      {status:"logged_in", uin:"..."}
      {status:"ok", url:"data:image/png;base64,...", type:"file"}
      {status:"ok", url:"https://...", type:"log"}
      {status:"waiting"}
    """
    try:
        res = await client.make_request(
            "GET", f"/api/containers/{instance_name}/qrcode"
        )
        if not isinstance(res, dict):
            return [f"接口返回格式异常：{res}"]

        status = str(res.get("status", "")).lower().strip()

        if status == "logged_in":
            uin = res.get("uin", "")
            return [f"实例已登录（QQ: {uin}），无需扫码。"]

        if status == "waiting":
            return ["容器尚未就绪或正在启动中，暂时无法获取二维码，请稍后重试。"]

        if status == "ok":
            url: str = res.get("url", "")
            qr_type: str = res.get("type", "")
            if url.startswith("data:image"):
                # Inline base64 image (type=="file")
                b64_data = url.split(",", 1)[1] if "," in url else url
                return [
                    Image.fromBase64(b64_data),
                    "登录二维码已就绪，请尽快用手机 QQ 扫码登录。",
                ]
            if url.startswith("http"):
                # External URL extracted from container logs (type=="log")
                return [
                    Image.fromURL(url),
                    "从容器日志中提取到二维码地址，请尽快扫码登录。",
                ]
            return [f"二维码获取成功，但 URL 格式未识别：{url!r}（type={qr_type}）"]

        return [f"接口返回未知状态：{res}"]
    except Exception as e:
        return [f"接口调用异常: {e}"]
