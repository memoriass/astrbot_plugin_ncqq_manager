"""Miao-Plugin 风格帮助渲染器 - NCQQ Manager 插件

此模块提供与 miao-plugin 相同风格的帮助图片渲染功能。
"""

import base64
from pathlib import Path
from typing import Dict, List, Any
from jinja2 import Template

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class MiaoHelpRenderer:
    """Miao-Plugin 风格帮助渲染器"""
    
    def __init__(self, resources_dir: Path):
        """
        初始化渲染器
        
        Args:
            resources_dir: 资源目录路径（包含 help 子目录）
        """
        self.resources_dir = resources_dir
        self.help_dir = resources_dir / "help"
        
        # 检查必要文件
        self.template_path = self.help_dir / "index_miao.html"
        self.bg_image = self.help_dir / "bg.jpg"
        self.main_image = self.help_dir / "main.png"
        self.icon_image = self.help_dir / "icon.png"
        
        if not self.template_path.exists():
            raise FileNotFoundError(f"模板文件不存在: {self.template_path}")
    
    def _calculate_icon_css(self, icon_num: int) -> str:
        """
        计算图标的 CSS background-position
        
        Args:
            icon_num: 图标编号（1-100）
            
        Returns:
            CSS 样式字符串
        """
        if not icon_num or icon_num <= 0:
            return "display:none"
        
        # 图标精灵图：10列，每个图标 50x50px
        x = (icon_num - 1) % 10
        y = (icon_num - x - 1) // 10
        return f"background-position:-{x * 50}px -{y * 50}px"
    
    def _prepare_help_data(self, config: Dict[str, Any], help_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        准备渲染数据
        
        Args:
            config: 帮助配置
            help_list: 帮助列表
            
        Returns:
            渲染数据字典
        """
        # 处理图标 CSS
        for group in help_list:
            if "list" in group:
                for item in group["list"]:
                    icon = item.get("icon", 0)
                    item["css"] = self._calculate_icon_css(icon)
        
        # 计算列宽百分比
        col_count = config.get("colCount", 3)
        col_width = 100 / col_count
        
        # 转换图片为 base64（用于嵌入 HTML）
        def image_to_base64(image_path: Path) -> str:
            if image_path.exists():
                with open(image_path, "rb") as f:
                    return f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
            return ""
        
        return {
            "title": config.get("title", "帮助"),
            "subtitle": config.get("subTitle", ""),
            "groups": help_list,
            "col_count": col_count,
            "col_width": col_width,
            "bg_image": image_to_base64(self.bg_image),
            "main_image": image_to_base64(self.main_image),
            "icon_image": image_to_base64(self.icon_image)
        }
    
    async def render_to_image(self, config: Dict[str, Any], help_list: List[Dict[str, Any]]) -> bytes:
        """
        渲染帮助为图片
        
        Args:
            config: 帮助配置
            help_list: 帮助列表
            
        Returns:
            PNG 图片字节数据
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright 未安装，无法渲染图片。请运行: pip install playwright && playwright install chromium")
        
        # 准备数据
        data = self._prepare_help_data(config, help_list)
        
        # 读取模板
        with open(self.template_path, "r", encoding="utf-8") as f:
            template_content = f.read()
        
        # 渲染 HTML
        template = Template(template_content)
        html = template.render(**data)
        
        # 使用 Playwright 渲染为图片
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": 830, "height": 1400})
            
            await page.set_content(html)
            
            # 等待渲染完成
            await page.wait_for_load_state("networkidle")
            
            # 截图
            screenshot = await page.screenshot(full_page=True, type="png")
            
            await browser.close()
            
            return screenshot

