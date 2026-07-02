"""配置入口 — 从环境变量读取凭证与 API key。

Phase 0:集中 DEEPSEEK_KEY(原寄生在已删除的 agent.py 意图解析模块)。
Phase 1:扩展为多 provider 抽象(base_url / model / key 可配)。
"""
import os

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
