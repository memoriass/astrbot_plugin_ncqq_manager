# NapCat QQ Manager 插件 - 接口文档

## 公共接口

### NCQQAPIClient (api_client.py)

```python
class NCQQAPIClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 10)
    
    async def get_cluster_config(self) -> ClusterConfig
    async def list_containers(self) -> List[Container]
    async def get_container(self, name: str) -> Optional[Container]
    async def create_container(self, request: CreateContainerRequest) -> Dict[str, Any]
    async def start_container(self, name: str) -> Dict[str, Any]
    async def stop_container(self, name: str) -> Dict[str, Any]
    async def restart_container(self, name: str) -> Dict[str, Any]
    async def delete_container(self, name: str, delete_data: bool = False) -> Dict[str, Any]
    async def list_nodes(self) -> List[Node]
    async def test_connection(self) -> bool
```

### 数据模型 (models.py)

```python
class ContainerStatus(str, Enum):
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
    id: str
    name: str
    status: ContainerStatus
    node_id: str = "local"
    uin: Optional[str] = None
    webui_port: Optional[int] = None
    http_port: Optional[int] = None
    ws_port: Optional[int] = None
    created_at: Optional[str] = None

class Node(BaseModel):
    node_id: str
    name: str
    address: str
    status: str = "unknown"
    cpu_percent: float = 0.0
    mem_percent: float = 0.0
    container_count: int = 0

class SystemInfo(BaseModel):
    cpu_percent: float
    mem_percent: float
    platform: str
    python_version: str

class ClusterConfig(BaseModel):
    docker_image: str
    webui_base_port: int
    http_base_port: int
    ws_base_port: int
    api_key: str
    data_dir: str
    system: SystemInfo

class CreateContainerRequest(BaseModel):
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
```

### 格式化工具 (utils.py)

```python
def format_status(status: ContainerStatus) -> str
def format_container_info(container: Container) -> str
def format_container_list(containers: List[Container]) -> str
def format_node_list(nodes: List[Node]) -> str
```

### 插件主类 (main.py)

```python
class Main(Star):
    def __init__(self, context: Context, config: dict)
    
    # 命令处理方法
    async def help_command(self, event: AstrMessageEvent)
    async def status_command(self, event: AstrMessageEvent)
    async def list_containers_command(self, event: AstrMessageEvent)
    async def container_info_command(self, event: AstrMessageEvent, container_name: str = "")
    async def start_container_command(self, event: AstrMessageEvent, container_name: str = "")
    async def stop_container_command(self, event: AstrMessageEvent, container_name: str = "")
    async def restart_container_command(self, event: AstrMessageEvent, container_name: str = "")
    async def delete_container_command(self, event: AstrMessageEvent, container_name: str = "")
    async def create_container_command(self, event: AstrMessageEvent, container_name: str = "")
    async def list_nodes_command(self, event: AstrMessageEvent)
    async def start_all_containers_command(self, event: AstrMessageEvent)
    async def stop_all_containers_command(self, event: AstrMessageEvent)
```

## 配置接口

### _conf_schema.json

```json
{
  "api_url": {
    "type": "string",
    "description": "API 地址",
    "hint": "ncqq-manager 服务器地址，例如: http://localhost:8000",
    "default": "http://localhost:8000"
  },
  "api_key": {
    "type": "string",
    "description": "API 密钥",
    "hint": "ncqq-manager 的 API 密钥，用于身份验证",
    "default": ""
  },
  "timeout": {
    "type": "int",
    "description": "请求超时时间",
    "hint": "API 请求超时时间（秒），范围 5-60",
    "default": 10
  },
  "admin_only": {
    "type": "bool",
    "description": "仅管理员可用",
    "hint": "是否仅允许管理员使用此插件",
    "default": true
  }
}
```

## 依赖

```
aiohttp>=3.9.0
pydantic>=2.0.0
```

## Updated

2026-03-08T16:02:00+08:00

