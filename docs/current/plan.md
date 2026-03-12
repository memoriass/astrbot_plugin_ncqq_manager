# NapCat QQ Manager 插件 - 实施计划

## 受影响文件清单

| 文件路径 | 类/函数 | 行号范围 | 预估变更 | 说明 |
|---------|---------|---------|---------|------|
| `main.py` | `Main` | L1-L320 | +320 | 插件主类，命令处理 |
| `api_client.py` | `NCQQAPIClient` | L1-L200 | +195 | API 客户端封装 |
| `models.py` | `Container/Node` | L1-L100 | +80 | 数据模型 |
| `utils.py` | `format_*` | L1-L100 | +85 | 格式化工具 |
| `__init__.py` | - | L1-L10 | +6 | 包初始化 |
| `metadata.yaml` | - | L1-L10 | +6 | 插件元数据 |
| `README.md` | - | L1-L100 | +85 | 使用文档 |
| `requirements.txt` | - | L1-L5 | +2 | 依赖声明 |
| `_conf_schema.json` | - | L1-L30 | +28 | 配置模式 |

## 实施步骤

### Phase 1: 基础结构 ✅
1. 创建插件目录结构
2. 编写 `metadata.yaml`（6 行）
3. 编写 `requirements.txt`（2 行）
4. 编写 `_conf_schema.json`（28 行）
5. 编写 `README.md`（85 行）

**检查点**: 文件存在性验证
**回滚**: `rm -rf data/plugins/astrbot_plugin_ncqq_manager`

### Phase 2: 数据模型与工具 ✅
1. 创建 `models.py`（80 行）
2. 创建 `utils.py`（85 行）

**检查点**: `ruff format && ruff check`
**回滚**: `git restore models.py utils.py`

### Phase 3: API 客户端 ✅
1. 创建 `api_client.py`（195 行）

**检查点**: `ruff format && ruff check && mypy api_client.py`
**回滚**: `git restore api_client.py`

### Phase 4: 主插件类 ✅
1. 创建 `main.py`（320 行）
2. 添加权限检查
3. 添加容器创建功能

**检查点**: `ruff format && ruff check`
**回滚**: `git restore main.py`

### Phase 5: 完善与优化 ✅
1. 添加 `__init__.py`（6 行）
2. 添加权限检查方法
3. 添加容器创建命令
4. 优化帮助信息

**检查点**: 所有 gates 通过
**回滚**: `git reset --hard HEAD~1`

## 验收 KPI

- [x] 编译警告 = 0
- [x] Lint 违规 = 0
- [x] 日志超限 = 0（每文件 ≤5）
- [x] 硬编码 = 0
- [x] Δ行数偏差 ≤20%
- [x] 文件行数：main.py ≤320, api_client.py ≤200, 其他 ≤100
- [x] codebase-retrieval 命中 ≥3
- [x] remeber 条目 ≥15（5 阶段 × 3）

## 接口签名

### 基础配置
- `#ncqq帮助` → 显示帮助信息
- `#ncqq状态` → 查看连接状态和系统信息

### 容器管理
- `#ncqq列表` → 查看所有容器
- `#ncqq详情 <容器名>` → 查看容器详情
- `#ncqq创建 <容器名>` → 创建新容器
- `#ncqq启动 <容器名>` → 启动容器
- `#ncqq停止 <容器名>` → 停止容器
- `#ncqq重启 <容器名>` → 重启容器
- `#ncqq删除 <容器名>` → 删除容器（需管理员权限）

### 节点管理
- `#ncqq节点列表` → 查看所有节点

## 错误处理策略

1. API 连接失败 → 返回友好提示，记录日志
2. 权限不足 → 提示需要管理员权限
3. 容器不存在 → 提示容器名称错误
4. 参数错误 → 返回命令使用说明

## 回滚触发条件

- 插件加载失败
- API 调用成功率 <50%
- 命令响应时间 >5s
- 内存泄漏或异常崩溃

## 回滚命令

```bash
# 禁用插件
/plugin off ncqq_manager

# 删除插件
rm -rf data/plugins/astrbot_plugin_ncqq_manager

# Git 回滚
git restore data/plugins/astrbot_plugin_ncqq_manager
```

## Updated
2026-03-08T15:40:00+08:00

