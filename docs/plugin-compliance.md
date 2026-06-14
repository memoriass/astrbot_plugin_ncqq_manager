# AstrBot 插件合规检查

检查依据：AstrBot 开发文档 `dev/star/plugin-new.html` 与插件发布说明。

## 当前结论

当前项目结构已按 AstrBot 插件约定补齐：

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| `metadata.yaml` | 已满足 | 位于插件根目录，包含 `name`、`display_name`、`author`、`desc`、`short_desc`、`version`、`repo`。 |
| `astrbot_version` | 已满足 | 声明 `>=4.25.0,<5.0.0`，避免在未验证的旧版本 AstrBot 中加载。 |
| `support_platforms` | 已满足 | 声明 `aiocqhttp`，按 OneBot v11 标准消息使用，不考虑 WeChat adapter。 |
| `main.py` | 已满足 | 插件主类入口，显式导入 AstrBot API；`@register(...)` 的作者、版本、仓库地址与 `metadata.yaml` 对齐。 |
| `__init__.py` | 已满足 | 导出插件类，保留包入口。 |
| `_conf_schema.json` | 已满足 | 使用 AstrBot 支持的 `string`、`bool`、`int` 类型；多面板列表以 JSON 文本方式配置。 |
| `logo.png` | 已满足 | 已替换为 AstrBot 与 ncqq 看板娘拥抱的扁平动画图标，正式图为官方推荐的 256x256 透明 PNG。 |
| `requirements.txt` | 已满足 | 声明运行时外部依赖 `aiohttp`。 |
| 日志入口 | 已满足 | 插件与脚本模块统一使用 `astrbot.api.logger`。 |
| 大文件拆分 | 已满足 | 所有文本/代码文件均低于 500 行。 |
| 发布包清洁度 | 已满足 | 已新增 `.gitignore` 并从版本库移除 Python 运行缓存与未使用候选图资产。 |

## Plugin Pages 结论

AstrBot Plugin Pages 适合在第二阶段提供独立 WebUI，例如多面板连通性测试、实例总览、审批队列和健康看板。当前 2.1.0 先把多面板能力落在配置 schema、聊天 workflow 和权限模型里；简单配置仍使用 `_conf_schema.json`，避免同时引入页面前端和权限交互风险。

## 结构约定

- 插件入口层保持在根目录：`main.py`、`__init__.py`、`metadata.yaml`、`_conf_schema.json`、`logo.png`。
- 运行代码按 `core/`、`tools/`、`workflows/`、`rendering/` 分层。
- 面向后续模型接手的说明放在 `docs/architecture.md`、`docs/module-map.md` 和按架构功能命名的文档中，代码内只保留必要短注释或 docstring。根目录保留唯一 `README.md`。

## 发布前复查

发布或同步到远端前建议执行：

```powershell
python -c "import json, pathlib; json.loads(pathlib.Path('_conf_schema.json').read_text(encoding='utf-8')); print('schema ok')"
python -c "from pathlib import Path; files=['main.py',*map(str, Path('core').glob('*.py')),*map(str, Path('tools').glob('*.py')),*map(str, Path('workflows').glob('*.py')),*map(str, Path('rendering').glob('*.py'))]; [compile(Path(f).read_text(encoding='utf-8-sig'), f, 'exec') for f in files]; print('compile ok')"
git diff --check
```
