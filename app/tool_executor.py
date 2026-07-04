"""工具执行器 — 缓存 + Scraper 双路径"""
import json
import logging

log = logging.getLogger("ole-agent")

MAX_RESULT_CHARS = 8000


class ToolExecutor:
    """缓存工具走 JSON，实时工具通过 ScraperPool 走浏览器"""

    def __init__(self, scraper_pool=None):
        self._pool = scraper_pool
        self._handlers = {
            "get_courses": self._get_courses,
            "get_assignments": self._get_assignments,
            "get_upcoming_classes": self._get_upcoming_classes,
            "list_course_files": self._list_course_files,
            "get_grades": self._get_grades,
            "browse_course_page": self._browse_course_page,
            "download_course_files": self._download_course_files,
            "get_course_materials": self._get_course_materials,
            "search_course_info": self._search_course_info,
            "retrieve_course_content": self._retrieve_course_content,
        }

    async def execute(self, tool_name: str, arguments: dict) -> str:
        handler = self._handlers.get(tool_name)
        if not handler:
            return json.dumps({"error": f"Unknown tool: {tool_name}"}, ensure_ascii=False)
        try:
            result = await handler(**{k: v for k, v in arguments.items() if v is not None})
            text = json.dumps(result, ensure_ascii=False, default=str)
            return text[:MAX_RESULT_CHARS]
        except Exception as e:
            log.error("Tool %s failed: %s", tool_name, e, exc_info=True)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    # ── 缓存数据（快） ──────────────────────────────────────────

    async def _get_courses(self, course_code: str = None) -> dict:
        from .cache import get_cached
        data = await get_cached("courses")
        courses = data.get("courses", [])
        if course_code:
            code_upper = course_code.upper()
            courses = [c for c in courses if code_upper in c.get("code", "")]
        return {"courses": courses, "total": len(courses)}

    async def _get_assignments(self, course_code: str = None) -> dict:
        from .cache import get_cached
        data = await get_cached("assignments")
        assignments = data.get("assignments", [])
        if course_code:
            code_upper = course_code.upper()
            assignments = [a for a in assignments if code_upper in a.get("course", "")]
        assignments.sort(key=lambda a: a.get("deadline", ""))
        return {"assignments": assignments, "total": len(assignments)}

    async def _get_upcoming_classes(self, course_code: str = None) -> dict:
        from .cache import get_cached
        data = await get_cached("classes")
        classes = data.get("upcoming_classes", [])
        if course_code:
            code_upper = course_code.upper()
            classes = [c for c in classes if code_upper in c.get("course", "")]
        return {"upcoming_classes": classes, "total": len(classes)}

    # ── 实时数据（通过 Scraper） ────────────────────────────────

    async def _get_scraper(self):
        """获取 scraper 实例，失败返回 None"""
        if not self._pool:
            return None
        try:
            return await self._pool.get()
        except Exception as e:
            log.error("Failed to get scraper: %s", e)
            return None

    async def _list_course_files(self, course_code: str, file_type: str = "all") -> dict:
        """通过 scraper 从 Dashboard 提取课程文件列表"""
        scraper = await self._get_scraper()
        if not scraper or not scraper.page:
            return {
                "course_code": course_code,
                "files": [],
                "total": 0,
                "hint": "浏览器未启动，无法获取文件列表。请稍后重试。",
            }

        try:
            from src.actions.downloads import DownloadsManager
            dm = DownloadsManager()
            files = await dm.get_files_from_dashboard(
                scraper.page, course_code=course_code, file_type=file_type
            )
            return {
                "course_code": course_code,
                "files": files,
                "total": len(files),
            }
        except Exception as e:
            log.error("list_course_files failed: %s", e, exc_info=True)
            return {"course_code": course_code, "files": [], "total": 0, "error": str(e)}

    async def _get_grades(self, course_code: str) -> dict:
        """通过 scraper 进入课程页面获取成绩"""
        scraper = await self._get_scraper()
        if not scraper or not scraper.page:
            return {
                "course_code": course_code,
                "grades": [],
                "hint": "浏览器未启动，无法获取成绩。",
            }

        try:
            # 先导航到课程页面
            from src.actions.courses import CoursesExtractor
            ce = CoursesExtractor()
            ok = await ce.navigate_to_course(scraper.page, course_code)
            if not ok:
                return {"course_code": course_code, "grades": [], "error": "无法导航到课程页面"}

            grades = await scraper.grades.get_grades(scraper.page, course_code)
            return {
                "course_code": course_code,
                "grades": grades,
                "total": len(grades),
            }
        except Exception as e:
            log.error("get_grades failed: %s", e, exc_info=True)
            return {"course_code": course_code, "grades": [], "error": str(e)}

    async def _browse_course_page(self, course_code: str, section: str = None) -> dict:
        """导航到课程页面并提取内容，可选点击特定 section

        Args:
            course_code: 课程代码
            section: 可选，要查看的板块名称（如 "Class Activities", "My Progress"）
        """
        scraper = await self._get_scraper()
        if not scraper or not scraper.page:
            return {"error": "浏览器未启动，无法访问课程页面。"}

        try:
            # 导航到课程页面
            from src.actions.courses import CoursesExtractor
            ce = CoursesExtractor()
            ok = await ce.navigate_to_course(scraper.page, course_code)
            if not ok:
                return {"error": f"无法导航到课程 {course_code} 的页面"}

            # 如果指定了 section，尝试点击对应的导航项
            section_id = None
            if section:
                # 常见 section 对应的 gotoItem ID
                section_map = {
                    "class activities": "10",
                    "my progress": "11",
                    "course content": "5",
                    "assignments": "6",
                    "announcements": "1",
                    "discussion": "7",
                    "gradebook": "11",
                }
                section_id = section_map.get(section.lower())

            if section_id:
                try:
                    # 在 frame 或 page 中点击
                    frame = scraper.page
                    has_frame = await scraper.page.query_selector("iframe, frameset, frame")
                    if has_frame:
                        frame = scraper.page.frame_locator("iframe, frameset frame, frame").first
                    await frame.click(f'a[onclick*="gotoItem(\'{section_id}\')"]', timeout=5000)
                    await scraper.page.wait_for_load_state("networkidle", timeout=10000)
                except Exception as e:
                    log.warning("Failed to click section %s: %s", section, e)

            # 提取页面文本内容
            try:
                frame = scraper.page
                has_frame = await scraper.page.query_selector("iframe, frameset, frame")
                if has_frame:
                    frame = scraper.page.frame_locator("iframe, frameset frame, frame").first
                page_text = await frame.inner_text("body")
            except Exception:
                page_text = await scraper.page.inner_text("body")

            # 截断
            if len(page_text) > 3000:
                page_text = page_text[:3000] + "\n...(内容已截断)"

            return {
                "course_code": course_code,
                "section": section,
                "page_text": page_text,
                "source_url": scraper.page.url,
            }
        except Exception as e:
            log.error("browse_course_page failed: %s", e, exc_info=True)
            return {"error": f"访问课程页面失败: {e}"}

    # ── Skill 硬编码工具 ──────────────────────────────────────

    async def _download_course_files(
        self,
        course_code: str,
        file_type: str = "all",
        file_name: str = None,
        output_dir: str = None,
        max_files: int = 1,
    ) -> dict:
        """下载课程文件 — 通过课程页面 TileData 下载，支持文件名筛选和指定保存目录"""
        scraper = await self._get_scraper()
        if not scraper or not scraper.page:
            return {"error": "浏览器未启动，无法下载文件。请稍后重试。"}

        try:
            from pathlib import Path
            from src.actions.downloads import DownloadsManager

            dm = DownloadsManager()
            result = await dm.download_from_course_page(
                scraper.page,
                course_code=course_code,
                file_type=file_type,
                file_name=file_name,
                max_files=max_files,
                output_dir=Path(output_dir) if output_dir else None,
            )

            result["course_code"] = course_code
            result["file_type"] = file_type
            return result
        except Exception as e:
            log.error("download_course_files failed: %s", e, exc_info=True)
            return {"error": f"下载失败: {e}"}

    async def _get_course_materials(
        self, course_code: str, category: str = "all"
    ) -> dict:
        """列出课程可下载材料清单（与下载同源 TileData）"""
        scraper = await self._get_scraper()
        if not scraper or not scraper.page:
            return {"error": "浏览器未启动，无法获取材料列表。"}

        try:
            from src.actions.downloads import DownloadsManager

            dm = DownloadsManager()
            result = await dm.list_files_from_course_page(
                scraper.page, course_code=course_code, file_type=category
            )
            result["category"] = category
            return result
        except Exception as e:
            log.error("get_course_materials failed: %s", e, exc_info=True)
            return {"error": f"获取材料列表失败: {e}"}

    async def _search_course_info(
        self, course_code: str, query: str
    ) -> dict:
        """从课程 TileData 搜索特定信息（日程 + 文件名）"""
        scraper = await self._get_scraper()
        if not scraper or not scraper.page:
            return {"error": "浏览器未启动，无法搜索课程信息。"}

        try:
            from src.actions.downloads import DownloadsManager

            dm = DownloadsManager()
            return await dm.search_course_info(
                scraper.page, course_code=course_code, query=query
            )
        except Exception as e:
            log.error("search_course_info failed: %s", e, exc_info=True)
            return {"error": f"搜索课程信息失败: {e}"}

    async def _retrieve_course_content(
        self, query: str, course_code: str = None
    ) -> dict:
        """从课程讲义/课件 PDF 检索内容(RAG,回答课件类问题)"""
        from .rag_index import retrieve

        results = retrieve(query, top_k=5)
        if not results:
            return {"query": query, "results": [], "total": 0,
                    "hint": "RAG 索引未建或为空。先运行:python3 -m app.rag_index build"}
        return {"query": query, "results": results, "total": len(results)}
