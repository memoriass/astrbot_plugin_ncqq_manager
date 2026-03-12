"""NapCat QQ Manager 插件主类"""

import astrbot.api.star as star
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageEventResult, filter
from astrbot.api.star import Context, Star

from .api_client import NCQQAPIClient
from .models import CreateContainerRequest
from .utils import format_container_info, format_container_list, format_node_list
from .commands import (
    handle_help_command,
    handle_status_command,
    handle_list_containers_command,
    handle_container_info_command,
    handle_start_container_command,
    handle_stop_container_command,
    handle_restart_container_command,
    handle_delete_container_command,
    handle_create_container_command,
    handle_list_nodes_command,
    handle_start_all_containers_command,
    handle_stop_all_containers_command,
)


class Main(Star):
    """NapCat QQ Manager 插件"""

    def __init__(self, context: Context, config: dict):
        super().__init__(context, config)

        # 读取配置
        self.api_url = config.get("api_url", "http://localhost:8000")
        self.api_key = config.get("api_key", "")
        self.timeout = config.get("timeout", 10)
        self.admin_only = config.get("admin_only", True)

        # 初始化 API 客户端
        if self.api_key:
            self.client = NCQQAPIClient(self.api_url, self.api_key, self.timeout)
            logger.info(f"NapCat Manager 插件已加载，API: {self.api_url}")
        else:
            self.client = None
            logger.warning("NapCat Manager 插件未配置 API 密钥")

    def _check_client(self, event: AstrMessageEvent) -> bool:
        """检查客户端是否已初始化"""
        if not self.client:
            event.set_result(
                MessageEventResult().message(
                    "❌ 插件未配置，请先在配置页面设置 API 地址和密钥"
                )
            )
            return False
        return True

    @filter.command("ncqq帮助", "ncqq help")
    async def help_command(self, event: AstrMessageEvent):
        """显示帮助信息"""
        await handle_help_command(event)

    @filter.command("ncqq状态", "ncqq status")
    async def status_command(self, event: AstrMessageEvent):
        """查看连接状态"""
        if not self._check_client(event):
            return
        await handle_status_command(event, self.client, self.api_url)

    @filter.command("ncqq列表", "ncqq list")
    async def list_containers_command(self, event: AstrMessageEvent):
        """查看所有容器"""
        if not self._check_client(event):
            return
        await handle_list_containers_command(event, self.client)

    @filter.command("ncqq详情", "ncqq info")
    async def container_info_command(
        self, event: AstrMessageEvent, container_name: str = ""
    ):
        """查看容器详情"""
        if not self._check_client(event):
            return
        await handle_container_info_command(event, self.client, container_name)

    @filter.command("ncqq启动", "ncqq start")
    async def start_container_command(
        self, event: AstrMessageEvent, container_name: str = ""
    ):
        """启动容器"""
        if not self._check_client(event):
            return
        await handle_start_container_command(event, self.client, container_name)

    @filter.command("ncqq停止", "ncqq stop")
    async def stop_container_command(
        self, event: AstrMessageEvent, container_name: str = ""
    ):
        """停止容器"""
        if not self._check_client(event):
            return
        await handle_stop_container_command(event, self.client, container_name)

    @filter.command("ncqq重启", "ncqq restart")
    async def restart_container_command(
        self, event: AstrMessageEvent, container_name: str = ""
    ):
        """重启容器"""
        if not self._check_client(event):
            return
        await handle_restart_container_command(event, self.client, container_name)

    @filter.command("ncqq删除", "ncqq delete")
    async def delete_container_command(
        self, event: AstrMessageEvent, container_name: str = ""
    ):
        """删除容器"""
        if not self._check_client(event):
            return
        await handle_delete_container_command(event, self.client, container_name)

    @filter.command("ncqq创建", "ncqq create")
    async def create_container_command(
        self, event: AstrMessageEvent, container_name: str = ""
    ):
        """创建新容器"""
        if not self._check_client(event):
            return
        await handle_create_container_command(event, self.client, container_name)

    @filter.command("ncqq节点列表", "ncqq nodes")
    async def list_nodes_command(self, event: AstrMessageEvent):
        """查看所有节点"""
        if not self._check_client(event):
            return
        await handle_list_nodes_command(event, self.client)

    @filter.command("ncqq全部启动", "ncqq startall")
    async def start_all_containers_command(self, event: AstrMessageEvent):
        """启动所有已停止的容器"""
        if not self._check_client(event):
            return
        await handle_start_all_containers_command(event, self.client)

    @filter.command("ncqq全部停止", "ncqq stopall")
    async def stop_all_containers_command(self, event: AstrMessageEvent):
        """停止所有运行中的容器"""
        if not self._check_client(event):
            return
        await handle_stop_all_containers_command(event, self.client)

    @filter.command("ncqq二维码", "ncqq qrcode")
    async def qrcode_command(self, event: AstrMessageEvent, container_name: str = ""):
        """获取容器登录二维码"""
        if not self._check_client(event):
            return

        if not container_name:
            event.set_result(
                MessageEventResult().message(
                    "❌ 请指定容器名称\n用法: ncqq二维码 <容器名>"
                )
            )
            return

        try:
            result = await self.client.get_qrcode(container_name)
            if result.get("status") == "ok":
                qr_url = result.get("url", "")
                qr_type = result.get("type", "unknown")

                if qr_url:
                    # 返回二维码图片
                    from astrbot.api.message_components import Image

                    event.set_result(
                        MessageEventResult().message(
                            [
                                f"📱 容器 {container_name} 登录二维码\n",
                                f"类型: {qr_type}\n",
                                Image.fromURL(qr_url)
                                if qr_url.startswith("http")
                                else Image.fromBase64(qr_url),
                            ]
                        )
                    )
                else:
                    event.set_result(
                        MessageEventResult().message(
                            f"❌ 容器 {container_name} 暂无二维码"
                        )
                    )
            elif result.get("status") == "waiting":
                event.set_result(
                    MessageEventResult().message(
                        f"⏳ 容器 {container_name} 正在等待登录\n请稍后再试"
                    )
                )
            else:
                event.set_result(
                    MessageEventResult().message(
                        f"❌ 获取二维码失败: {result.get('message', '未知错误')}"
                    )
                )
        except Exception as e:
            logger.error(f"获取二维码失败: {e}")
            event.set_result(
                MessageEventResult().message(f"❌ 获取二维码失败: {str(e)}")
            )

    @filter.command("ncqq帮助")
    async def help_command(self, event: AstrMessageEvent):
        """显示帮助信息"""
        help_text = """📖 NapCat QQ Manager 插件帮助

🔧 基础配置
  #ncqq状态 - 查看连接状态
  #ncqq帮助 - 显示此帮助

💻 容器管理
  #ncqq列表 - 查看所有容器
  #ncqq详情 <容器名> - 查看容器详情
  #ncqq创建 <容器名> - 创建新容器
  #ncqq启动 <容器名> - 启动容器
  #ncqq停止 <容器名> - 停止容器
  #ncqq重启 <容器名> - 重启容器
  #ncqq删除 <容器名> - 删除容器（需管理员）

🌐 节点管理
  #ncqq节点列表 - 查看所有节点

⚠️ 注意：删除操作不可逆，请谨慎使用"""

        event.set_result(MessageEventResult().message(help_text))

    @filter.command("ncqq状态")
    async def status_command(self, event: AstrMessageEvent):
        """查看连接状态"""
        if not self._check_client(event):
            return

        try:
            config = await self.client.get_cluster_config()

            status_text = f"""🌐 NapCat Manager 状态

📡 连接状态: ✅ 已连接
🔗 API 地址: {self.api_url}
🐳 Docker 镜像: {config.docker_image}
📁 数据目录: {config.data_dir}

💻 系统信息
  CPU 使用率: {config.system.cpu_percent:.1f}%
  内存使用率: {config.system.mem_percent:.1f}%
  平台: {config.system.platform}
  Python 版本: {config.system.python_version}

🔌 端口配置
  WebUI 基础端口: {config.webui_base_port}
  HTTP 基础端口: {config.http_base_port}
  WebSocket 基础端口: {config.ws_base_port}"""

            event.set_result(MessageEventResult().message(status_text))
        except Exception as e:
            logger.error(f"获取状态失败: {e}")
            event.set_result(MessageEventResult().message(f"❌ 获取状态失败: {str(e)}"))

    @filter.command("ncqq列表")
    async def list_containers_command(self, event: AstrMessageEvent):
        """查看所有容器"""
        if not self._check_client(event):
            return

        try:
            containers = await self.client.list_containers()
            result_text = format_container_list(containers)
            event.set_result(MessageEventResult().message(result_text))
        except Exception as e:
            logger.error(f"获取容器列表失败: {e}")
            event.set_result(
                MessageEventResult().message(f"❌ 获取容器列表失败: {str(e)}")
            )

    @filter.command("ncqq详情")
    async def container_info_command(
        self, event: AstrMessageEvent, container_name: str = ""
    ):
        """查看容器详情"""
        if not self._check_client(event):
            return

        if not container_name:
            event.set_result(
                MessageEventResult().message(
                    "❌ 请指定容器名称\n用法: #ncqq详情 <容器名>"
                )
            )
            return

        try:
            container = await self.client.get_container(container_name)
            if not container:
                event.set_result(
                    MessageEventResult().message(f"❌ 容器 {container_name} 不存在")
                )
                return

            result_text = format_container_info(container)
            event.set_result(MessageEventResult().message(result_text))
        except Exception as e:
            logger.error(f"获取容器详情失败: {e}")
            event.set_result(
                MessageEventResult().message(f"❌ 获取容器详情失败: {str(e)}")
            )

    @filter.command("ncqq启动")
    async def start_container_command(
        self, event: AstrMessageEvent, container_name: str = ""
    ):
        """启动容器"""
        if not self._check_client(event):
            return

        if not container_name:
            event.set_result(
                MessageEventResult().message(
                    "❌ 请指定容器名称\n用法: #ncqq启动 <容器名>"
                )
            )
            return

        try:
            result = await self.client.start_container(container_name)
            if result.get("status") == "ok":
                event.set_result(
                    MessageEventResult().message(f"✅ 容器 {container_name} 启动成功")
                )
            else:
                event.set_result(
                    MessageEventResult().message(
                        f"❌ 容器 {container_name} 启动失败: {result.get('message', '未知错误')}"
                    )
                )
        except Exception as e:
            logger.error(f"启动容器失败: {e}")
            event.set_result(MessageEventResult().message(f"❌ 启动容器失败: {str(e)}"))

    @filter.command("ncqq停止")
    async def stop_container_command(
        self, event: AstrMessageEvent, container_name: str = ""
    ):
        """停止容器"""
        if not self._check_client(event):
            return

        if not container_name:
            event.set_result(
                MessageEventResult().message(
                    "❌ 请指定容器名称\n用法: #ncqq停止 <容器名>"
                )
            )
            return

        try:
            result = await self.client.stop_container(container_name)
            if result.get("status") == "ok":
                event.set_result(
                    MessageEventResult().message(f"✅ 容器 {container_name} 停止成功")
                )
            else:
                event.set_result(
                    MessageEventResult().message(
                        f"❌ 容器 {container_name} 停止失败: {result.get('message', '未知错误')}"
                    )
                )
        except Exception as e:
            logger.error(f"停止容器失败: {e}")
            event.set_result(MessageEventResult().message(f"❌ 停止容器失败: {str(e)}"))

    @filter.command("ncqq重启")
    async def restart_container_command(
        self, event: AstrMessageEvent, container_name: str = ""
    ):
        """重启容器"""
        if not self._check_client(event):
            return

        if not container_name:
            event.set_result(
                MessageEventResult().message(
                    "❌ 请指定容器名称\n用法: #ncqq重启 <容器名>"
                )
            )
            return

        try:
            result = await self.client.restart_container(container_name)
            if result.get("status") == "ok":
                event.set_result(
                    MessageEventResult().message(f"✅ 容器 {container_name} 重启成功")
                )
            else:
                event.set_result(
                    MessageEventResult().message(
                        f"❌ 容器 {container_name} 重启失败: {result.get('message', '未知错误')}"
                    )
                )
        except Exception as e:
            logger.error(f"重启容器失败: {e}")
            event.set_result(MessageEventResult().message(f"❌ 重启容器失败: {str(e)}"))

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("ncqq删除")
    async def delete_container_command(
        self, event: AstrMessageEvent, container_name: str = ""
    ):
        """删除容器"""
        if not self._check_client(event):
            return

        if not container_name:
            event.set_result(
                MessageEventResult().message(
                    "❌ 请指定容器名称\n用法: #ncqq删除 <容器名>"
                )
            )
            return

        try:
            result = await self.client.delete_container(
                container_name, delete_data=False
            )
            if result.get("status") == "ok":
                event.set_result(
                    MessageEventResult().message(
                        f"✅ 容器 {container_name} 删除成功\n⚠️ 注意：容器数据已保留"
                    )
                )
            else:
                event.set_result(
                    MessageEventResult().message(
                        f"❌ 容器 {container_name} 删除失败: {result.get('message', '未知错误')}"
                    )
                )
        except Exception as e:
            logger.error(f"删除容器失败: {e}")
            event.set_result(MessageEventResult().message(f"❌ 删除容器失败: {str(e)}"))

    @filter.command("ncqq创建")
    @filter.command("ncqq创建")
    async def create_container_command(
        self, event: AstrMessageEvent, container_name: str = ""
    ):
        """创建新容器"""
        if not self._check_client(event):
            return

        if not container_name:
            event.set_result(
                MessageEventResult().message(
                    "❌ 请指定容器名称\n用法: #ncqq创建 <容器名>"
                )
            )
            return

        try:
            request = CreateContainerRequest(name=container_name)
            result = await self.client.create_container(request)
            if result.get("status") == "ok":
                container_info = result.get("container", {})
                webui_port = container_info.get("webui_port", "未分配")
                message = f"""✅ 容器 {container_name} 创建成功

📦 容器信息：
  名称: {container_name}
  WebUI端口: {webui_port}
  状态: 已创建

💡 提示：使用 #ncqq启动 {container_name} 启动容器"""
                event.set_result(MessageEventResult().message(message))
            else:
                event.set_result(
                    MessageEventResult().message(
                        f"❌ 容器 {container_name} 创建失败: {result.get('message', '未知错误')}"
                    )
                )
        except Exception as e:
            logger.error(f"创建容器失败: {e}")
            event.set_result(MessageEventResult().message(f"❌ 创建容器失败: {str(e)}"))

    @filter.command("ncqq节点列表")
    async def list_nodes_command(self, event: AstrMessageEvent):
        """查看所有节点"""
        if not self._check_client(event):
            return

        try:
            nodes = await self.client.list_nodes()
            result_text = format_node_list(nodes)
            event.set_result(MessageEventResult().message(result_text))
        except Exception as e:
            logger.error(f"获取节点列表失败: {e}")
            event.set_result(
                MessageEventResult().message(f"❌ 获取节点列表失败: {str(e)}")
            )

    @filter.command("ncqq全部启动")
    async def start_all_containers_command(self, event: AstrMessageEvent):
        """启动所有已停止的容器"""
        if not self._check_client(event):
            return

        try:
            containers = await self.client.list_containers()
            stopped_containers = [
                c
                for c in containers
                if c.status.value in ["stopped", "exited", "created"]
            ]

            if not stopped_containers:
                event.set_result(MessageEventResult().message("📭 没有需要启动的容器"))
                return

            success_count = 0
            fail_count = 0
            messages = [f"🚀 正在启动 {len(stopped_containers)} 个容器...\n"]

            for container in stopped_containers:
                try:
                    result = await self.client.start_container(container.name)
                    if result.get("status") == "ok":
                        success_count += 1
                        messages.append(f"✅ {container.name}")
                    else:
                        fail_count += 1
                        messages.append(
                            f"❌ {container.name}: {result.get('message', '未知错误')}"
                        )
                except Exception as e:
                    fail_count += 1
                    messages.append(f"❌ {container.name}: {str(e)}")

            messages.append(f"\n📊 结果：成功 {success_count} 个，失败 {fail_count} 个")
            event.set_result(MessageEventResult().message("\n".join(messages)))
        except Exception as e:
            logger.error(f"批量启动容器失败: {e}")
            event.set_result(
                MessageEventResult().message(f"❌ 批量启动容器失败: {str(e)}")
            )

    @filter.command("ncqq全部停止")
    async def stop_all_containers_command(self, event: AstrMessageEvent):
        """停止所有运行中的容器"""
        if not self._check_client(event):
            return

        try:
            containers = await self.client.list_containers()
            running_containers = [c for c in containers if c.status.value == "running"]

            if not running_containers:
                event.set_result(MessageEventResult().message("📭 没有需要停止的容器"))
                return

            success_count = 0
            fail_count = 0
            messages = [f"🛑 正在停止 {len(running_containers)} 个容器...\n"]

            for container in running_containers:
                try:
                    result = await self.client.stop_container(container.name)
                    if result.get("status") == "ok":
                        success_count += 1
                        messages.append(f"✅ {container.name}")
                    else:
                        fail_count += 1
                        messages.append(
                            f"❌ {container.name}: {result.get('message', '未知错误')}"
                        )
                except Exception as e:
                    fail_count += 1
                    messages.append(f"❌ {container.name}: {str(e)}")

            messages.append(f"\n📊 结果：成功 {success_count} 个，失败 {fail_count} 个")
            event.set_result(MessageEventResult().message("\n".join(messages)))
        except Exception as e:
            logger.error(f"批量停止容器失败: {e}")
            event.set_result(
                MessageEventResult().message(f"❌ 批量停止容器失败: {str(e)}")
            )
