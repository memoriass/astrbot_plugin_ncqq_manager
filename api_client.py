"""ncqq-manager API 客户端"""

import aiohttp
from typing import List, Optional, Dict, Any
from astrbot.api import logger

from .models import (
    Container,
    Node,
    ClusterConfig,
    CreateContainerRequest,
    ContainerStatus,
)


class NCQQAPIClient:
    """ncqq-manager API 客户端"""

    def __init__(self, base_url: str, api_key: str, timeout: int = 10):
        """
        初始化 API 客户端

        Args:
            base_url: API 基础地址，例如 http://localhost:8000
            api_key: API 密钥
            timeout: 请求超时时间（秒）
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.headers = {
            "x-request-api-key": api_key,
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        发送 HTTP 请求

        Args:
            method: HTTP 方法
            endpoint: API 端点
            data: 请求体数据
            params: URL 参数

        Returns:
            响应数据字典

        Raises:
            Exception: 请求失败时抛出异常
        """
        url = f"{self.base_url}{endpoint}"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    json=data,
                    params=params,
                ) as response:
                    if response.status >= 400:
                        error_text = await response.text()
                        raise Exception(
                            f"API 请求失败 [{response.status}]: {error_text}"
                        )

                    return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"API 请求异常: {e}")
            raise Exception(f"网络请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"未知错误: {e}")
            raise

    async def get_cluster_config(self) -> ClusterConfig:
        """获取集群配置信息"""
        data = await self._request("GET", "/api/cluster/config")
        return ClusterConfig(**data["config"], system=data["system"])

    async def list_containers(self) -> List[Container]:
        """获取所有容器列表"""
        data = await self._request("GET", "/api/containers")
        containers = []
        for item in data.get("containers", []):
            try:
                status = ContainerStatus(item.get("status", "unknown"))
            except ValueError:
                status = ContainerStatus.UNKNOWN

            containers.append(
                Container(
                    id=item.get("id", ""),
                    name=item["name"],
                    status=status,
                    node_id=item.get("node_id", "local"),
                    uin=item.get("uin"),
                    webui_port=item.get("webui_port"),
                    http_port=item.get("http_port"),
                    ws_port=item.get("ws_port"),
                    created_at=item.get("created_at"),
                )
            )
        return containers

    async def get_container(self, name: str) -> Optional[Container]:
        """获取指定容器信息"""
        data = await self._request("GET", f"/api/containers/{name}")
        if data.get("status") != "ok":
            return None

        item = data.get("container", {})
        try:
            status = ContainerStatus(item.get("status", "unknown"))
        except ValueError:
            status = ContainerStatus.UNKNOWN

        return Container(
            id=item.get("id", ""),
            name=item["name"],
            status=status,
            node_id=item.get("node_id", "local"),
            uin=item.get("uin"),
            webui_port=item.get("webui_port"),
            http_port=item.get("http_port"),
            ws_port=item.get("ws_port"),
            created_at=item.get("created_at"),
        )

    async def create_container(self, request: CreateContainerRequest) -> Dict[str, Any]:
        """创建新容器"""
        return await self._request("POST", "/api/containers", data=request.dict())

    async def start_container(self, name: str) -> Dict[str, Any]:
        """启动容器"""
        return await self._request("POST", f"/api/containers/{name}/start")

    async def stop_container(self, name: str) -> Dict[str, Any]:
        """停止容器"""
        return await self._request("POST", f"/api/containers/{name}/stop")

    async def restart_container(self, name: str) -> Dict[str, Any]:
        """重启容器"""
        return await self._request("POST", f"/api/containers/{name}/restart")

    async def delete_container(
        self, name: str, delete_data: bool = False
    ) -> Dict[str, Any]:
        """删除容器"""
        return await self._request(
            "DELETE",
            f"/api/containers/{name}",
            data={"delete_data": delete_data},
        )

    async def list_nodes(self) -> List[Node]:
        """获取所有节点列表"""
        data = await self._request("GET", "/api/nodes")
        nodes = []
        for item in data.get("nodes", []):
            nodes.append(
                Node(
                    node_id=item.get("node_id", "unknown"),
                    name=item.get("name", "Unknown"),
                    address=item.get("address", ""),
                    status=item.get("status", "unknown"),
                    cpu_percent=item.get("cpu_percent", 0.0),
                    mem_percent=item.get("mem_percent", 0.0),
                    container_count=item.get("container_count", 0),
                )
            )
        return nodes

    async def test_connection(self) -> bool:
        """测试 API 连接"""
        try:
            await self.get_cluster_config()
            return True
        except Exception:
            return False

    async def get_qrcode(self, name: str, node_id: str = "local") -> Dict[str, Any]:
        """获取容器登录二维码"""
        return await self._request(
            "GET",
            f"/api/containers/{name}/qrcode",
            params={"node_id": node_id},
        )
