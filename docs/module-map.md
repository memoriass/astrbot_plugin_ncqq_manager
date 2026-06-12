# 模块结构说明

当前项目运行代码按正式插件职责拆分为 `core`、`tools`、`workflows`、`rendering` 四组。

## 目录总览

| 目录 | 面向对象 | 说明 |
| --- | --- | --- |
| `core/` | 底层服务 | HTTP 客户端、API 动作、监控查询、审批、健康检查。 |
| `tools/` | AstrBot 入口 | `main.py` 混入的工具能力，负责把 AstrBot 事件转到底层服务。 |
| `workflows/` | 业务编排 | LLM 和 `/ncqq` 只选择 workflow，由这里串联底层服务。 |
| `rendering/` | 图文渲染 | HTML 模板转图片和降级输出。 |
| `templates/` | 资源模板 | 实例列表、绑定关系、告警图模板。 |

## 维护边界

- `main.py` 不写具体业务流程，只做 AstrBot 生命周期和入口分发。
- `workflows/` 只编排业务，不直接处理 AstrBot 配置或 KV 存储细节。
- `tools/` 负责兼容既有命令/tool 行为，不新增底层 HTTP 逻辑。
- `core/` 不依赖 `tools/`，避免底层服务反向调用入口层。
- `rendering/` 只处理渲染，不读写审批、绑定或远端状态。

## 新增能力放置规则

| 需求 | 放置位置 |
| --- | --- |
| 新 ncqq-manager API 封装 | `core/actions.py` 或 `core/monitoring.py` |
| 新聊天业务流程 | `workflows/models.py`、`workflows/parsing.py`、对应 flow 文件、`workflows/dispatcher.py` |
| 新 AstrBot 命令或工具混入 | `tools/` |
| 新 HTML 图片输出 | `rendering/html_renderer.py` 与 `templates/` |
| 新交接或结构说明 | `docs/` 下按架构功能命名的文档 |
