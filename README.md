# NapCat QQ Manager 插件

# NapCat QQ Manager 说明

`astrbot_plugin_ncqq_manager` 是一个 `AstrBot` 的扩展插件，提供强大的 NapCat QQ 容器管理功能。

具体功能可在安装插件后通过 `ncqq帮助` 进行查看。包含容器创建、启动、停止、重启、删除，以及二维码获取等功能。

---

## 安装与更新

### 使用 Git 安装（推荐）

请将本插件放置在 AstrBot 的 `data/plugins/` 目录下，安装依赖后重启 AstrBot 即可使用。
在 AstrBot 根目录下打开终端，运行下述指令：

```bash
cd data/plugins/
git clone https://github.com/your-repo/astrbot_plugin_ncqq_manager.git
cd astrbot_plugin_ncqq_manager
pip install -r requirements.txt
```

### 手工下载安装

手工下载安装包，解压后将文件夹重命名为 `astrbot_plugin_ncqq_manager`，然后放置在 AstrBot 的 `data/plugins/` 目录内，并安装 `requirements.txt` 中的依赖。

---

## AstrBot 版本与支持

`astrbot_plugin_ncqq_manager` 支持最新版本的 AstrBot。
需要配合 `ncqq-manager` 服务端使用。

---

## 配置说明

在 AstrBot 的插件配置页面配置以下参数：

- **API 地址**: ncqq-manager 服务器地址（例如：`http://localhost:8000`）
- **API 密钥**: ncqq-manager 的 API 密钥（需要管理员权限）
- **请求超时时间**: API 请求超时时间（秒），默认 10 秒
- **仅管理员可用**: 是否仅允许管理员使用此插件，默认为 true

---

## 功能说明

> **注意**：命令前缀由 AstrBot 配置决定。如果 AstrBot 配置了命令前缀（如 `#`），则需要在命令前添加前缀（如 `#ncqq状态`）。以下示例不包含前缀。

### #ncqq状态 & #ncqq帮助
使用指令 `ncqq帮助` 可以查看所有可用命令的详细说明。
使用指令 `ncqq状态` 查看当前连接状态和系统信息。

### #容器管理
包含一系列容器操作：
- `ncqq列表`：查看所有容器
- `ncqq详情 <容器名>`：查看容器详细信息
- `ncqq创建 <容器名>`：创建新容器
- `ncqq启动/停止/重启/删除 <容器名>`：操作指定容器
- `ncqq全部启动/全部停止`：批量操作容器

### #登录管理
`ncqq二维码 <容器名>`：获取指定容器的登录二维码图片。

### #节点管理
`ncqq节点列表`：查看所有后端节点状态。

---

## 免责声明

1. `astrbot_plugin_ncqq_manager` 自身的 UI 与代码均开放，无需征得特殊同意，可任意使用。
2. 请尊重 AstrBot 本体及其他插件作者的努力，妥善保管你的 API 密钥。删除容器操作不可逆，请谨慎使用。

# 资源

- [ncqq-manager](https://github.com/your-repo/ncqq-manager) - NapCat QQ 容器管理系统后端
- [AstrBot](https://github.com/Soulter/AstrBot) - 多平台 LLM 聊天机器人

# 其他&感谢

- 感谢 AstrBot 提供的强大且易用的插件框架。
- 感谢 NapCat QQ 提供的优秀无头 QQ 客户端实现。

