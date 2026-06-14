# Multi Manager Upgrade Plan

目标：让插件同时管理多个 ncqq-manager 面板，例如本地面板与云端面板。BotShepherd/radar endpoint 仍属于各自 ncqq-manager 面板内部的后端端点，不和 manager 面板概念混用。

## 改造清单

- [x] 配置层：保留旧 `manager_url` / `api_key` 单面板配置，新增多面板配置入口，并保持向后兼容。
- [x] Client 层：从单个 `NCQQClient` 升级为 manager registry，按 `manager_id` 复用独立 HTTP session。
- [x] Workflow 参数：支持 `manager` / `manager_id` / `panel` 参数，并支持 `manager/instance` 形式的目标实例。
- [x] 绑定模型：兼容旧 `instances: ["name"]`，新增 `manager/name` 命名空间，避免本地和云端同名实例冲突。
- [x] 权限校验：所有用户侧实例操作必须同时校验 `manager_id` 和 `instance_name`。
- [x] 审批记录：创建、删除、后端接入审批必须记录目标 `manager_id`，管理员批准时回到正确面板执行。
- [x] 查询与诊断：实例、后端、健康、资源、配置、日志等查询按目标 manager 执行。
- [x] 文档：更新 README、工作流说明、模块说明和合规说明。
- [x] 校验：运行 Python 编译、JSON 解析、行数检查、密钥扫描和基础解析回归。

## 配置格式

旧配置继续可用：

```json
{
  "manager_url": "http://127.0.0.1:8080",
  "api_key": "..."
}
```

新增 `manager_profiles` 使用 JSON 文本，便于在 AstrBot 配置面板中编辑复杂列表：

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

`default_manager` 控制未显式指定时使用的面板。若未配置多面板，则旧单面板自动作为 `default`。

## 调用约定

- LLM tool 参数：`{"manager":"cloud","intent":"control","action":"restart"}`。
- CLI 参数：`/ncqq query health manager=cloud detail`。
- 目标实例可写成 `cloud/mybot`；解析后 manager 为 `cloud`，实例名为 `mybot`。

## Plugin Pages

Plugin Pages 适合第二阶段做 WebUI 管理面板：多 manager 配置、连通性测试、实例总览、审批队列和健康看板。第一阶段先完成后端能力与聊天工作流，避免 UI 和权限模型同时变化导致风险扩大。

## 本次落地范围

- 2.1.0 后端能力已支持多 ncqq-manager 面板。
- 管理器选择在聊天工具参数、`/ncqq` CLI 和 `manager/instance` 目标写法中生效。
- 定时健康检查会遍历所有已配置 manager，并以 `manager/instance` 作为快照 key。
- Plugin Pages 暂不实现，后续作为 WebUI 管理增强单独推进。
