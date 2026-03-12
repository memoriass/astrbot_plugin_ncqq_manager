# NapCat QQ Manager 插件 - 文件树

**Generated**: 2026-03-08T16:02:30+08:00

```
data/plugins/astrbot_plugin_ncqq_manager/
├── docs/
│   └── current/
│       ├── overview.md          # 项目概览（40 行）
│       ├── plan.md              # 实施计划（150 行）
│       ├── task.md              # 执行日志（176 行）
│       ├── SUMMARY.md           # 完成总结（150 行）
│       ├── INTERFACE.md         # 接口文档（150 行）
│       └── TREE.md              # 文件树（本文件）
├── __init__.py                  # 包初始化（7 行）
├── metadata.yaml                # 插件元数据（6 行）
├── requirements.txt             # 依赖声明（2 行）
├── _conf_schema.json            # 配置模式（28 行）
├── README.md                    # 使用文档（97 行）
├── models.py                    # 数据模型（78 行）
├── utils.py                     # 格式化工具（81 行）
├── api_client.py                # API 客户端（181 行）
├── commands.py                  # 命令处理（360 行）
└── main.py                      # 插件主类（403 行）
```

## 文件统计

| 类型 | 文件数 | 总行数 |
|------|--------|--------|
| 文档 | 6 | 766 |
| 代码 | 7 | 1,138 |
| 配置 | 3 | 36 |
| **总计** | **16** | **1,940** |

## 模块说明

### 核心模块
- `main.py` - 插件主类，命令注册与分发
- `api_client.py` - ncqq-manager API 客户端封装
- `commands.py` - 命令处理函数集合
- `models.py` - 数据模型定义（Pydantic）
- `utils.py` - 格式化工具函数

### 配置文件
- `metadata.yaml` - 插件元数据（名称、作者、版本等）
- `requirements.txt` - Python 依赖声明
- `_conf_schema.json` - 配置模式定义（WebUI 配置）

### 文档
- `README.md` - 用户使用文档
- `docs/current/overview.md` - 项目概览
- `docs/current/plan.md` - 实施计划
- `docs/current/task.md` - 执行日志
- `docs/current/SUMMARY.md` - 完成总结
- `docs/current/INTERFACE.md` - 接口文档
- `docs/current/TREE.md` - 文件树（本文件）

## 依赖关系

```
main.py
├── api_client.py
│   └── models.py
├── commands.py
│   ├── api_client.py
│   ├── models.py
│   └── utils.py
└── utils.py
    └── models.py
```

## 更新历史

- 2026-03-08T16:02:30+08:00 - 初始创建

