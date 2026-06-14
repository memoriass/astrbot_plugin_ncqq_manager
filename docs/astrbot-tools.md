# AstrBot Tools

`tools` 存放 `main.py` 混入的 AstrBot 工具能力，负责接收事件参数并调用 `core`。

| 文件 | 职责 |
| --- | --- |
| `tools/instance.py` | 实例列表、动作、二维码、监控、文件、绑定关系展示。 |
| `tools/backend.py` | 后端端点注入和审批入口。 |
| `tools/admin.py` | 审批列表、批准、驳回和已批准动作分发。 |

维护约定：

- 新增聊天侧业务优先放到 `workflows`，不要在这里堆长流程。
- 这里可以保留已有工具行为的兼容层，但不得新增旧命令别名体系。
- 管理员判断统一调用插件实例的 `is_plugin_admin()`。
- 所有实例、后端、二维码和审批执行入口都要接收或解析 `manager_id`，并通过 `client_for_manager()` 调用目标面板。
