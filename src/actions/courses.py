"""
课程列表提取模块
"""
from playwright.async_api import Page
from typing import List, Dict
import re

from ..utils.helpers import load_config, log_message, clean_course_code


class CoursesExtractor:
    """提取课程列表"""

    def __init__(self):
        self.config = load_config()

    async def get_courses_from_dashboard(self, page: Page) -> List[Dict]:
        """
        从 Dashboard 提取课程列表

        Returns:
            课程列表 [{code, name, url}]
        """
        courses = []

        try:
            # 等待页面加载
            await page.wait_for_selector("text=我的學科", timeout=10000)

            # 查找课程卡片
            course_cards = await page.query_selector_all(
                ".course-card, .course-item, [data-course-code]"
            )

            # 如果找不到课程卡片，尝试其他选择器
            if not course_cards:
                # 尝试查找包含课程链接的区域
                course_links = await page.query_selector_all(
                    'a[href*="/course2600/"][href$=".nsf"]'
                )

                for link in course_links:
                    href = await link.get_attribute("href") or ""
                    text = await link.inner_text()

                    # 提取课程代码
                    code_match = re.search(r"/([A-Z]+\d+[A-Z]*)\.nsf", href)
                    if code_match:
                        code = code_match.group(1)
                    else:
                        # 从文本中提取
                        code = text.split()[0] if text else ""

                    if code and code not in [c["code"] for c in courses]:
                        courses.append(
                            {
                                "code": clean_course_code(code),
                                "name": text.replace(code, "").strip(),
                                "url": href
                                if href.startswith("http")
                                else f"https://ole.hkmu.edu.hk{href}",
                            }
                        )

            log_message(f"从 Dashboard 提取到 {len(courses)} 门课程")
            return courses

        except Exception as e:
            log_message(f"提取课程列表失败: {e}", "ERROR")
            return []

    async def get_course_navigation(self, page: Page, course_code: str) -> Dict:
        """
        获取课程页面的导航菜单

        Args:
            page: 已导航到课程 AutoFramed 页面的 Page
            course_code: 课程代码

        Returns:
            导航菜单 {name: url}
        """
        navigation = {}

        try:
            # 等待页面加载
            await page.wait_for_load_state("networkidle", timeout=10000)

            # 查找导航链接
            nav_links = await page.query_selector_all('a[onclick*="gotoItem"]')

            for link in nav_links:
                onclick = await link.get_attribute("onclick") or ""
                text = await link.inner_text()

                # 提取 gotoItem 参数
                match = re.search(r"gotoItem\(['\"]?(\d+)['\"]?\)", onclick)
                if match:
                    item_id = match.group(1)
                    navigation[text.strip()] = {
                        "id": item_id,
                        "onclick": onclick,
                    }

            log_message(f"获取到 {len(navigation)} 个导航项")
            return navigation

        except Exception as e:
            log_message(f"获取导航菜单失败: {e}", "ERROR")
            return {}

    async def navigate_to_course(
        self, page: Page, course_code: str, username: str = None
    ) -> bool:
        """
        导航到课程 AutoFramed 页面

        Args:
            page: Page 对象
            course_code: 课程代码
            username: 用户名（用于构建 AutoFramed URL）

        Returns:
            是否成功
        """
        if username is None:
            from ..utils.helpers import get_credentials

            _, username = get_credentials()  # 获取用户名

        try:
            # 使用 AutoFramed URL
            url = f"https://ole.hkmu.edu.hk/course2600/{course_code}.nsf/usernavlookup/{username}?OpenDocument&AutoFramed"
            await page.goto(url, timeout=15000)
            await page.wait_for_load_state("networkidle", timeout=10000)
            log_message(f"已导航到课程 {course_code}")
            return True
        except Exception as e:
            log_message(f"导航到课程失败: {e}", "ERROR")
            return False
