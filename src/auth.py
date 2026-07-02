"""
OLE 登录认证模块
"""
from playwright.async_api import Page, BrowserContext, Browser
from typing import Optional

from .utils.helpers import load_config, get_credentials, log_message
from .utils.session import SessionManager


class OLEAuth:
    """OLE 登录认证"""

    def __init__(self):
        self.config = load_config()
        self.login_config = self.config.get("login", {})
        self.session_manager = SessionManager()

    async def login(
        self,
        page: Page,
        username: str = None,
        password: str = None,
        use_saved_session: bool = True,
    ) -> bool:
        """
        执行登录

        Args:
            page: Playwright Page 对象
            username: 用户名（可选，默认从 .env 读取）
            password: 密码（可选，默认从 .env 读取）
            use_saved_session: 是否使用保存的 Session

        Returns:
            登录是否成功
        """
        if username is None or password is None:
            username, password = get_credentials()

        login_url = self.login_config.get("url", "https://ole.hkmu.edu.hk/")
        redirect_url = self.login_config.get(
            "redirect_after_login", "https://ole.hkmu.edu.hk/dashboard/index.html"
        )

        log_message(f"正在访问登录页面: {login_url}")
        await page.goto(login_url)

        # 检查是否已经登录
        if page.url.startswith(redirect_url.rsplit("/", 1)[0]):
            log_message("已经登录，跳过登录步骤")
            return True

        # 等待登录表单加载
        await page.wait_for_selector(
            self.login_config.get("username_input", "input[name='Username']"),
            timeout=10000,
        )

        # 填写用户名
        username_selector = self.login_config.get(
            "username_input", "input[name='Username']"
        )
        await page.fill(username_selector, username)
        log_message("已填写用户名")

        # 填写密码
        password_selector = self.login_config.get(
            "password_input", "input[name='Password']"
        )
        await page.fill(password_selector, password)
        log_message("已填写密码")

        # 提交登录 - 尝试多种方式
        login_button = self.login_config.get("login_button", "a:has-text('Login')")

        try:
            # 方式1: 按 Enter 键提交
            await page.press(password_selector, "Enter")
            log_message("已按 Enter 提交")
        except Exception:
            try:
                # 方式2: 点击登录按钮
                await page.click(login_button, timeout=5000)
                log_message("已点击登录按钮")
            except Exception:
                # 方式3: 点击任何可点击的登录元素
                await page.click("button:has-text('Login'), a:has-text('Login'), input[type='submit']", timeout=5000)
                log_message("已点击登录元素")

        # 等待跳转 - OLE 登录后会先跳转到 myNavigator，再到 dashboard
        try:
            # 等待离开登录页面
            await page.wait_for_url("**/myNavigator**", timeout=15000)
            log_message("已跳转到 myNavigator")

            # 直接导航到 dashboard
            await page.goto(
                "https://ole.hkmu.edu.hk/dashboard/index.html", timeout=15000
            )
            await page.wait_for_load_state("networkidle", timeout=10000)
            log_message("登录成功！")
            return True
        except Exception as e:
            # 检查是否已经在 dashboard
            if "dashboard" in page.url:
                log_message("登录成功！")
                return True
            log_message(f"登录失败: {e}", "ERROR")
            return False

    async def login_with_context(
        self,
        browser: Browser,
        username: str = None,
        password: str = None,
        use_saved_session: bool = True,
    ) -> tuple[BrowserContext, Page, bool]:
        """
        使用 Context 登录，支持 Session 复用

        Returns:
            (context, page, is_new_login)
        """
        context = None
        is_new_login = False

        # 尝试加载保存的 Session
        if use_saved_session:
            context = await self.session_manager.load_storage_state(browser)
            if context:
                page = await context.new_page()
                await page.goto(
                    "https://ole.hkmu.edu.hk/dashboard/index.html", timeout=15000
                )
                # 验证 Session 是否有效
                if page.url.startswith("https://ole.hkmu.edu.hk/dashboard"):
                    log_message("使用保存的 Session 登录成功")
                    return context, page, False
                else:
                    log_message("保存的 Session 已过期", "WARN")
                    await context.close()
                    context = None

        # 创建新的 Context 并登录
        if context is None:
            context = await browser.new_context()
            page = await context.new_page()

            success = await self.login(page, username, password)
            if success:
                # 保存 Session
                await self.session_manager.save_storage_state(context)
                is_new_login = True
            else:
                await context.close()
                return None, None, False

        return context, page, is_new_login

    async def check_login_status(self, page: Page) -> bool:
        """检查当前登录状态"""
        try:
            await page.goto(
                "https://ole.hkmu.edu.hk/dashboard/index.html", timeout=10000
            )
            return page.url.startswith("https://ole.hkmu.edu.hk/dashboard")
        except Exception:
            return False

    async def logout(self, page: Page):
        """登出"""
        try:
            # 查找并点击登出按钮
            await page.click("a:has-text('Logout'), a:has-text('登出')")
            log_message("已登出")
        except Exception as e:
            log_message(f"登出失败: {e}", "WARN")
