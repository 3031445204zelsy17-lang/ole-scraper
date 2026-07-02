"""
文件下载模块
"""
from playwright.async_api import Page, Download
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import unquote
import re
import asyncio
import json

from ..utils.helpers import log_message, ensure_dir, PROJECT_ROOT


class DownloadsManager:
    """管理文件下载"""

    def __init__(self, download_dir: Path = None):
        self.download_dir = download_dir or PROJECT_ROOT / "downloads"
        ensure_dir(self.download_dir)

    async def download_file(
        self,
        page: Page,
        url: str = None,
        selector: str = None,
        filename: str = None,
    ) -> Optional[Path]:
        """
        下载文件

        Args:
            page: Page 对象
            url: 直接下载 URL（可选）
            selector: 文件链接选择器（可选）
            filename: 保存的文件名（可选）

        Returns:
            下载文件的路径，失败返回 None
        """
        try:
            async with page.expect_download(timeout=60000) as download_info:
                if url:
                    # 用 JS 导航避免 page.goto 的 "Download is starting" 错误
                    await page.evaluate('(url) => window.location.href = url', url)
                elif selector:
                    await page.click(selector)
                else:
                    raise ValueError("必须提供 url 或 selector")

            download = await download_info.value

            # 确定文件名
            if filename:
                save_name = filename
            else:
                save_name = download.suggested_filename

            save_path = self.download_dir / save_name

            # 保存文件
            await download.save_as(save_path)
            log_message(f"文件已下载: {save_path}")

            return save_path

        except Exception as e:
            log_message(f"下载文件失败: {e}", "ERROR")
            return None

    async def get_course_files(
        self,
        page: Page,
        course_code: str,
        file_type: str = "lecture",
        download: bool = False,
    ) -> List[Dict]:
        """
        获取课程文件列表

        Args:
            page: 已在课程 Class Activities 页面的 Page
            course_code: 课程代码
            file_type: 文件类型 (lecture, tutorial, all)
            download: 是否下载文件

        Returns:
            文件列表 [{name, url, type, downloaded, local_path}]
        """
        files = []

        try:
            # 尝试点击 Class Activities 菜单
            # 首先检查是否在 frame 中
            has_frame = await page.query_selector("iframe, frameset, frame")
            if has_frame:
                frame = page.frame_locator("iframe, frameset frame, frame").first
            else:
                frame = page

            try:
                if has_frame:
                    await frame.click('a[onclick*="gotoItem(\'10\')"]', timeout=5000)
                    await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                # 如果点击失败，尝试直接在当前页面查找文件
                log_message("无法点击 Class Activities 菜单，尝试直接查找文件链接")

            # 检查页面内容（在 frame 或 page 中）
            try:
                page_text = await frame.inner_text("body")
            except:
                page_text = await page.inner_text("body")
            if "No task available" in page_text or "沒有" in page_text:
                log_message(f"课程 {course_code} 的 Class Activities 页面为空")
                return []

            # 查找文件链接（在 frame 或 page 中）
            # OLE 文件链接格式: /$File/xxx.pptx 或 $File/xxx.pdf
            file_selectors = 'a[href*="$File/"], a[href*="/$File/"], a[href*=".pptx"], a[href*=".ppt"], a[href*=".pdf"], a[href*=".doc"], a[href*=".docx"], a[href*=".zip"], a[href*=".rar"]'
            try:
                file_links = await frame.query_selector_all(file_selectors)
            except:
                file_links = await page.query_selector_all(file_selectors)

            for link in file_links:
                file_info = await self._parse_file_link(link, course_code)
                if file_info:
                    # 过滤文件类型
                    if file_type != "all":
                        file_name_lower = file_info["name"].lower()
                        if file_type == "lecture" and "lecture" not in file_name_lower and "lect" not in file_name_lower:
                            continue
                        if file_type == "tutorial" and "tutorial" not in file_name_lower and "tut" not in file_name_lower:
                            continue

                    # 下载文件
                    if download:
                        local_path = await self.download_file(
                            page, selector=f'a[href="{file_info["url"]}"]'
                        )
                        file_info["downloaded"] = local_path is not None
                        file_info["local_path"] = str(local_path) if local_path else None
                    else:
                        file_info["downloaded"] = False
                        file_info["local_path"] = None

                    files.append(file_info)

            log_message(f"找到 {len(files)} 个文件")
            return files

        except Exception as e:
            log_message(f"获取课程文件失败: {e}", "ERROR")
            return []

    async def _parse_file_link(self, link, course_code: str) -> Optional[Dict]:
        """解析文件链接"""
        try:
            href = await link.get_attribute("href") or ""
            text = await link.inner_text()

            if not href or not text:
                return None

            # 确定文件类型
            ext = Path(href).suffix.lower()
            file_type = "other"
            if "lecture" in text.lower() or "lect" in text.lower():
                file_type = "lecture"
            elif "tutorial" in text.lower() or "tut" in text.lower():
                file_type = "tutorial"
            elif "assignment" in text.lower():
                file_type = "assignment"

            return {
                "name": text.strip(),
                "url": href,
                "extension": ext,
                "type": file_type,
                "course": course_code,
            }

        except Exception:
            return None

    async def download_lectures(
        self,
        page: Page,
        course_code: str,
        lecture_nums: List[int] = None,
        output_dir: Path = None,
    ) -> List[Path]:
        """
        下载指定讲座文件

        Args:
            page: Page 对象
            course_code: 课程代码
            lecture_nums: 要下载的讲座编号列表，None 表示全部
            output_dir: 输出目录

        Returns:
            下载成功的文件路径列表
        """
        if output_dir:
            self.download_dir = output_dir
            ensure_dir(self.download_dir)

        downloaded_files = []

        try:
            # 获取所有讲座文件
            files = await self.get_course_files(
                page, course_code, file_type="lecture", download=False
            )

            for file_info in files:
                # 检查是否需要下载
                if lecture_nums:
                    # 提取讲座编号
                    match = re.search(r"[Ll]ect(?:ure)?\s*(\d+)", file_info["name"])
                    if not match:
                        continue
                    lect_num = int(match.group(1))
                    if lect_num not in lecture_nums:
                        continue

                # 下载文件
                local_path = await self.download_file(
                    page, url=file_info["url"], filename=file_info["name"]
                )
                if local_path:
                    downloaded_files.append(local_path)

            log_message(f"已下载 {len(downloaded_files)} 个讲座文件")
            return downloaded_files

        except Exception as e:
            log_message(f"下载讲座文件失败: {e}", "ERROR")
            return []

    async def download_all_course_materials(
        self,
        page: Page,
        course_code: str,
        output_dir: Path = None,
    ) -> Dict[str, List[Path]]:
        """
        下载课程所有材料

        Returns:
            {type: [file_paths]}
        """
        if output_dir:
            self.download_dir = output_dir
            ensure_dir(self.download_dir)

        result = {"lectures": [], "tutorials": [], "others": []}

        try:
            files = await self.get_course_files(
                page, course_code, file_type="all", download=False
            )

            for file_info in files:
                local_path = await self.download_file(
                    page, url=file_info["url"], filename=file_info["name"]
                )
                if local_path:
                    if file_info["type"] == "lecture":
                        result["lectures"].append(local_path)
                    elif file_info["type"] == "tutorial":
                        result["tutorials"].append(local_path)
                    else:
                        result["others"].append(local_path)

            return result

        except Exception as e:
            log_message(f"下载课程材料失败: {e}", "ERROR")
            return result

    async def get_files_from_dashboard(
        self,
        page: Page,
        course_code: str = None,
        file_type: str = "all",
    ) -> List[Dict]:
        """
        从 Dashboard 页面直接提取文件链接

        Args:
            page: 已在 Dashboard 页面的 Page
            course_code: 课程代码过滤（可选）
            file_type: 文件类型 (lecture, tutorial, all)

        Returns:
            文件列表 [{name, url, course, type}]
        """
        files = []

        try:
            # 确保在 Dashboard 页面
            if "dashboard" not in page.url:
                await page.goto(
                    "https://ole.hkmu.edu.hk/dashboard/index.html", timeout=15000
                )
                await page.wait_for_load_state("networkidle", timeout=10000)

            # 等待 AJAX 内容加载
            await asyncio.sleep(3)

            # 查找所有文件下载链接
            # 链接格式: .../course2600/LCE108F.nsf/.../$File/Lesson%20EIGHT.pptx
            file_links = await page.query_selector_all(
                'a[href*="$File"]'
            )
            log_message(f"找到 {len(file_links)} 个包含 $File 的链接")

            for link in file_links:
                try:
                    href = await link.get_attribute("href") or ""
                    text = await link.inner_text()

                    log_message(f"检查链接: {text[:30]}... -> {href[:60]}...")

                    if not href or not text:
                        continue

                    # 跳过非文件链接
                    if not any(ext in href.lower() for ext in [".pptx", ".ppt", ".pdf", ".doc", ".docx", ".zip", ".rar", ".xlsx", ".xls"]):
                        log_message(f"跳过非文件链接: {href[:50]}")
                        continue

                    # 从 URL 提取课程代码 - 支持带空格的格式如 "IT 1030SEF"
                    course_match = re.search(r"/([A-Z]+\s*\d+[A-Z]*)\.nsf", href, re.IGNORECASE)
                    link_course = course_match.group(1).replace(" ", "").upper() if course_match else ""
                    log_message(f"提取课程代码: '{link_course}' from href")

                    # 过滤课程
                    if course_code and link_course != course_code.replace(" ", "").upper():
                        log_message(f"课程不匹配: {link_course} != {course_code}")
                        continue

                    # 确定文件类型
                    detected_type = "other"
                    text_lower = text.lower()
                    if "lecture" in text_lower or "lect" in text_lower:
                        detected_type = "lecture"
                    elif "tutorial" in text_lower or "tut" in text_lower:
                        detected_type = "tutorial"
                    elif "assignment" in text_lower:
                        detected_type = "assignment"

                    # 过滤文件类型
                    if file_type != "all" and detected_type != file_type:
                        continue

                    files.append({
                        "name": text.strip(),
                        "url": href if href.startswith("http") else f"https://ole.hkmu.edu.hk{href}",
                        "course": link_course,
                        "type": detected_type,
                    })

                except Exception:
                    continue

            log_message(f"从 Dashboard 找到 {len(files)} 个文件")
            return files

        except Exception as e:
            log_message(f"从 Dashboard 提取文件失败: {e}", "ERROR")
            return []

    async def get_tiledata_files(
        self,
        page: Page,
        course_code: str,
        file_type: str = "all",
    ) -> List[Dict]:
        """
        从课程页面 Playwright frame 中提取 TileData（保留作为备用）

        Args:
            page: 已导航到课程页面的 Page
            course_code: 课程代码
            file_type: 文件类型

        Returns:
            文件列表 [{name, url, type}]
        """
        try:
            # 遍历所有 frame 查找 TileData
            for frame in page.frames:
                try:
                    html = await frame.evaluate("() => document.body.innerHTML")
                    files = self._extract_tiledata_from_html(html, course_code, file_type)
                    if files:
                        return files
                except Exception:
                    continue

            # fallback: 从所有 frame 提取 $File 链接
            return await self._extract_file_links_from_frames(page, course_code, file_type)

        except Exception as e:
            log_message(f"get_tiledata_files 失败: {e}", "ERROR")
            return []

    async def _extract_file_links_from_frames(
        self, page: Page, course_code: str, file_type: str = "all"
    ) -> List[Dict]:
        """从课程页面的所有 frame 中提取 $File 链接"""
        files = []
        seen_urls = set()

        for frame in page.frames:
            try:
                file_links = await frame.query_selector_all('a[href*="$File"]')
                for link in file_links:
                    try:
                        href = await link.get_attribute("href") or ""
                        text = await link.inner_text()
                        if not href or not text:
                            continue
                        if not href.startswith("http"):
                            href = f"https://ole.hkmu.edu.hk{href}"
                        if href in seen_urls:
                            continue
                        seen_urls.add(href)
                        if not any(ext in href.lower() for ext in [".pptx", ".ppt", ".pdf", ".doc", ".docx", ".zip", ".rar", ".xlsx"]):
                            continue
                        text_lower = text.lower()
                        detected_type = "other"
                        if "lecture" in text_lower or "lect" in text_lower:
                            detected_type = "lecture"
                        elif "tutorial" in text_lower or "tut" in text_lower:
                            detected_type = "tutorial"
                        elif "assignment" in text_lower:
                            detected_type = "assignment"
                        if file_type != "all" and detected_type != file_type:
                            continue
                        files.append({"name": text.strip(), "url": href, "type": detected_type, "course": course_code})
                    except Exception:
                        continue
            except Exception:
                continue

        log_message(f"从 frame 链接提取到 {len(files)} 个文件")
        return files

    async def _fetch_course_files(
        self,
        page: Page,
        course_code: str,
        file_type: str = "all",
        file_name: str = None,
    ) -> dict:
        """
        从课程页面获取文件列表（httpx + cookies）。

        返回 {"files": [...], "cookie_str": ..., "headers": ..., "error": ...}
        files 为空时 error 字段说明原因。
        """
        cookies_list = await page.context.cookies()
        cookie_dict = {c["name"]: c["value"] for c in cookies_list}
        ltpa_token = cookie_dict.get("LtpaToken", "")

        if not ltpa_token:
            log_message("未找到 LtpaToken cookie，可能未登录")
            return {"files": [], "error": "未登录或 session 过期"}

        cookie_str = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
        log_message(f"获取到 cookies: LtpaToken={ltpa_token[:20]}...")

        import httpx
        course_lower = course_code.lower()
        ft_main_url = f"https://ole.hkmu.edu.hk/course2600/{course_lower}.nsf/ft_main?ReadForm&"

        headers = {
            "Cookie": cookie_str,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": f"https://ole.hkmu.edu.hk/course2600/{course_code}.nsf",
        }

        log_message(f"请求 ft_main: {ft_main_url}")

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(ft_main_url, headers=headers)
            log_message(f"ft_main 响应: {resp.status_code}, 长度: {len(resp.text)}")

            if resp.status_code != 200:
                return {"files": [], "error": f"ft_main 返回 HTTP {resp.status_code}"}

            debug_path = PROJECT_ROOT / "logs" / "ft_main_debug.html"
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            debug_path.write_text(resp.text, encoding="utf-8")

            all_files = self._extract_tiledata_from_html(resp.text, course_code, file_type)

        if not all_files:
            return {"files": [], "error": f"课程 {course_code} 未找到可下载的文件"}

        # 按 file_name 关键词过滤
        if file_name:
            keyword = file_name.lower().strip()
            matched = [f for f in all_files if keyword in f["name"].lower()]
            if matched:
                log_message(f"file_name 过滤: '{file_name}' 匹配到 {len(matched)}/{len(all_files)} 个文件")
                all_files = matched
            else:
                log_message(f"file_name 过滤: '{file_name}' 未匹配到任何文件")
                return {
                    "files": all_files,
                    "unmatched": True,
                    "cookie_str": cookie_str,
                    "headers": headers,
                }

        return {"files": all_files, "cookie_str": cookie_str, "headers": headers}

    async def list_files_from_course_page(
        self,
        page: Page,
        course_code: str,
        file_type: str = "all",
    ) -> dict:
        """列出课程页面文件（不下载），供 get_course_materials 使用"""
        result = await self._fetch_course_files(page, course_code, file_type)
        files = result.get("files", [])
        if result.get("error") and not files:
            return {"error": result["error"], "files": [], "total": 0}

        # 分类统计
        stats = {"lecture": 0, "tutorial": 0, "assignment": 0, "other": 0}
        for f in files:
            stats[f.get("type", "other")] += 1

        return {
            "files": [{"name": f["name"], "type": f["type"], "tile": f.get("tile", "")} for f in files],
            "total": len(files),
            "stats": stats,
            "course_code": course_code,
        }

    async def search_course_info(
        self,
        page: Page,
        course_code: str,
        query: str,
    ) -> dict:
        """从课程 TileData 按关键词搜索信息（日程 + 文件名）

        复用 _fetch_course_files 的 cookie/httpx 流程，
        但提取全部 TileData 项（含非文件的日程/公告）。
        """
        cookies_list = await page.context.cookies()
        cookie_dict = {c["name"]: c["value"] for c in cookies_list}
        ltpa_token = cookie_dict.get("LtpaToken", "")

        if not ltpa_token:
            return {"error": "未登录或 session 过期", "results": []}

        cookie_str = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
        import httpx
        course_lower = course_code.lower()
        ft_main_url = f"https://ole.hkmu.edu.hk/course2600/{course_lower}.nsf/ft_main?ReadForm&"

        headers = {
            "Cookie": cookie_str,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": f"https://ole.hkmu.edu.hk/course2600/{course_code}.nsf",
        }

        log_message(f"search_course_info 请求 ft_main: {ft_main_url}")

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(ft_main_url, headers=headers)
            if resp.status_code != 200:
                return {"error": f"ft_main 返回 HTTP {resp.status_code}", "results": []}

            # 提取全部项（含非文件）
            all_items = self._extract_tiledata_from_html(
                resp.text, course_code, file_type="all", include_non_file=True
            )

        if not all_items:
            return {"results": [], "total": 0, "message": f"课程 {course_code} 无可用数据"}

        # 按关键词搜索
        keywords = [k.strip().lower() for k in query.split() if k.strip()]
        scored = []
        for item in all_items:
            name_lower = item["name"].lower()
            match_count = sum(1 for k in keywords if k in name_lower)
            if match_count > 0:
                scored.append((match_count, item))

        scored.sort(key=lambda x: -x[0])
        matched = [item for _, item in scored]

        # 分离日程项和文件项
        events = [i for i in matched if not i.get("is_file", True)]
        files = [i for i in matched if i.get("is_file", True)]

        result = {
            "course_code": course_code,
            "query": query,
            "total_items": len(all_items),
            "matched_events": [{"name": e["name"], "tile": e["tile"]} for e in events],
            "matched_files": [{"name": f["name"], "type": f["type"], "tile": f["tile"]} for f in files],
        }

        # 也列出全部日程项（供参考）
        all_events = [i for i in all_items if not i.get("is_file", True)]
        if all_events:
            result["all_events"] = [{"name": e["name"], "tile": e["tile"]} for e in all_events]

        return result

    async def download_from_course_page(
        self,
        page: Page,
        course_code: str,
        file_type: str = "all",
        file_name: str = None,
        max_files: int = 1,
        output_dir: Path = None,
    ) -> dict:
        """
        从课程页面下载文件（httpx + cookies）

        Args:
            page: Page 对象（用于获取 cookies）
            course_code: 课程代码
            file_type: 文件类型
            file_name: 文件名关键词，模糊匹配（如 "lecture 5"）
            max_files: 最大下载数量，默认 1
            output_dir: 输出目录（会在其下建 course_code/ 子目录）

        Returns:
            {"downloaded": [...], "available": [...], "total_available": int}
        """
        # 按课程建子目录
        base_dir = output_dir or (PROJECT_ROOT / "downloads")
        self.download_dir = base_dir / course_code
        ensure_dir(self.download_dir)

        try:
            result = await self._fetch_course_files(page, course_code, file_type, file_name)
            all_files = result.get("files", [])

            if not all_files:
                return {
                    "downloaded": [],
                    "available": [],
                    "total_available": 0,
                    "message": result.get("error", f"课程 {course_code} 未找到可下载的文件"),
                }

            if result.get("unmatched"):
                return {
                    "downloaded": [],
                    "available": [f["name"] for f in all_files],
                    "total_available": len(all_files),
                    "message": f"未找到包含 '{file_name}' 的文件，共 {len(all_files)} 个文件可用",
                }

            cookie_str = result["cookie_str"]
            headers = result["headers"]

            # 下载文件
            import httpx
            to_download = all_files[:max_files]
            downloaded = []

            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                for i, file_info in enumerate(to_download):
                    log_message(f"正在下载 ({i+1}/{len(to_download)}): {file_info['name']}")
                    try:
                        dl_resp = await client.get(file_info["url"], headers=headers)
                        if dl_resp.status_code == 200:
                            safe_name = self._safe_filename(file_info["name"], file_info["url"])
                            save_path = self.download_dir / safe_name
                            save_path.write_bytes(dl_resp.content)
                            downloaded.append({"name": file_info["name"], "path": str(save_path)})
                            log_message(f"已下载: {save_path}")
                        else:
                            log_message(f"下载失败 HTTP {dl_resp.status_code}: {file_info['name']}")
                    except Exception as e:
                        log_message(f"下载异常: {file_info['name']} - {e}")

            available_names = [f["name"] for f in all_files]
            return {
                "downloaded": downloaded,
                "available": available_names,
                "total_available": len(all_files),
                "message": f"已下载 {len(downloaded)} 个文件到 {self.download_dir}" if downloaded else f"下载失败，共 {len(all_files)} 个文件可用",
            }

        except Exception as e:
            log_message(f"从课程页面下载失败: {e}", "ERROR")
            return {"error": str(e), "downloaded": [], "available": []}

    @staticmethod
    def _safe_filename(label: str, url: str) -> str:
        """从 label + url 生成安全的文件名，确保有正确的扩展名"""
        # 从 URL 的 $FILE/ 之后提取真实文件名
        url_filename = ""
        file_match = re.search(r'\$FILE/(.+)$', url, re.IGNORECASE)
        if file_match:
            url_filename = unquote(file_match.group(1))

        # 确定扩展名：优先从 URL 文件名取
        url_ext = Path(url_filename).suffix if url_filename else ""

        # 清理 label 中的非法字符
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', label)

        # 如果 label 已有扩展名就用 label 的
        if Path(safe_name).suffix:
            return safe_name

        # 否则从 URL 文件名拼接扩展名
        if url_ext:
            return safe_name + url_ext

        # fallback: 如果 URL 文件名有内容，直接用它
        if url_filename:
            return re.sub(r'[\\/:*?"<>|]', '_', url_filename)

        return safe_name


    def _extract_tiledata_from_html(
        self, html: str, course_code: str, file_type: str = "all",
        include_non_file: bool = False,
    ) -> List[Dict]:
        """从 ft_main HTML 中提取 TileData（week tiles 嵌套 items 结构）

        Args:
            include_non_file: True 时也返回 type:lbl 的日程/公告项（无下载链接）
        """
        files = []
        seen = set()

        # 提取 TileData JSON
        match = re.search(r'TileData\s*=\s*(\[[\s\S]*?\]);', html)
        if not match:
            log_message(f"HTML 中未找到 TileData (长度 {len(html)})")
            return self._extract_file_links_from_html(html, course_code, file_type)

        try:
            tile_data = json.loads(match.group(1))
        except json.JSONDecodeError as e:
            log_message(f"TileData JSON 解析失败: {e}")
            return self._extract_file_links_from_html(html, course_code, file_type)

        base_url = f"https://ole.hkmu.edu.hk/course2600/{course_code}.nsf"

        # TileData 结构: [{id, title, term, items: [{id, type, lbl, link, show, deny_edit}]}]
        for tile in tile_data:
            tile_title = tile.get("title", "")
            items = tile.get("items", [])

            for item in items:
                item_type = item.get("type", "")
                lbl = item.get("lbl", "").strip()
                link = item.get("link", "").strip()

                if not lbl:
                    continue

                # 非文件项（日程/公告）：只有 include_non_file 时才收集
                if item_type == "lbl" and not link:
                    if include_non_file:
                        seen_key = f"lbl:{lbl}"
                        if seen_key in seen:
                            continue
                        seen.add(seen_key)
                        files.append({
                            "name": lbl,
                            "url": "",
                            "type": "event",
                            "course": course_code,
                            "tile": tile_title,
                            "is_file": False,
                        })
                    continue

                if not link:
                    continue

                if link in seen:
                    continue
                seen.add(link)

                # 文件类型检测
                lbl_lower = lbl.lower()
                detected_type = "other"
                if any(k in lbl_lower for k in ("lecture", "lect", "lec_note")):
                    detected_type = "lecture"
                elif any(k in lbl_lower for k in ("tutorial", "tut", "lab")):
                    detected_type = "tutorial"
                elif "assignment" in lbl_lower:
                    detected_type = "assignment"

                if file_type != "all" and detected_type != file_type:
                    continue

                # 构建完整 URL
                rel_path = link.lstrip("./")
                full_url = f"{base_url}/{rel_path}"

                # 只保留有 $FILE 的下载链接（实际文件）
                if "$FILE" not in full_url and "$File" not in full_url:
                    continue

                files.append({
                    "name": lbl,
                    "url": full_url,
                    "type": detected_type,
                    "course": course_code,
                    "tile": tile_title,
                    "is_file": True,
                })

        log_message(f"从 TileData 提取到 {len(files)} 个文件")
        return files

    def _extract_file_links_from_html(
        self, html: str, course_code: str, file_type: str = "all"
    ) -> List[Dict]:
        """从 HTML 中直接提取 $File 链接作为 fallback"""
        files = []
        seen = set()
        base_url = f"https://ole.hkmu.edu.hk/course2600/{course_code}.nsf"

        # 匹配 href 中的 $File 链接
        for match in re.finditer(r'href=["\']([^"\']*\$File[^"\']*)["\']', html, re.IGNORECASE):
            href = match.group(1)
            if href in seen:
                continue
            seen.add(href)

            # 尝试获取文件名
            name_match = re.search(r'\$File/(.+)$', href)
            name = name_match.group(1) if name_match else href.split("/")[-1]
            # URL decode
            name = unquote(name)

            if not any(ext in href.lower() for ext in [".pptx", ".ppt", ".pdf", ".doc", ".docx", ".zip", ".xlsx"]):
                continue

            full_url = href if href.startswith("http") else f"{base_url}/{href.lstrip('./')}"

            lbl_lower = name.lower()
            detected_type = "other"
            if any(k in lbl_lower for k in ("lecture", "lect", "lec_note")):
                detected_type = "lecture"
            elif any(k in lbl_lower for k in ("tutorial", "tut")):
                detected_type = "tutorial"

            if file_type != "all" and detected_type != file_type:
                continue

            files.append({"name": name, "url": full_url, "type": detected_type, "course": course_code})

        log_message(f"从 HTML 链接提取到 {len(files)} 个文件")
        return files
