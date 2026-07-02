"""
OLE Session 管理
处理 Cookie 持久化和 Session 复用
"""
import json
import pickle
from pathlib import Path
from typing import Optional

from playwright.async_api import BrowserContext, Page

from .helpers import PROJECT_ROOT, log_message


class SessionManager:
    """管理 OLE 登录 Session"""

    def __init__(self, session_dir: Path = None):
        self.session_dir = session_dir or PROJECT_ROOT / "sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.cookies_file = self.session_dir / "ole_cookies.json"
        self.storage_file = self.session_dir / "ole_storage.pkl"

    async def save_cookies(self, context: BrowserContext):
        """保存 Cookies 到文件"""
        cookies = await context.cookies()
        with open(self.cookies_file, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        log_message(f"已保存 {len(cookies)} 个 Cookies")

    async def load_cookies(self, context: BrowserContext) -> bool:
        """从文件加载 Cookies"""
        if not self.cookies_file.exists():
            return False

        try:
            with open(self.cookies_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            log_message(f"已加载 {len(cookies)} 个 Cookies")
            return True
        except Exception as e:
            log_message(f"加载 Cookies 失败: {e}", "ERROR")
            return False

    async def save_storage_state(self, context: BrowserContext):
        """保存完整的存储状态（Cookies + LocalStorage）"""
        storage = await context.storage_state()
        storage_file = self.session_dir / "ole_state.json"
        with open(storage_file, "w", encoding="utf-8") as f:
            json.dump(storage, f, ensure_ascii=False, indent=2)
        log_message("已保存存储状态")

    async def load_storage_state(self, browser) -> Optional[BrowserContext]:
        """加载存储状态创建新的上下文"""
        storage_file = self.session_dir / "ole_state.json"
        if not storage_file.exists():
            return None

        try:
            context = await browser.new_context(storage_state=str(storage_file))
            log_message("已从存储状态恢复会话")
            return context
        except Exception as e:
            log_message(f"加载存储状态失败: {e}", "ERROR")
            return None

    def clear_session(self):
        """清除保存的 Session"""
        for file in self.session_dir.glob("ole_*"):
            file.unlink()
        log_message("已清除所有保存的 Session")

    def has_saved_session(self) -> bool:
        """检查是否有保存的 Session"""
        return self.cookies_file.exists() or (
            self.session_dir / "ole_state.json"
        ).exists()
