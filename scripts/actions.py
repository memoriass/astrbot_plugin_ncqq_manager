import json

from .api import NCQQClient


async def do_create_instance(client: NCQQClient, instance_name: str) -> str:
    try:
        res = await client.make_request(
            "POST", "/api/containers", json={"name": instance_name}
        )
        return (
            f"创建实例指令已发送！管理器返回：\n{json.dumps(res, ensure_ascii=False)}"
        )
    except Exception as e:
        return f"创建失败: {e}"


async def do_instance_action(
    client: NCQQClient, instance_name: str, action: str
) -> str:
    try:
        await client.make_request(
            "POST", f"/api/containers/{instance_name}/action?action={action}"
        )
        return f"管理器底层回报：针对 {instance_name} 执行动作 {action} 成功。"
    except Exception as e:
        return f"操作执行失败，原因: {e}"


async def do_inject_backend(
    client: NCQQClient, instance_name: str, backend_name: str, url: str
) -> str:
    try:
        bs_conns = {}
        try:
            bs_conns = await client.make_request("GET", "/api/botshepherd/connections")
        except Exception:
            pass

        if instance_name in bs_conns:
            conn_data = bs_conns[instance_name]
            conn_data["target_endpoints"] = [url]
            await client.make_request(
                "PUT", f"/api/botshepherd/connections/{instance_name}", json=conn_data
            )
            return f"🌟 [智能注入引擎] 检测到实例 {instance_name} 正处于 BotShepherd(BS) 集群中间件接管状态！已成功通过 BS API 将 target_endpoints 全局覆写为目标端口 [{backend_name}: {url}]。流量已动态切分生效。"
        else:
            payload = {
                "uin": "default",
                "network": {
                    "websocketClients": [
                        {
                            "name": backend_name,
                            "enable": True,
                            "url": url,
                            "reportSelfMessage": False,
                            "messagePostFormat": "array",
                            "token": "",
                            "debug": False,
                            "heartInterval": 30000,
                            "reconnectInterval": 30000,
                        }
                    ]
                },
            }
            await client.make_request(
                "POST",
                f"/api/containers/{instance_name}/inject-network-config",
                json=payload,
            )
            await client.make_request(
                "POST", f"/api/containers/{instance_name}/action?action=restart"
            )
            return f"🔌 [智能注入引擎] 检测到实例 {instance_name} 处于原生 NapCat 直通状态！已向其底层配置注入 WS 直连节点 [{backend_name}: {url}]，并发起容器重启请求使其生效。"
    except Exception as e:
        return f"动态环境嗅探与注入失败: {e}"
