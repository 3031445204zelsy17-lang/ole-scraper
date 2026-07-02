#!/usr/bin/env python3
"""命令行入口"""
from .scraper import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
