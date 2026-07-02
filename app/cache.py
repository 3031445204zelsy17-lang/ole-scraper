"""数据缓存 — JSON 文件 + 过期检查"""
import json
import time
import asyncio
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone

log = logging.getLogger("ole-agent")

DATA_DIR = Path(__file__).parent.parent / "ole-data" / "current"

# 缓存 TTL（秒）：作业 30 分钟，课表 1 小时，课程 2 小时
_TTL = {
    "assignments": 30 * 60,
    "classes": 60 * 60,
    "courses": 120 * 60,
}
_DEFAULT_TTL = 30 * 60


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _is_fresh(data: dict, key: str) -> bool:
    """检查 fetch_time 是否在 TTL 内"""
    fetch_time_str = data.get("fetch_time")
    if not fetch_time_str:
        return False
    try:
        fetch_time = datetime.fromisoformat(fetch_time_str)
        if fetch_time.tzinfo is None:
            fetch_time = fetch_time.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - fetch_time).total_seconds()
        return age < _TTL.get(key, _DEFAULT_TTL)
    except Exception:
        return False


async def _refresh_all():
    """调用 scraper 刷新所有数据"""
    project_root = str(Path(__file__).parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from src.scraper import OLEScraper

    scraper = OLEScraper(headless=True)
    try:
        ok = await scraper.start(use_saved_session=True)
        if not ok:
            return False
        data = await scraper.get_dashboard_data()

        # 保存各文件 — 每个文件只保留对应子集 + 元信息
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        key_to_file = {
            "courses": "courses",
            "assignments": "assignments",
            "upcoming_classes": "classes",
        }
        meta = {k: v for k, v in data.items() if k in ("fetch_time", "source")}
        for key, filename in key_to_file.items():
            subset = data.get(key, [])
            payload = {**meta, key: subset}
            filepath = DATA_DIR / f"{filename}.json"
            filepath.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return True
    except Exception:
        log.warning("Scraper refresh failed", exc_info=True)
        return False
    finally:
        await scraper.close()


async def get_cached(key: str) -> dict:
    """获取缓存数据，过期则刷新

    Args:
        key: "courses" | "assignments" | "classes"

    Returns:
        解析后的 JSON dict，失败返回空 dict
    """
    filename = {
        "courses": "courses",
        "assignments": "assignments",
        "classes": "classes",
    }.get(key, key)

    data = _read_json(DATA_DIR / f"{filename}.json")

    if data and _is_fresh(data, filename):
        return data

    # 过期或不存在，尝试刷新
    refreshed = await _refresh_all()
    if refreshed:
        data = _read_json(DATA_DIR / f"{filename}.json")

    return data or {}
