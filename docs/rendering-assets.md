# Rendering And Assets

`rendering` 负责把 HTML 模板渲染为 AstrBot 可发送图片，并提供文本降级。正式插件图标只保留根目录 `logo.png`。

## Rendering

| 文件 | 职责 |
| --- | --- |
| `rendering/html_renderer.py` | 实例列表、绑定关系、健康告警 HTML 转图片。 |
| `templates/instances.html` | 实例列表模板。 |
| `templates/bindings.html` | 绑定关系模板。 |
| `templates/alert.html` | 健康告警模板。 |

维护约定：

- 模板文件放在根目录 `templates/`。
- 渲染失败必须提供文本降级，避免功能不可用。
- 不在本层读取远端 API 或处理权限。

## Assets

| 文件 | 说明 |
| --- | --- |
| `logo.png` | 根目录正式插件图标，256x256 透明 PNG，AstrBot 与 ncqq 看板娘拥抱形象。 |
