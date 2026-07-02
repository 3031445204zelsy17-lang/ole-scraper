#!/usr/bin/env python3
"""
OLE Scraper 主程序
用法:
    python -m src.scraper [command] [options]

命令:
    courses     获取课程列表
    assignments 获取作业信息
    classes     获取即将上课信息
    all         获取所有信息
    download    下载课程文件
    login       测试登录
"""
import asyncio
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from .auth import OLEAuth
from .actions.courses import CoursesExtractor
from .actions.assignments import AssignmentsExtractor
from .actions.grades import GradesExtractor
from .actions.calendar import CalendarExtractor
from .actions.downloads import DownloadsManager
from .utils.helpers import (
    load_config,
    save_data,
    log_message,
    get_credentials,
    ensure_dir,
    PROJECT_ROOT,
)


class OLEScraper:
    """OLE 数据抓取器"""

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        self.auth = OLEAuth()
        self.courses = CoursesExtractor()
        self.assignments = AssignmentsExtractor()
        self.grades = GradesExtractor()
        self.calendar = CalendarExtractor()
        self.downloads = DownloadsManager()

    async def start(self, use_saved_session: bool = True) -> bool:
        """启动浏览器并登录"""
        playwright = await async_playwright().start()

        self.browser = await playwright.chromium.launch(headless=self.headless)

        # 尝试使用保存的 Session
        self.context, self.page, is_new_login = await self.auth.login_with_context(
            self.browser, use_saved_session=use_saved_session
        )

        if self.context is None:
            log_message("启动失败：无法登录", "ERROR")
            return False

        return True

    async def close(self):
        """关闭浏览器"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()

    async def get_dashboard_data(self) -> dict:
        """获取 Dashboard 所有数据"""
        data = {
            "fetch_time": datetime.now().isoformat(),
            "source": "https://ole.hkmu.edu.hk/dashboard/index.html",
        }

        # 确保在 Dashboard 页面
        await self.page.goto(
            "https://ole.hkmu.edu.hk/dashboard/index.html", timeout=15000
        )
        await self.page.wait_for_load_state("networkidle", timeout=10000)

        # 获取课程列表
        log_message("正在获取课程列表...")
        data["courses"] = await self.courses.get_courses_from_dashboard(self.page)

        # 获取即将上课
        log_message("正在获取即将上课信息...")
        data["upcoming_classes"] = await self.calendar.get_upcoming_classes(self.page)

        # 获取作业
        log_message("正在获取作业信息...")
        data["assignments"] = await self.assignments.get_assignments_from_dashboard(
            self.page
        )

        return data

    async def fetch_all(self, save: bool = True) -> dict:
        """获取所有数据"""
        data = await self.get_dashboard_data()

        if save:
            filepath = save_data(data)
            log_message(f"数据已保存到: {filepath}")

        return data

    async def fetch_courses(self, save: bool = True) -> list:
        """获取课程列表"""
        await self.page.goto(
            "https://ole.hkmu.edu.hk/dashboard/index.html", timeout=15000
        )
        courses = await self.courses.get_courses_from_dashboard(self.page)

        if save:
            data = {
                "fetch_time": datetime.now().isoformat(),
                "courses": courses,
            }
            save_data(data, f"courses_{datetime.now().strftime('%Y-%m-%d')}.json")

        return courses

    async def fetch_assignments(self, save: bool = True) -> list:
        """获取作业信息"""
        await self.page.goto(
            "https://ole.hkmu.edu.hk/dashboard/index.html", timeout=15000
        )
        assignments = await self.assignments.get_assignments_from_dashboard(self.page)

        if save:
            data = {
                "fetch_time": datetime.now().isoformat(),
                "assignments": assignments,
            }
            save_data(
                data, f"assignments_{datetime.now().strftime('%Y-%m-%d')}.json"
            )

        return assignments

    async def fetch_classes(self, save: bool = True) -> list:
        """获取即将上课信息"""
        await self.page.goto(
            "https://ole.hkmu.edu.hk/dashboard/index.html", timeout=15000
        )
        classes = await self.calendar.get_upcoming_classes(self.page)

        if save:
            data = {
                "fetch_time": datetime.now().isoformat(),
                "upcoming_classes": classes,
            }
            save_data(data, f"classes_{datetime.now().strftime('%Y-%m-%d')}.json")

        return classes

    async def download_course_files(
        self,
        course_code: str = None,
        file_type: str = "all",
        output_dir: Path = None,
    ) -> dict:
        """
        下载课程文件

        Args:
            course_code: 课程代码（None 表示下载所有可见文件）
            file_type: 文件类型 (lecture, tutorial, all)
            output_dir: 输出目录

        Returns:
            下载结果
        """
        # 先导航到 Dashboard
        await self.page.goto(
            "https://ole.hkmu.edu.hk/dashboard/index.html", timeout=15000
        )
        await self.page.wait_for_load_state("networkidle", timeout=10000)

        # 使用 Dashboard 方法下载文件
        downloaded = await self.downloads.download_from_dashboard(
            self.page,
            course_code=course_code,  # 可以为 None
            file_type=file_type,
            output_dir=output_dir,
            max_files=20,
        )

        if not downloaded:
            return {"success": False, "message": "未找到文件", "files": []}

        return {
            "success": True,
            "total": len(downloaded),
            "downloaded": len(downloaded),
            "files": [
                {"name": f.name, "local_path": str(f)} for f in downloaded
            ],
        }


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="OLE Scraper - HKMU 学习系统数据抓取工具"
    )
    parser.add_argument(
        "command",
        choices=["courses", "assignments", "classes", "all", "download", "login"],
        help="要执行的命令",
    )
    parser.add_argument(
        "--course",
        "-c",
        help="课程代码（用于 download 命令）",
    )
    parser.add_argument(
        "--type",
        "-t",
        choices=["lecture", "tutorial", "all"],
        default="all",
        help="文件类型（用于 download 命令）",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="输出目录（用于 download 命令）",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="不保存数据到文件",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="无头模式运行（不显示浏览器窗口）",
    )
    parser.add_argument(
        "--new-session",
        action="store_true",
        help="不使用保存的 Session，重新登录",
    )

    args = parser.parse_args()

    # 创建 Scraper 实例
    scraper = OLEScraper(headless=args.headless)

    try:
        # 启动并登录
        log_message("正在启动...")
        success = await scraper.start(use_saved_session=not args.new_session)

        if not success:
            print("❌ 启动失败")
            sys.exit(1)

        log_message("✅ 登录成功")

        # 执行命令
        if args.command == "login":
            print("✅ 登录测试成功")

        elif args.command == "all":
            data = await scraper.fetch_all(save=not args.no_save)
            print(json.dumps(data, ensure_ascii=False, indent=2))

        elif args.command == "courses":
            courses = await scraper.fetch_courses(save=not args.no_save)
            print(f"\n📚 课程列表 ({len(courses)} 门):\n")
            for course in courses:
                print(f"  • {course['code']}: {course['name']}")

        elif args.command == "assignments":
            assignments = await scraper.fetch_assignments(save=not args.no_save)
            print(f"\n📝 作业列表 ({len(assignments)} 个):\n")
            for a in assignments:
                print(f"  • [{a['course']}] {a['title']}")
                print(f"    截止: {a['deadline']}")

        elif args.command == "classes":
            classes = await scraper.fetch_classes(save=not args.no_save)
            print(f"\n📅 即将上课 ({len(classes)} 节):\n")
            for c in classes:
                print(f"  • {c['course']} - {c['type']}")
                print(f"    时间: {c['time']} | 地点: {c['location']}")

        elif args.command == "download":
            output_dir = Path(args.output) if args.output else None
            if args.course:
                print(f"📥 下载课程 {args.course} 的文件...")
            else:
                print("📥 下载所有可见文件...")

            result = await scraper.download_course_files(
                args.course,
                file_type=args.type,
                output_dir=output_dir,
            )

            if result["success"]:
                print(
                    f"\n📥 下载完成: {result['downloaded']}/{result['total']} 个文件\n"
                )
                for f in result["files"]:
                    print(f"  ✓ {f['name']} -> {f['local_path']}")
            else:
                print(f"❌ {result['message']}")

    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(main())
