# ncqq 内部 Workflow 设计

聊天侧只暴露“按能力方向落地”的 workflow。模型先判断用户意图，再选择一个具体 workflow；底层 API 调用、权限判断、审批、分支条件都在该 workflow 内部完成。

核心原则：

- 一个 workflow 只负责一个能力方向。
- workflow 是完整流程，不是单个 API 包装。
- 只接受新 workflow ID，不保留旧入口兼容。
- 不再把 `scope` 当作主要公开接口。

## 公开 Workflow

| workflow | 能力方向 | 说明 |
| --- | --- | --- |
| `create_instance` | 创建流程 | 创建或接续创建实例，按条件绑定用户、启动实例、接入后端、拉二维码 |
| `relogin_instance` | 掉线重登流程 | 检查登录状态，离线时拉二维码，可选先重启 |
| `control_instance` | 控制流程 | 启动、停止、重启、暂停、恢复、强杀 |
| `connect_backend` | 后端接入流程 | 校验端点别名和目标实例，再注入已有后端 |
| `check_instance` | 实例检测流程 | 检查实例存在、登录、资源、日志，可选文件/配置 |
| `list_instances` | 实例列表流程 | 查看实例状态和绑定关系 |
| `check_backends` | 后端端点检测流程 | 查看已配置后端端点，不显示 token 明文 |
| `check_manager` | 管理器健康检测流程 | 检测 ncqq-manager、Docker、状态引擎等 |
| `check_botshepherd` | BotShepherd 检测流程 | 检测 BotShepherd 进程、激活、心跳 |
| `check_bot_runtime` | Bot 运行态检测流程 | 查看 Bot WS 连接与账号运行态 |
| `read_bot_messages` | Bot 消息读取流程 | 读取指定 Bot 最近消息 |
| `audit_operations` | 操作审计流程 | 查看最近操作日志 |
| `inspect_resources` | 资源检测流程 | 查看镜像与节点资产 |
| `read_instance_config` | 配置读取流程 | 查看实例文件树和指定配置文件 |
| `delete_instance` | 销毁流程 | 显式确认后删除实例，可选删除数据目录 |
| `review_approvals` | 审批队列流程 | 管理员查看待审批请求 |

## 选择规则

| 用户意图 | 选择 workflow |
| --- | --- |
| “创建一个实例 / 开一个 bot / 给某人开通” | `create_instance` |
| “掉线了 / 重新登录 / 获取二维码 / 扫码” | `relogin_instance` |
| “重启 / 启动 / 停止 / 暂停” | `control_instance` |
| “把某个后端接到实例上” | `connect_backend` |
| “这个实例有什么问题 / 看日志 / 看资源占用” | `check_instance` |
| “有哪些实例 / 当前状态” | `list_instances` |
| “有哪些后端端点” | `check_backends` |
| “管理器健康 / Docker 是否正常” | `check_manager` |
| “BotShepherd 是否正常” | `check_botshepherd` |
| “Bot 是否连接 / 账号运行态” | `check_bot_runtime` |
| “看某个 Bot 最近消息” | `read_bot_messages` |
| “谁操作过 / 最近变更” | `audit_operations` |
| “有哪些镜像 / 节点资源” | `inspect_resources` |
| “看配置 / 看文件” | `read_instance_config` |
| “删除 / 销毁实例” | `delete_instance` |
| “有哪些审批” | `review_approvals` |

## 创建流程

```mermaid
flowchart TD
    A["create_instance(target=name)"] --> B{"实例名是否明确"}
    B -- 否 --> B1["停止：要求补充实例名"]
    B -- 是 --> C["读取 /api/containers"]
    C --> D{"实例是否已存在"}
    D -- 是 --> E{"当前用户是否有权限"}
    E -- 否 --> E1["停止：实例已存在但无权限"]
    E -- 是 --> F["跳过创建，继续创建后流程"]
    D -- 否 --> G{"触发者是否管理员"}
    G -- 否 --> G1["生成整合审批"]
    G1 --> G2["审批通过后执行：创建、绑定、可选接入后端"]
    G -- 是 --> H["调用 POST /api/containers"]
    H --> I["等待 create/start 事件并重新读取列表"]
    I --> J{"实例是否可见"}
    J -- 否 --> J1["停止：创建已提交，稍后继续重登/接入"]
    J -- 是 --> F
    F --> K{"是否需要绑定用户"}
    K -- 是 --> K1["写入 user_mapping"]
    K -- 否 --> L{"是否需要启动"}
    K1 --> L
    L -- 是且未运行 --> L1["调用 start"]
    L -- 否或已运行 --> M{"是否提供 backend_alias"}
    L1 --> M
    M -- 是 --> M1["接入已有后端"]
    M -- 否 --> N["刷新登录状态"]
    M1 --> N
    N --> O{"是否已登录"}
    O -- 是 --> O1["结束：返回在线账号"]
    O -- 否且 qrcode=true --> P["拉取二维码"]
    O -- 否且 qrcode=false --> P1["结束：提示未登录"]
```

推荐参数：

```json
{
  "backend_alias": "astrbot",
  "bind_qq": "123456",
  "nickname": "可选昵称",
  "qrcode": true,
  "auto_start": true
}
```

## 掉线重登流程

```mermaid
flowchart TD
    A["relogin_instance(target=name)"] --> B{"能否解析目标实例"}
    B -- 否 --> B1["停止：要求指定实例"]
    B -- 是 --> C{"是否有权限"}
    C -- 否 --> C1["停止：无权操作"]
    C -- 是 --> D{"restart_first=true"}
    D -- 是 --> D1["先调用 restart"]
    D -- 否 --> E["刷新登录状态"]
    D1 --> E
    E --> F{"已登录"}
    F -- 是且非 force_qrcode --> F1["结束：返回在线账号"]
    F -- 否 --> G{"qrcode=true 或 force_qrcode=true"}
    G -- 是 --> G1["拉取二维码"]
    G -- 否 --> G2["结束：只报告离线状态"]
```

## 实例检测流程

```mermaid
flowchart TD
    A["check_instance(target=name)"] --> B["读取容器列表"]
    B --> C{"实例是否存在"}
    C -- 否 --> C1["停止：实例不存在"]
    C -- 是 --> D["刷新登录状态"]
    D --> E["读取资源监控"]
    E --> F["读取最近日志"]
    F --> G{"是否指定 path/file_name"}
    G -- 是 --> H["读取文件树或配置摘要"]
    G -- 否 --> I["输出检测结果"]
    H --> I
```

## 调试命令

```text
ncqq create_instance <实例> [端点别名]
ncqq relogin_instance [实例]
ncqq control_instance <start|stop|restart|pause|unpause|kill> [实例]
ncqq connect_backend <端点别名> [实例]
ncqq check_instance [实例]
ncqq list_instances
ncqq check_backends
ncqq check_manager
ncqq check_botshepherd
ncqq check_bot_runtime
ncqq read_bot_messages <实例> [条数]
ncqq audit_operations [条数]
ncqq inspect_resources
ncqq read_instance_config <实例> [文件] [路径]
ncqq delete_instance <实例> confirm [data]
ncqq review_approvals
```
