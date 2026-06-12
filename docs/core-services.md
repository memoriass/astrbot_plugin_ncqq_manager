# Core Services

`core` 是插件的底层服务层，不负责 AstrBot 入口编排。

| 文件 | 职责 |
| --- | --- |
| `core/client.py` | 复用的 ncqq-manager HTTP 客户端。 |
| `core/actions.py` | 创建、删除、生命周期控制、后端注入等写操作。 |
| `core/monitoring.py` | 容器列表、资源、日志、文件、SSE 确认、后端端点读取。 |
| `core/interaction.py` | 登录状态刷新和二维码读取。 |
| `core/config_reader.py` | 容器内配置文件读取。 |
| `core/approval.py` | 审批 KV 队列、过期清理、原子领取。 |
| `core/health_check.py` | 定时掉线检测和通知。 |

维护约定：

- 底层 API 返回尽量保持原始结构，由 `tools` 或 `workflows` 决定展示文案。
- 高权限用户侧操作不得绕过 `core/approval.py`。
- 本层可以依赖 `rendering` 做健康告警图片，但不得依赖 `tools`。
