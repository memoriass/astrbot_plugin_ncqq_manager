"""命令处理函数模块"""

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageEventResult

from .models import CreateContainerRequest
from .utils import format_container_info, format_container_list, format_node_list


async def handle_help_command(event: AstrMessageEvent):
    """处理帮助命令"""
    from pathlib import Path
    import astrbot.api.message_components as Comp

    try:
        # 动态导入避免缓存
        plugin_dir = Path(__file__).parent

        # 使用 importlib.util 动态加载配置文件
        import importlib.util
        config_file = plugin_dir / "resources" / "help" / "help_config.py"
        spec = importlib.util.spec_from_file_location("help_config", config_file)
        help_config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(help_config_module)

        HELP_CONFIG = help_config_module.HELP_CONFIG
        HELP_LIST = help_config_module.HELP_LIST

        # 导入渲染器
        from .help_renderer import MiaoHelpRenderer

        # 初始化渲染器
        renderer = MiaoHelpRenderer(plugin_dir / "resources")

        # 渲染图片
        image_bytes = await renderer.render_to_image(HELP_CONFIG, HELP_LIST)

        # 发送图片
        event.set_result(MessageEventResult().message([Comp.Image.fromBytes(image_bytes)]))
    except Exception as e:
        logger.error(f"生成帮助图片失败: {e}")
        event.set_result(MessageEventResult().message(f"❌ 生成帮助图片失败: {str(e)}"))


async def handle_status_command(event: AstrMessageEvent, client, api_url: str):
    """处理状态查询命令"""
    try:
        config = await client.get_cluster_config()

        status_text = f"""🌐 NapCat Manager 状态

📡 连接状态: ✅ 已连接
🔗 API 地址: {api_url}
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


async def handle_list_containers_command(event: AstrMessageEvent, client):
    """处理容器列表查询命令"""
    try:
        containers = await client.list_containers()
        result_text = format_container_list(containers)
        event.set_result(MessageEventResult().message(result_text))
    except Exception as e:
        logger.error(f"获取容器列表失败: {e}")
        event.set_result(MessageEventResult().message(f"❌ 获取容器列表失败: {str(e)}"))


async def handle_container_info_command(
    event: AstrMessageEvent, client, container_name: str
):
    """处理容器详情查询命令"""
    if not container_name:
        event.set_result(
            MessageEventResult().message("❌ 请指定容器名称\n用法: #ncqq详情 <容器名>")
        )
        return

    try:
        container = await client.get_container(container_name)
        if not container:
            event.set_result(
                MessageEventResult().message(f"❌ 容器 {container_name} 不存在")
            )
            return

        result_text = format_container_info(container)
        event.set_result(MessageEventResult().message(result_text))
    except Exception as e:
        logger.error(f"获取容器详情失败: {e}")
        event.set_result(MessageEventResult().message(f"❌ 获取容器详情失败: {str(e)}"))


async def handle_start_container_command(
    event: AstrMessageEvent, client, container_name: str
):
    """处理容器启动命令"""
    if not container_name:
        event.set_result(
            MessageEventResult().message("❌ 请指定容器名称\n用法: #ncqq启动 <容器名>")
        )
        return

    try:
        result = await client.start_container(container_name)
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


async def handle_stop_container_command(
    event: AstrMessageEvent, client, container_name: str
):
    """处理容器停止命令"""
    if not container_name:
        event.set_result(
            MessageEventResult().message("❌ 请指定容器名称\n用法: #ncqq停止 <容器名>")
        )
        return

    try:
        result = await client.stop_container(container_name)
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


async def handle_restart_container_command(
    event: AstrMessageEvent, client, container_name: str
):
    """处理容器重启命令"""
    if not container_name:
        event.set_result(
            MessageEventResult().message("❌ 请指定容器名称\n用法: #ncqq重启 <容器名>")
        )
        return

    try:
        result = await client.restart_container(container_name)
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


async def handle_delete_container_command(
    event: AstrMessageEvent, client, container_name: str
):
    """处理容器删除命令"""
    if not container_name:
        event.set_result(
            MessageEventResult().message("❌ 请指定容器名称\n用法: #ncqq删除 <容器名>")
        )
        return

    try:
        result = await client.delete_container(container_name, delete_data=False)
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


async def handle_create_container_command(
    event: AstrMessageEvent, client, container_name: str
):
    """处理容器创建命令"""
    if not container_name:
        event.set_result(
            MessageEventResult().message("❌ 请指定容器名称\n用法: #ncqq创建 <容器名>")
        )
        return

    try:
        request = CreateContainerRequest(name=container_name)
        result = await client.create_container(request)
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


async def handle_list_nodes_command(event: AstrMessageEvent, client):
    """处理节点列表查询命令"""
    try:
        nodes = await client.list_nodes()
        result_text = format_node_list(nodes)
        event.set_result(MessageEventResult().message(result_text))
    except Exception as e:
        logger.error(f"获取节点列表失败: {e}")
        event.set_result(MessageEventResult().message(f"❌ 获取节点列表失败: {str(e)}"))


async def handle_start_all_containers_command(event: AstrMessageEvent, client):
    """处理批量启动容器命令"""
    try:
        containers = await client.list_containers()
        stopped_containers = [
            c for c in containers if c.status.value in ["stopped", "exited", "created"]
        ]

        if not stopped_containers:
            event.set_result(MessageEventResult().message("📭 没有需要启动的容器"))
            return

        success_count = 0
        fail_count = 0
        messages = [f"🚀 正在启动 {len(stopped_containers)} 个容器...\n"]

        for container in stopped_containers:
            try:
                result = await client.start_container(container.name)
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
        event.set_result(MessageEventResult().message(f"❌ 批量启动容器失败: {str(e)}"))


async def handle_stop_all_containers_command(event: AstrMessageEvent, client):
    """处理批量停止容器命令"""
    try:
        containers = await client.list_containers()
        running_containers = [c for c in containers if c.status.value == "running"]

        if not running_containers:
            event.set_result(MessageEventResult().message("📭 没有需要停止的容器"))
            return

        success_count = 0
        fail_count = 0
        messages = [f"🛑 正在停止 {len(running_containers)} 个容器...\n"]

        for container in running_containers:
            try:
                result = await client.stop_container(container.name)
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
        event.set_result(MessageEventResult().message(f"❌ 批量停止容器失败: {str(e)}"))
