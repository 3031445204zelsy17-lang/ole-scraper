"""
数据提取模块
"""
from .courses import CoursesExtractor
from .assignments import AssignmentsExtractor
from .grades import GradesExtractor
from .calendar import CalendarExtractor
from .downloads import DownloadsManager

__all__ = [
    "CoursesExtractor",
    "AssignmentsExtractor",
    "GradesExtractor",
    "CalendarExtractor",
    "DownloadsManager",
]
