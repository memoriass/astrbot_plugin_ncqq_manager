# Plugin Pages 架构

本插件提供 `ncqq-dashboard` Page，用于在 AstrBot WebUI 中查看多 ncqq-manager 面板状态并处理审批。页面不替代聊天 workflow，也不编辑插件配置。

## 页面目录

| 路径 | 职责 |
| --- | --- |
| `pages/ncqq-dashboard/index.html` | AstrBot 扫描入口。 |
| `pages/ncqq-dashboard/app.js` | 通过 `window.AstrBotPluginPage` bridge 调用插件 API 并渲染页面。 |
| `pages/ncqq-dashboard/style.css` | 基础布局、侧栏和通用控件样式。 |
| `pages/ncqq-dashboard/dashboard.css` | 多面板分组、端点条和实例状态卡样式。 |

页面可在无 bridge 环境下使用预览数据渲染，便于本地检查多面板布局。正式运行时只通过 bridge 请求后端。

## 后端 API

后端 API 在 `tools/page_api.py` 中注册，路由前缀为 `/astrbot_plugin_ncqq_manager`。

| Dashboard endpoint | 方法 | 说明 |
| --- | --- | --- |
| `dashboard/summary` | `GET` | 汇总 manager 健康、实例、后端、审批、绑定和健康快照。 |
| `approvals/<approval_id>/approve` | `POST` | 原子领取审批并复用现有审批执行器批准。 |
| `approvals/<approval_id>/reject` | `POST` | 原子领取审批并拒绝。 |

Page 端调用 bridge 时不写插件名前缀，例如 `bridge.apiGet("dashboard/summary")`。

## 数据边界

- manager 信息只返回 ID、名称、URL 和状态，不返回 API key。
- Dashboard 按 manager 分组渲染，每个 ncqq-manager 面板独立展示健康、实例、容器和端点摘要。
- 实例卡片数据来自目标 manager 的 `/api/containers` 和 `/api/bots`，包括昵称、UIN、头像、登录阶段、心跳和容器状态。
- 后端端点只返回 alias、URL 和 token 是否存在，不返回 token 明文。
- 审批列表不返回原始 `params`，只返回页面展示所需的 manager、实例、后端别名和描述。
- 绑定关系只读展示，不在页面修改。
- 健康快照只展示 `manager/instance` 与在线状态。

## 操作边界

Page 第一版只允许审批：

- approve：调用 `claim_approval()` 后执行 `_dispatch_approved_action()`。
- reject：调用 `claim_approval()` 后移除记录。

不在 Page 中提供实例启动、停止、重启、二维码、后端接入、配置编辑或批量跨 manager 操作。这些能力继续由聊天 workflow 和审批模型承接。

## 维护要求

- 修改 Page API 时同步本文和 `docs/plugin-compliance.md`。
- 新增页面目录时必须包含 `pages/<page_name>/index.html`。
- Page 后端不得绕过 `core/`、`tools/` 中已有的审批和数据读取逻辑。
- 不把真实 token、API key、本地 AstrBot 配置或远端日志写入页面资源。
