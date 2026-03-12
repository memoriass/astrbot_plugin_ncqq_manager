"""数据模型定义"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel


class ContainerStatus(str, Enum):
    """容器状态枚举"""

    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    RESTARTING = "restarting"
    REMOVING = "removing"
    EXITED = "exited"
    DEAD = "dead"
    CREATED = "created"
    UNKNOWN = "unknown"


class Container(BaseModel):
    """容器信息模型"""

    id: str
    name: str
    status: ContainerStatus
    node_id: str = "local"
    uin: Optional[str] = None
    webui_port: Optional[int] = None
    http_port: Optional[int] = None
    ws_port: Optional[int] = None
    created_at: Optional[str] = None

    class Config:
        use_enum_values = True


class Node(BaseModel):
    """节点信息模型"""

    node_id: str
    name: str
    address: str
    status: str = "unknown"
    cpu_percent: float = 0.0
    mem_percent: float = 0.0
    container_count: int = 0


class SystemInfo(BaseModel):
    """系统信息模型"""

    cpu_percent: float
    mem_percent: float
    platform: str
    python_version: str


class ClusterConfig(BaseModel):
    """集群配置模型"""

    docker_image: str
    webui_base_port: int
    http_base_port: int
    ws_base_port: int
    api_key: str
    data_dir: str
    system: SystemInfo


class CreateContainerRequest(BaseModel):
    """创建容器请求模型"""

    name: str
    node_id: str = "local"
    docker_image: Optional[str] = None
    webui_port: int = 0
    http_port: int = 0
    ws_port: int = 0
    memory_limit: int = 0
    restart_policy: str = "always"
    network_mode: str = "bridge"
    env_vars: list = []
