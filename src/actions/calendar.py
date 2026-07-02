"""
日历事件提取模块
"""
from playwright.async_api import Page
from typing import List, Dict
from datetime import datetime
import re

from ..utils.helpers import log_message, format_datetime


class CalendarExtractor:
    """提取日历事件"""

    def __init__(self):
        pass

    async def get_upcoming_classes(self, page: Page) -> List[Dict]:
        """
        从 Dashboard 获取即将上课信息

        Returns:
            课程列表 [{course, type, time, location, instructor}]
        """
        classes = []

        try:
            # 确保在 Dashboard 页面
            if not page.url.endswith("/dashboard/index.html"):
                await page.goto(
                    "https://ole.hkmu.edu.hk/dashboard/index.html", timeout=10000
                )

            # 等待即将上课区域
            await page.wait_for_selector("text=即將上課", timeout=10000)

            # 查找课程项
            class_items = await page.query_selector_all(
                ".class-item, .schedule-item, [data-class]"
            )

            if not class_items:
                # 尝试其他选择器
                class_items = await page.query_selector_all(
                    '.upcoming-classes li, [class*="class"] li'
                )

            for item in class_items:
                class_info = await self._parse_class_item(item)
                if class_info:
                    classes.append(class_info)

            log_message(f"提取到 {len(classes)} 个即将上课信息")
            return classes

        except Exception as e:
            log_message(f"提取即将上课信息失败: {e}", "ERROR")
            return []

    async def _parse_class_item(self, item) -> Dict:
        """解析课程项"""
        try:
            text = await item.inner_text()
            lines = [l.strip() for l in text.split("\n") if l.strip()]

            if not lines:
                return None

            # 尝试解析课程代码和类型
            course = ""
            class_type = ""
            time_str = ""
            location = ""
            instructor = ""

            for line in lines:
                # 课程代码通常在前
                if re.match(r"^[A-Z]+\s*\d+[A-Z]*", line):
                    course = line
                # 时间格式
                elif re.match(r"\d{1,2}:\d{2}", line) or re.match(
                    r"\d{4}-\d{2}-\d{2}", line
                ):
                    time_str = line
                # 地点
                elif re.match(r"[A-Z]+-\d+|JCC\s+\w+", line):
                    location = line
                # 类型
                elif "Lecture" in line or "Tutorial" in line:
                    class_type = line

            return {
                "course": course,
                "type": class_type,
                "time": format_datetime(time_str),
                "location": location,
                "instructor": instructor,
            }

        except Exception:
            return None

    async def get_calendar_events(
        self, page: Page, course_code: str = None
    ) -> List[Dict]:
        """
        获取日历事件

        Args:
            page: Page 对象
            course_code: 可选的课程代码

        Returns:
            事件列表 [{title, date, course, type}]
        """
        events = []

        try:
            if course_code:
                # 导航到课程的 Calendar
                await page.click('a[onclick*="gotoItem(\'6\')"]')
                await page.wait_for_load_state("networkidle", timeout=10000)

            # 查找日历事件
            event_items = await page.query_selector_all(
                ".calendar-event, .event-item, [data-event]"
            )

            for item in event_items:
                event = await self._parse_event_item(item, course_code)
                if event:
                    events.append(event)

            log_message(f"获取到 {len(events)} 个日历事件")
            return events

        except Exception as e:
            log_message(f"获取日历事件失败: {e}", "ERROR")
            return []

    async def _parse_event_item(self, item, course_code: str = None) -> Dict:
        """解析日历事件"""
        try:
            title_elem = await item.query_selector(".event-title, .title, strong")
            date_elem = await item.query_selector(
                ".event-date, .date, time, [datetime]"
            )

            title = await title_elem.inner_text() if title_elem else ""
            date = await date_elem.inner_text() if date_elem else ""

            return {
                "title": title.strip(),
                "date": format_datetime(date.strip()),
                "course": course_code or "",
                "type": "calendar",
            }

        except Exception:
            return None
