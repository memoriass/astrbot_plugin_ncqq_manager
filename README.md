# AstrBot Plugin: ncqq-manager (NapCat 协议端一键管理与集群对接工具)

这是一个专为 **AstrBot** 打造的高级原生插件。它赋予了大语言模型（LLM）通过自然语言操控和管理远端 [NapCatQQ 容器管理面板] 的能力。

## 🌟 核心特性
1. **🤖 AI 全自动智能运维**
   可以直接在群聊里跟机器人对话：“帮我重启一下测试节点”、“列出所有的机器归属” 或 “调出扫码登录图片”。
2. **🔐 原生艾特鉴权架构**
   依托 AstrBot 原生的组件事件，直接捕获 `@群友` 传递的纯数字 QQ ID，杜绝大模型的名字伪造和越权操作，配合底层 SQLite KV 库永久记住机器的所有者是谁。
3. **⚡ 智能中间件注入雷达 (Injection Engine)**
   无需人工修改配置文件，你可以对 AI 下令：“给 @老李 的机器对接原神”。
   底层的强力雷达会自动推断这台机器是处于 **BS原生中间件集群 (BotShepherd)** 状态还是 **单体 WS 直流状态**，并向目标端口智能发包覆写，实现零延时的多业务热切！
4. **📡 已对接 ncqq-manager SSE / 最近事件感知**
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
