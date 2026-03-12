"""动态命令提取器 - 从插件代码中自动提取命令列表

此模块用于从 AstrBot 插件代码中自动提取 @filter.command 装饰器定义的命令。
"""

import ast
import inspect
from pathlib import Path
from typing import List, Dict, Any, Optional


class CommandExtractor:
    """命令提取器 - 从插件类中提取命令定义"""
    
    def __init__(self, plugin_class):
        """
        初始化命令提取器
        
        Args:
            plugin_class: 插件类（继承自 Star）
        """
        self.plugin_class = plugin_class
        self.commands = []
    
    def extract_commands(self) -> List[Dict[str, Any]]:
        """
        提取插件中的所有命令
        
        Returns:
            命令列表，每个命令包含：name, desc, aliases
        """
        commands = []
        
        # 遍历插件类的所有方法
        for name, method in inspect.getmembers(self.plugin_class, predicate=inspect.ismethod):
            # 检查方法是否有 __filter_command__ 属性（由 @filter.command 装饰器添加）
            if hasattr(method, '__filter_command__'):
                filter_info = method.__filter_command__
                
                # 提取命令信息
                command_name = filter_info.get('command', name)
                aliases = filter_info.get('alias', set())
                
                # 提取 docstring 作为描述
                desc = method.__doc__.strip() if method.__doc__ else ""
                
                commands.append({
                    'name': command_name,
                    'desc': desc,
                    'aliases': list(aliases) if aliases else [],
                    'method': name
                })
        
        return commands
    
    @staticmethod
    def extract_from_source(source_file: Path) -> List[Dict[str, Any]]:
        """
        从源代码文件中提取命令（备用方法，使用 AST 解析）
        
        Args:
            source_file: 插件源代码文件路径
            
        Returns:
            命令列表
        """
        commands = []
        
        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source)
            
            # 遍历 AST 查找 @filter.command 装饰器
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for decorator in node.decorator_list:
                        # 检查是否是 filter.command 装饰器
                        if (isinstance(decorator, ast.Call) and
                            isinstance(decorator.func, ast.Attribute) and
                            decorator.func.attr == 'command'):
                            
                            # 提取命令名称（第一个参数）
                            if decorator.args:
                                command_name = ast.literal_eval(decorator.args[0])
                            else:
                                command_name = node.name
                            
                            # 提取别名（alias 关键字参数）
                            aliases = []
                            for keyword in decorator.keywords:
                                if keyword.arg == 'alias':
                                    if isinstance(keyword.value, ast.Set):
                                        aliases = [ast.literal_eval(elt) for elt in keyword.value.elts]
                            
                            # 提取 docstring
                            desc = ast.get_docstring(node) or ""
                            
                            commands.append({
                                'name': command_name,
                                'desc': desc,
                                'aliases': aliases,
                                'method': node.name
                            })
        
        except Exception as e:
            print(f"警告：从源代码提取命令失败: {e}")
        
        return commands


def generate_help_config(commands: List[Dict[str, Any]], groups: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    根据命令列表生成帮助配置
    
    Args:
        commands: 命令列表
        groups: 分组配置（包含 group 名称和 command_patterns）
        
    Returns:
        帮助配置字典
    """
    help_list = []
    
    for group_config in groups:
        group_name = group_config['group']
        patterns = group_config.get('patterns', [])
        icon_map = group_config.get('icon_map', {})
        
        group_commands = []
        
        # 根据模式匹配命令
        for cmd in commands:
            for pattern in patterns:
                if pattern in cmd['name']:
                    # 获取图标编号
                    icon = icon_map.get(cmd['name'], 79)  # 默认图标 79
                    
                    group_commands.append({
                        'icon': icon,
                        'title': cmd['name'],
                        'desc': cmd['desc']
                    })
                    break
        
        if group_commands:
            help_list.append({
                'group': group_name,
                'list': group_commands
            })
    
    return help_list

