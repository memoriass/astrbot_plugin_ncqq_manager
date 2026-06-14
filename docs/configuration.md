# 配置说明

本文说明 `_conf_schema.json` 中的正式配置项。真实 API key、token、本地地址和测试日志不得写入仓库文档。

## Manager 配置

单面板配置：

| 配置项 | 类型 | 说明 |
| --- | --- | --- |
| `manager_url` | `string` | ncqq-manager 后端地址，例如 `http://127.0.0.1:8080`。 |
| `api_key` | `string` | ncqq-manager API key。 |
| `default_manager` | `string` | 默认 manager ID。单面板可保持 `default`。 |

多面板配置使用 `manager_profiles`，值为 JSON 文本：

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

若 `manager_profiles` 留空，插件使用 `manager_url` / `api_key` 作为旧单面板配置。若同时配置旧字段和多面板列表，旧字段会作为 `default_manager` 对应的 profile 保留。

## 二维码配置

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `qrcode_private` | `bool` | `true` | 群聊触发二维码时，通过私聊发送给请求者。私聊失败时回退到群内直接展示。 |

## 通知配置

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enable_offline_notify` | `bool` | `true` | 启用定时掉线检测。 |
| `health_check_interval` | `int` | `5` | 掉线检测间隔，单位分钟。 |
| `notify_group` | `string` | 空 | 掉线和恢复通知推送群号；留空则不推送群通知。 |

定时健康检查会遍历所有 configured manager。快照 key 使用 `manager/instance`，避免不同面板同名实例互相覆盖状态。

## 群聊白名单

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enable_group_whitelist` | `bool` | `false` | 开启后只响应指定群聊。 |
| `response_groups` | `string` | 空 | 允许响应的群号，支持逗号、空格、顿号分隔。 |

白名单只限制群聊入口，不限制私聊。作用范围包括：

- LLM 工具入口 `ncqq_manager`
- `/ncqq` 调试命令
- 群内审批快捷回复

## 安全要求

- 文档和测试记录中只写示例 key，例如 `...`。
- 不提交真实 `manager_profiles`。
- 不把从远端复制的 AstrBot AI 配置写入仓库。
- 本地配置和接入测试记录放入 ignored 目录：`local-docs/` 或 `docs/current/`。
