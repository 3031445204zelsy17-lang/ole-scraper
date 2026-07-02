"""DeepSeek function calling 工具定义 — 缓存 + 实时浏览器"""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_courses",
            "description": "获取所有已注册课程的列表。可选传入 course_code 过滤特定课程。",
            "parameters": {
                "type": "object",
                "properties": {
                    "course_code": {
                        "type": "string",
                        "description": "可选，课程代码过滤，如 COMP2090SEF",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_assignments",
            "description": "获取待交作业列表，按截止日期排序。可选传入 course_code 过滤特定课程的作业。",
            "parameters": {
                "type": "object",
                "properties": {
                    "course_code": {
                        "type": "string",
                        "description": "可选，课程代码过滤，如 COMP2090SEF",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_classes",
            "description": "获取即将到来的课程时间表，包括时间、地点和课程类型。可选传入 course_code 过滤。",
            "parameters": {
                "type": "object",
                "properties": {
                    "course_code": {
                        "type": "string",
                        "description": "可选，课程代码过滤",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_course_files",
            "description": "列出课程可下载的文件（课件、辅导材料等）。通过浏览器实际访问 OLE Dashboard 获取真实文件列表，返回文件名、URL和类型。",
            "parameters": {
                "type": "object",
                "properties": {
                    "course_code": {
                        "type": "string",
                        "description": "课程代码，如 COMP2090SEF 或 IT1030SEF",
                    },
                    "file_type": {
                        "type": "string",
                        "enum": ["lecture", "tutorial", "all"],
                        "description": "文件类型筛选，默认 all",
                    },
                },
                "required": ["course_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_grades",
            "description": "获取特定课程的成绩信息。通过浏览器进入课程 My Progress 页面获取真实成绩数据。",
            "parameters": {
                "type": "object",
                "properties": {
                    "course_code": {
                        "type": "string",
                        "description": "课程代码",
                    }
                },
                "required": ["course_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_course_page",
            "description": "导航到课程页面并提取页面内容。适用于查询课程特定信息，如 Presentation 安排、课程公告、Class Activities 内容等。通过浏览器实际访问 OLE 课程页面。",
            "parameters": {
                "type": "object",
                "properties": {
                    "course_code": {
                        "type": "string",
                        "description": "课程代码，如 IT1030SEF",
                    },
                    "section": {
                        "type": "string",
                        "description": "可选，要查看的课程板块。可选值: 'Class Activities', 'My Progress', 'Course Content', 'Assignments', 'Announcements', 'Discussion'",
                    },
                },
                "required": ["course_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "download_course_files",
            "description": "下载课程文件到本地。通过课程页面 TileData 提取文件列表。注意：用户说下载 tutorial/教程 时必须传 file_type='tutorial'，说下载 lecture/课件时必须传 file_type='lecture'。批量下载时传 max_files=50。",
            "parameters": {
                "type": "object",
                "properties": {
                    "course_code": {
                        "type": "string",
                        "description": "课程代码，如 COMP2090SEF",
                    },
                    "file_type": {
                        "type": "string",
                        "enum": ["lecture", "tutorial", "all"],
                        "description": "用户说下载 tutorial/教程 → 传 'tutorial'；用户说下载 lecture/课件 → 传 'lecture'；其他情况传 'all'",
                    },
                    "file_name": {
                        "type": "string",
                        "description": "文件名关键词，用于匹配具体文件。如 'lecture 5'、'Week 3'、'tutorial'。不传则下载 file_type 匹配的第一个文件。",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "文件保存目录的绝对路径(可选)。不传则默认保存到 downloads/<课程代码>/。",
                    },
                    "max_files": {
                        "type": "integer",
                        "description": "最大下载数量。下载全部时传 50，默认 1（单个文件）",
                    },
                },
                "required": ["course_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_course_materials",
            "description": "列出课程所有可下载的材料，返回分类统计（lecture/tutorial/assignment/other）。不执行下载，仅列出文件清单供用户确认。",
            "parameters": {
                "type": "object",
                "properties": {
                    "course_code": {
                        "type": "string",
                        "description": "课程代码",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["lecture", "tutorial", "assignment", "all"],
                        "description": "材料类别筛选，默认 all",
                    },
                },
                "required": ["course_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_course_info",
            "description": "从课程页面搜索特定信息（如 presentation 安排、考试时间、分组信息等）。通过课程 TileData 全文搜索，返回匹配的日程项和文件名。",
            "parameters": {
                "type": "object",
                "properties": {
                    "course_code": {
                        "type": "string",
                        "description": "课程代码，如 IT1030SEF",
                    },
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，如 'presentation'、'group project'、'exam'、'mid-term'",
                    },
                },
                "required": ["course_code", "query"],
            },
        },
    },
]
