# AstrBot Plugin: ncqq-manager

NapCatQQ 容器控制与后端路由管理插件。插件面向 OneBot v11 场景，提供实例状态查询、登录恢复、生命周期控制、后端接入、健康诊断和审批队列。

维护和接手请先看：

- [架构说明](docs/architecture.md)
- [模块结构说明](docs/module-map.md)
- [工作流说明](docs/workflows.md)
- [插件合规检查](docs/plugin-compliance.md)

## 能力

- 通过统一 LLM 工具 `ncqq_manager` 调用 ncqq 工作流。
- 通过 `/ncqq` 命令进行确定性调试和人工触发。
- 支持同时配置多个 ncqq-manager 面板，用 `manager/instance` 区分本地和云端实例。
- 普通用户只可操作已绑定实例。
- 创建、删除、后端接入等高权限动作进入审批队列。
- 管理员可读取健康、消息、审计、资源和配置诊断信息。
- 实例列表、绑定关系和告警支持 HTML 转图片，渲染失败时回退文本。

## 安装

1. 将插件目录放到 `AstrBot/data/plugins/astrbot_plugin_ncqq_manager`。
2. 安装依赖，AstrBot 会读取根目录 `requirements.txt`。
3. 在 AstrBot WebUI 的插件配置中填写：
   - `manager_url`: ncqq-manager 后端地址。
   - `api_key`: ncqq-manager API Key。
   - `default_manager`: 默认面板 ID，单面板时可保持 `default`。
   - `manager_profiles`: 可选 JSON 数组，用于同时配置本地和云端面板。
4. 平台使用 OneBot v11，也就是 AstrBot 的 `aiocqhttp` 适配器。

多面板配置示例：

```json
[
  {
    "id": "local",
    "name": "本地面板",
    "manager_url": "http://127.0.0.1:8080",
    "api_key": "..."
  },
  {
    "id": "cloud",
    "name": "云端面板",
    "manager_url": "https://example.com",
    "api_key": "..."
  }
]
```

聊天或调试命令中可写 `manager=cloud`，也可把实例写成 `cloud/mybot`。

## 工作流入口

聊天场景优先使用主工作流：

| workflow | 用途 |
| --- | --- |
| `manage_instance` | 实例主流程，按 `intent` 路由到创建、重登、控制、检测、列表、销毁等动作。 |
| `query` | 查询主流程，按 `scope` 查询实例、后端、健康、消息、审计、资源或配置。 |
| `manage_backend` | 后端主流程，查看端点或把已有端点接入实例。 |
| `review_approvals` | 管理员审批队列，支持 list/approve/reject。 |

细分工作流仍可直接调用，主要用于模型已经明确目标场景时：

- `create_instance`
- `relogin_instance`
- `control_instance`
- `connect_backend`
- `check_instance`
- `list_instances`
- `check_backends`
- `check_health`
- `read_bot_messages`
- `audit_operations`
- `inspect_resources`
- `read_instance_config`
- `delete_instance`

## 调试命令

使用 AstrBot 唤醒前缀加 `/ncqq`：

```text
/ncqq help
/ncqq query health detail
/ncqq query health manager=cloud detail
/ncqq manage_instance control restart <实例名>
/ncqq manage_instance control restart cloud/<实例名>
/ncqq manage_backend connect <端点别名> <实例名>
/ncqq review_approvals
/ncqq review_approvals approve <审批ID>
```

## 项目结构

```text
main.py                AstrBot 生命周期、LLM 工具和命令入口
core/                  HTTP 客户端、API 动作、审批、健康检查
tools/                 AstrBot 工具混入和审批快捷入口
workflows/             业务工作流路由、解析、权限和格式化
rendering/             HTML 转图片与文本降级
templates/             HTML 模板
docs/                  架构与维护说明
```

## 发布检查

```powershell
python -X utf8 -m compileall main.py core tools workflows rendering
python -X utf8 -c "import json; json.load(open('_conf_schema.json', encoding='utf-8')); print('json ok')"
git diff --check
```

## License

GPL-3.0
