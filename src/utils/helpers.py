"""
OLE Scraper 工具函数
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"


def load_config(config_name: str = "selectors.json") -> dict:
    """加载配置文件"""
    config_path = CONFIG_DIR / config_name
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_data(data: dict, filename: str = None) -> Path:
    """保存数据到 JSON 文件"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if filename is None:
        timestamp = datetime.now().strftime("%Y-%m-%d")
        filename = f"ole_data_{timestamp}.json"

    filepath = DATA_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return filepath


def load_env() -> dict:
    """从 .env 文件加载环境变量"""
    env_path = PROJECT_ROOT / ".env"
    env_vars = {}

    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()

    return env_vars


def get_credentials() -> tuple[str, str]:
    """获取登录凭证"""
    env = load_env()
    username = env.get("OLE_USERNAME") or os.environ.get("OLE_USERNAME")
    password = env.get("OLE_PASSWORD") or os.environ.get("OLE_PASSWORD")

    if not username or not password:
        raise ValueError("未找到登录凭证，请检查 .env 文件或环境变量")

    return username, password


def log_message(message: str, level: str = "INFO"):
    """记录日志"""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [{level}] {message}"

    # 打印到控制台
    print(log_line)

    # 写入日志文件
    log_file = LOGS_DIR / f"scraper_{datetime.now().strftime('%Y-%m-%d')}.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_line + "\n")


def format_datetime(dt_str: str) -> str:
    """格式化日期时间字符串"""
    try:
        # 尝试解析各种格式
        for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M"]:
            try:
                dt = datetime.strptime(dt_str, fmt)
                return dt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                continue
        return dt_str
    except Exception:
        return dt_str


def clean_course_code(code: str) -> str:
    """清理课程代码格式"""
    return code.replace(" ", "").replace("\u00a0", "")


def ensure_dir(path: Path) -> Path:
    """确保目录存在"""
    path.mkdir(parents=True, exist_ok=True)
    return path
