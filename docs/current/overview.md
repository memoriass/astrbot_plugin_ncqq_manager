# NapCat QQ Manager 插件 - 概览

## 项目目标
为 AstrBot 创建一个插件，对接 ncqq-manager（NapCat QQ 容器管理系统），实现通过 QQ 消息管理 NapCat 容器的功能。

## 功能范围
基于 mcsmanager-plugin 的功能逻辑，移植以下核心功能：
1. 容器管理（创建、启动、停止、重启、删除）
2. 容器状态查询
3. 容器列表展示
4. 节点管理
5. 用户权限管理

## 技术栈
- AstrBot 插件框架（Python）
- ncqq-manager API（FastAPI）
- HTTP 请求（aiohttp）

## KPI 指标
- 命令响应时间 < 3s
- API 调用成功率 > 95%
- 日志记录 ≤ 5 条/文件
- 代码行数 < 500 行/文件

## 回滚策略
如果插件加载失败或 API 连接异常：
```bash
# 禁用插件
/plugin off ncqq_manager

# 或删除插件目录
rm -rf data/plugins/astrbot_plugin_ncqq_manager
```

## 更新时间
Created: 2025-03-07T00:00:00Z
Updated: 2025-03-07T00:00:00Z

