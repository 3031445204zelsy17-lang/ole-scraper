"""
成绩查询模块
"""
from playwright.async_api import Page
from typing import List, Dict

from ..utils.helpers import log_message


class GradesExtractor:
    """提取成绩信息"""

    def __init__(self):
        pass

    async def get_grades(self, page: Page, course_code: str = None) -> List[Dict]:
        """
        获取成绩信息

        Args:
            page: Page 对象
            course_code: 可选的课程代码，不指定则获取所有课程成绩

        Returns:
            成绩列表 [{course, item, score, max_score, grade}]
        """
        grades = []

        try:
            if course_code:
                grades = await self._get_course_grades(page, course_code)
            else:
                # 获取所有课程成绩需要遍历
                # 这里简化处理，返回空列表
                log_message("获取所有课程成绩需要遍历每门课程", "WARN")

            return grades

        except Exception as e:
            log_message(f"获取成绩失败: {e}", "ERROR")
            return []

    async def _get_course_grades(self, page: Page, course_code: str) -> List[Dict]:
        """获取特定课程的成绩"""
        grades = []

        try:
            # 点击 My Progress 菜单
            await page.click('a[onclick*="gotoItem(\'11\')"]')
            await page.wait_for_load_state("networkidle", timeout=10000)

            # 查找成绩表格
            grade_rows = await page.query_selector_all("table tr, .grade-row")

            for row in grade_rows:
                grade = await self._parse_grade_row(row, course_code)
                if grade:
                    grades.append(grade)

            log_message(f"从课程 {course_code} 获取到 {len(grades)} 条成绩记录")
            return grades

        except Exception as e:
            log_message(f"获取课程成绩失败: {e}", "ERROR")
            return []

    async def _parse_grade_row(self, row, course_code: str) -> Dict:
        """解析成绩行"""
        try:
            cells = await row.query_selector_all("td")
            if len(cells) < 3:
                return None

            item = await cells[0].inner_text()
            score_text = await cells[1].inner_text() if len(cells) > 1 else ""
            grade_text = await cells[2].inner_text() if len(cells) > 2 else ""

            # 解析分数
            score = 0.0
            max_score = 100.0
            if "/" in score_text:
                parts = score_text.split("/")
                try:
                    score = float(parts[0].strip())
                    max_score = float(parts[1].strip())
                except ValueError:
                    pass

            return {
                "course": course_code,
                "item": item.strip(),
                "score": score,
                "max_score": max_score,
                "grade": grade_text.strip(),
            }

        except Exception:
            return None
