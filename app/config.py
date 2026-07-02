"""配置入口 — 从环境变量读取 OLE 凭证与 LLM 配置。

- OLE 凭证:OLE_USERNAME / OLE_PASSWORD(登录 HKMU OLE)
- LLM:多 provider(见 llm.py),LLM_PROVIDER + LLM_API_KEY(+ 可选 LLM_BASE_URL/LLM_MODEL)
"""
import os

from .llm import get_llm_config

# OLE 登录凭证
OLE_USERNAME = os.environ.get("OLE_USERNAME", "")
OLE_PASSWORD = os.environ.get("OLE_PASSWORD", "")

# LLM(多 provider,OpenAI 兼容)
LLM_CONFIG = get_llm_config()
