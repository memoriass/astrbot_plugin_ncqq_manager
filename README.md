# AstrBot Plugin: ncqq-manager (NapCat 协议端一键管理与集群对接工具)

这是一个专为 **AstrBot** 打造的高级原生插件。它赋予了大语言模型（LLM）通过自然语言操控和管理远端 [NapCatQQ 容器管理面板] 的能力。

维护和接手请先看 [架构说明](docs/architecture.md)、[模块结构说明](docs/module-map.md) 与 [插件合规检查](docs/plugin-compliance.md)。

## 🌟 核心特性
1. **🤖 AI 全自动智能运维**
   可以直接在群聊里跟机器人对话：“帮我重启一下测试节点”、“列出所有的机器归属” 或 “调出扫码登录图片”。
2. **🔐 原生艾特鉴权架构**
   依托 AstrBot 原生的组件事件，直接捕获 `@群友` 传递的纯数字 QQ ID，杜绝大模型的名字伪造和越权操作，配合底层 SQLite KV 库永久记住机器的所有者是谁。
3. **⚡ 智能中间件注入雷达 (Injection Engine)**
   无需人工修改配置文件，你可以对 AI 下令：“给 @老李 的机器对接原神”。
   底层的强力雷达会自动推断这台机器是处于 **BS原生中间件集群 (BotShepherd)** 状态还是 **单体 WS 直流状态**，并向目标端口智能发包覆写，实现零延时的多业务热切！4. **📡 已对接 ncqq-manager SSE / 最近事件感知**
   监控信息会读取 `/api/containers/{name}/stats` 返回的 `last_event`，展示最近一次容器生命周期事件；执行 start/stop/restart/delete 等动作后，插件会短暂订阅 `/api/containers/{name}/events` 进行 SSE 确认，无需常驻长连接。

## 🎯 交互方式

本插件提供 **两种互补** 的交互方式：

### 方式一：固定命令（确定性触发，零延迟）

通过 AstrBot 唤醒前缀 + `ncqq` 命令使用。前缀由 AstrBot 配置项 `wake_prefix` 动态决定（如 `plana`）：

| 命令 | 说明 | 权限 |
|------|------|------|
| `ncqq list` | 列出所有实例及运行状态 | 所有人 |
| `ncqq login [名称]` | 查看实例登录状态 | 所有人 |
| `ncqq qrcode [名称]` | 获取登录二维码图片 | 所有人 |
| `ncqq start\|stop\|restart [名称]` | 生命周期管理 | 所有人 |
| `ncqq pause\|unpause [名称]` | 暂停/恢复实例 | 所有人 |
| `ncqq kill [名称]` | 强杀实例 | 所有人 |
| `ncqq create <名称>` | 创建新实例（逗号分隔多个） | 管理员 / 审批 |
| `ncqq delete [名称] [purge]` | 销毁实例（`purge` 彻底删数据） | 管理员 / 审批 |
| `ncqq switch [名称]` | 重置登录账号（保留配置） | 管理员 / 审批 |
| `ncqq monitor [名称]` | 查看 CPU/内存/网络占用 | 管理员 |
| `ncqq logs [名称]` | 查看容器尾部日志 | 管理员 |
| `ncqq config [名称] [文件名]` | 读取容器内配置文件 | 管理员 |
| `ncqq files [名称] [路径]` | 列出实例文件目录 | 管理员 |
| `ncqq assets` | 查看镜像与节点资产 | 管理员 |
| `ncqq bind <实例名>` | 绑定实例到 @目标用户 | 管理员 / 审批 |
| `ncqq unbind <实例名>` | 解绑实例（需 @目标用户） | 管理员 |
| `ncqq bindings` | 查看所有绑定关系 | 所有人 |
| `ncqq nick <QQ号> <昵称>` | 设置用户展示昵称 | 管理员 |
| `ncqq backend add <别名> <地址>` | 添加后端端点模板 | 管理员 / 审批 |
| `ncqq backend remove <别名>` | 删除后端端点 | 管理员 / 审批 |
| `ncqq backend inject <别名>` | 注入后端到实例 | 管理员 / 审批 |
| `ncqq approvals` | 查看所有待审批请求 | 管理员 |
| `ncqq approve <ID>` | 批准审批请求 | 管理员 |
| `ncqq reject <ID> [原因]` | 拒绝审批请求 | 管理员 |
| `ncqq help` | 显示命令帮助 | 所有人 |

> **智能省略**：当用户只绑定了 1 个实例时，`[名称]` 参数可省略，系统自动使用唯一绑定实例。绑定多个时需指定名称。

### 方式二：自然语言（LLM 驱动）

插件注册了一个精简的 LLM 工具 `ncqq_manager`，当对话中提及以下关键词时自动触发：

**ncqq** / **NapCat** / **QQ机器人** / **机器人实例** / **bot实例** / **容器实例**

示例：
- `帮我重启一下机器人实例` → 自动执行 restart（单绑定时自动推断实例名）
- `看看 ncqq 都有哪些机器在线` → 列出所有实例
- `给我的 QQ机器人 拉个登录码` → 获取二维码

> ⚠️ 仅涉及上述关键词的对话才会触发，普通聊天、系统状态查询、其他插件功能不受影响。

## ⚙️ 安装与配置
1. 将本文件夹完整放至 `AstrBot/data/plugins/` 目录中。
2. 启动 AstrBot。
3. 进入 **AstrBot 管理端 (WebUI)** → **插件配置**，找到 `ncqq-manager`：
   * `manager_url`：填写管理面板后端地址（如 `http://admin.com:8080`）。
   * `api_key`：填写对应的防刷鉴权令牌。

## 📜 协议 (License)
本项目遵守 **GNU General Public License v3.0 (GPL-3.0)** 协议。4. **📡 已对接 ncqq-manager SSE / 最近事件感知**
   监控信息会读取 `/api/containers/{name}/stats` 返回的 `last_event`，展示最近一次容器生命周期事件；执行 start/stop/restart/delete 等动作后，插件会短暂订阅 `/api/containers/{name}/events` 进行 SSE 确认，无需常驻长连接。

## ⚙️ 安装与配置
1. 将本文件夹完整放至 `AstrBot/data/plugins/` 目录中。
2. 启动 AstrBot。
3. 进入 **AstrBot 管理端 (WebUI)** -> **插件配置**，找到 `ncqq-manager`：
   * `manager_url`: 填写你的管理面板后端地址（如 `http://admin.com:8080`）
   * `api_key`: 填写对应的防刷鉴权令牌。
4. **编辑可用接口**: 
   你可以直接在当前目录下的 `backends.json` 文件中增加你常玩或自建的后端地址作为“模板”（如原神、各个游戏查水表机器人），大模型后续能够根据此表完成对接寻址。

## 📜 协议 (License)
本项目遵守 **GNU General Public License v3.0 (GPL-3.0)** 协议，享受自由分发与引用的权利。
