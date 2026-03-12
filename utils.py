"""格式化工具函数"""

from typing import List
from .models import Container, Node, ContainerStatus


def format_status(status: ContainerStatus) -> str:
    """格式化容器状态为中文"""
    status_map = {
        ContainerStatus.RUNNING: "🟢 运行中",
        ContainerStatus.STOPPED: "🔴 已停止",
        ContainerStatus.PAUSED: "⏸️ 已暂停",
        ContainerStatus.RESTARTING: "🔄 重启中",
        ContainerStatus.REMOVING: "🗑️ 删除中",
        ContainerStatus.EXITED: "⚫ 已退出",
        ContainerStatus.DEAD: "💀 已死亡",
        ContainerStatus.CREATED: "🆕 已创建",
        ContainerStatus.UNKNOWN: "❓ 未知",
    }
    return status_map.get(status, "❓ 未知")


def format_container_info(container: Container) -> str:
    """格式化单个容器详细信息"""
    lines = [
        f"📦 容器名称: {container.name}",
        f"🆔 容器ID: {container.id[:12]}",
        f"📊 状态: {format_status(container.status)}",
        f"🌐 节点: {container.node_id}",
    ]

    if container.uin:
        lines.append(f"👤 QQ号: {container.uin}")

    if container.webui_port:
        lines.append(f"🖥️ WebUI端口: {container.webui_port}")

    if container.http_port:
        lines.append(f"🌐 HTTP端口: {container.http_port}")

    if container.ws_port:
        lines.append(f"🔌 WebSocket端口: {container.ws_port}")

    if container.created_at:
        lines.append(f"📅 创建时间: {container.created_at}")

    return "\n".join(lines)


def format_container_list(containers: List[Container]) -> str:
    """格式化容器列表"""
    if not containers:
        return "📭 暂无容器"

    lines = [f"📦 容器列表 (共 {len(containers)} 个)\n"]

    for i, container in enumerate(containers, 1):
        status = format_status(container.status)
        uin_info = f" | QQ: {container.uin}" if container.uin else ""
        lines.append(f"{i}. {container.name} - {status}{uin_info}")

    return "\n".join(lines)


def format_node_list(nodes: List[Node]) -> str:
    """格式化节点列表"""
    if not nodes:
        return "📭 暂无节点"

    lines = [f"🌐 节点列表 (共 {len(nodes)} 个)\n"]

    for i, node in enumerate(nodes, 1):
        lines.append(
            f"{i}. {node.name} ({node.node_id})\n"
            f"   地址: {node.address}\n"
            f"   状态: {node.status}\n"
            f"   CPU: {node.cpu_percent:.1f}% | 内存: {node.mem_percent:.1f}%\n"
            f"   容器数: {node.container_count}"
        )


    return "\n".join(lines)

async def generate_help_image() -> str:
    """生成并返回帮助图片的本地路径"""
    try:
        from html2image import Html2Image
        import os
        import tempfile

        # 确定资源路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        help_dir = os.path.join(current_dir, "resources", "help")
        html_path = os.path.join(help_dir, "index.html")
        css_path = os.path.join(help_dir, "style.css")

        # 创建临时输出目录
        output_dir = tempfile.gettempdir()
        output_file = os.path.join(output_dir, "ncqq_help_image.png")

        # 使用 html2image 渲染
        hti = Html2Image(output_path=output_dir, size=(600, 1000))
        hti.screenshot(html_file=html_path, css_file=css_path, save_as="ncqq_help_image.png")

        return output_file
    except ImportError:
        logger.error("未安装 html2image，无法生成帮助图片。请使用 pip install html2image")
        raise Exception("请先运行 pip install html2image 并在系统中安装 Chrome/Edge 浏览器。")
    except Exception as e:
        logger.error(f"生成帮助图片失败: {e}")
        raise e
