"""Scraper 池 — 每个 WebSocket 连接复用一个 scraper 实例，懒加载"""
import asyncio
import sys
import logging
from pathlib import Path

log = logging.getLogger("ole-agent")

_PROJECT_ROOT = str(Path(__file__).parent.parent)


class ScraperPool:
    """持有单个 scraper 实例，首次使用时初始化。"""

    def __init__(self):
        self._scraper = None
        self._lock = asyncio.Lock()

    async def get(self):
        async with self._lock:
            if self._scraper is None:
                if _PROJECT_ROOT not in sys.path:
                    sys.path.insert(0, _PROJECT_ROOT)
                from src.scraper import OLEScraper

                log.info("Initializing scraper for agent session...")
                scraper = OLEScraper(headless=True)
                ok = await scraper.start(use_saved_session=True)
                if not ok:
                    raise RuntimeError("Scraper 登录失败，请检查凭证")
                self._scraper = scraper
                log.info("Scraper initialized successfully")
            return self._scraper

    async def close(self):
        async with self._lock:
            if self._scraper:
                await self._scraper.close()
                self._scraper = None

    @property
    def is_ready(self) -> bool:
        return self._scraper is not None
