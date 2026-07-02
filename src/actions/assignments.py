"""
作业信息提取模块
"""
from playwright.async_api import Page
from typing import List, Dict
from datetime import datetime
import re

from ..utils.helpers import load_config, log_message


class AssignmentsExtractor:
    """提取作业信息"""

    def __init__(self):
        self.config = load_config()

    async def get_assignments_from_dashboard(self, page: Page) -> List[Dict]:
        """
        从 Dashboard 提取作业列表

        Returns:
            作业列表 [{course, title, deadline, submit_url}]
        """
        assignments = []

        try:
            # 确保在 Dashboard 页面
            if not page.url.endswith("/dashboard/index.html"):
                await page.goto(
                    "https://ole.hkmu.edu.hk/dashboard/index.html", timeout=10000
                )

            # 等待页面加载
            await page.wait_for_load_state("networkidle", timeout=10000)

            # 直接查找作业链接
            assignment_items = await page.query_selector_all(
                'a[href*="_tma.nsf"]'
            )

            for item in assignment_items:
                assignment = await self._parse_assignment_item(item)
                if assignment:
                    assignments.append(assignment)

            log_message(f"从 Dashboard 提取到 {len(assignments)} 个作业")
            return assignments

        except Exception as e:
            log_message(f"提取作业列表失败: {e}", "ERROR")
            return []

    async def _parse_assignment_item(self, item) -> Dict:
        """解析单个作业项"""
        try:
            # 获取链接
            link = await item.query_selector("a")
            if not link:
                link = item

            href = await link.get_attribute("href") or ""
            text = await link.inner_text()

            # 从 URL 提取课程代码
            course_code = ""
            url_match = re.search(r"/([A-Z]+\d+[A-Z]*)_tma\.nsf", href)
            if url_match:
                course_code = url_match.group(1)

            # 尝试获取截止时间
            deadline_text = ""

            # 尝试从父元素或兄弟元素获取更多信息
            try:
                parent = await item.evaluate_handle("el => el.parentElement")
                parent_text = await parent.evaluate("el => el.innerText")

                # 查找日期格式
                date_match = re.search(
                    r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}[/\-]\d{1,2}[/\-]\d{1,2})",
                    parent_text,
                )
                if date_match:
                    deadline_text = date_match.group(1)

                # 查找时间格式
                time_match = re.search(r"(\d{1,2}:\d{2})", parent_text)
                if time_match:
                    deadline_text += " " + time_match.group(1)
            except Exception:
                pass

            return {
                "course": course_code,
                "title": text.strip(),
                "deadline": deadline_text.strip(),
                "submit_url": href,
            }

        except Exception:
            return None

    async def get_course_assignments(self, page: Page, course_code: str) -> List[Dict]:
        """
        获取特定课程的作业列表

        Args:
            page: 已在课程页面的 Page
            course_code: 课程代码

        Returns:
            作业列表
        """
        assignments = []

        try:
            # 点击 Assignment File 菜单
            await page.click('a[onclick*="gotoItem(\'15\')"]')

            # 等待新页面或内容加载
            await page.wait_for_load_state("networkidle", timeout=10000)

            # 查找作业列表
            assignment_rows = await page.query_selector_all(
                "table tr, .assignment-row, .file-item"
            )

            for row in assignment_rows:
                assignment = await self._parse_assignment_row(row, course_code)
                if assignment:
                    assignments.append(assignment)

            log_message(f"从课程 {course_code} 提取到 {len(assignments)} 个作业")
            return assignments

        except Exception as e:
            log_message(f"获取课程作业失败: {e}", "ERROR")
            return []

    async def _parse_assignment_row(self, row, course_code: str) -> Dict:
        """解析作业行"""
        try:
            cells = await row.query_selector_all("td")
            if len(cells) < 2:
                return None

            title = await cells[0].inner_text() if cells else ""
            deadline = await cells[1].inner_text() if len(cells) > 1 else ""

            link = await cells[0].query_selector("a")
            href = await link.get_attribute("href") if link else ""

            return {
                "course": course_code,
                "title": title.strip(),
                "deadline": deadline.strip(),
                "submit_url": href,
            }

        except Exception:
            return None
