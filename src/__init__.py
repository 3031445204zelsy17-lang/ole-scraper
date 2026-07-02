"""
OLE Scraper - HKMU 学习系统数据抓取工具
"""
from .scraper import OLEScraper
from .auth import OLEAuth

__version__ = "0.3.0"
__all__ = ["OLEScraper", "OLEAuth"]
