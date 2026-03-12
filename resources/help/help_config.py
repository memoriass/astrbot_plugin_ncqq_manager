"""NCQQ Manager 插件帮助配置 - Miao-Plugin 风格"""

# 帮助配置
HELP_CONFIG = {
    # 帮助标题
    "title": "NCQQ Manager 帮助",
    
    # 帮助副标题
    "subTitle": "NapCat QQ Manager Plugin",
    
    # 帮助表格列数，可选：2-5，默认3
    "colCount": 3,
    
    # 单列宽度，默认265
    "colWidth": 265,
}

# 帮助菜单内容（从 main.py 中提取的真实命令）
HELP_LIST = [
    {
        "group": "基础配置",
        "list": [
            {
                "icon": 79,
                "title": "ncqq帮助 / ncqq help",
                "desc": "显示帮助信息"
            },
            {
                "icon": 85,
                "title": "ncqq状态 / ncqq status",
                "desc": "查看连接状态"
            }
        ]
    },
    {
        "group": "容器管理",
        "list": [
            {
                "icon": 67,
                "title": "ncqq列表 / ncqq list",
                "desc": "查看所有容器"
            },
            {
                "icon": 63,
                "title": "ncqq详情 <容器名> / ncqq info",
                "desc": "查看容器详情"
            },
            {
                "icon": 32,
                "title": "ncqq创建 <容器名> / ncqq create",
                "desc": "创建新容器"
            },
            {
                "icon": 86,
                "title": "ncqq启动 <容器名> / ncqq start",
                "desc": "启动容器"
            },
            {
                "icon": 87,
                "title": "ncqq停止 <容器名> / ncqq stop",
                "desc": "停止容器"
            },
            {
                "icon": 88,
                "title": "ncqq重启 <容器名> / ncqq restart",
                "desc": "重启容器"
            },
            {
                "icon": 35,
                "title": "ncqq删除 <容器名> / ncqq delete",
                "desc": "删除容器"
            },
            {
                "icon": 86,
                "title": "ncqq全部启动 / ncqq startall",
                "desc": "启动所有已停止的容器"
            },
            {
                "icon": 87,
                "title": "ncqq全部停止 / ncqq stopall",
                "desc": "停止所有运行中的容器"
            }
        ]
    },
    {
        "group": "登录管理",
        "list": [
            {
                "icon": 22,
                "title": "ncqq二维码 <容器名>",
                "desc": "获取容器登录二维码"
            }
        ]
    },
    {
        "group": "节点管理",
        "list": [
            {
                "icon": 83,
                "title": "ncqq节点列表 / ncqq nodes",
                "desc": "查看所有节点"
            }
        ]
    }
]

