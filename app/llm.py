"""LLM 抽象 — 统一 OpenAI 兼容的 Chat Completions 调用。

支持任意 OpenAI 兼容 provider(DeepSeek / GLM / OpenAI / Ollama / 自定义),
通过 .env 配置 LLM_PROVIDER + LLM_API_KEY(+ 可选 LLM_BASE_URL / LLM_MODEL 覆盖)。

预设 provider 的 base_url/model 只是默认值,均可被环境变量覆盖。
"""
import os
import logging

import httpx

log = logging.getLogger("ole-agent")

# 预设 provider:默认 base_url + model。均可被 .env 的 LLM_BASE_URL / LLM_MODEL 覆盖。
_PROVIDERS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "ollama": {  # 本地,需先 ollama pull <model>
        "base_url": "http://localhost:11434/v1",
        "model": "qwen2.5",
    },
}


class LLMConfig:
    """从环境变量解析的 LLM 配置。"""

    def __init__(self):
        provider = os.environ.get("LLM_PROVIDER", "deepseek").strip().lower()
        preset = _PROVIDERS.get(provider, {})

        self.provider = provider
        self.api_key = os.environ.get("LLM_API_KEY", "").strip()
        # 环境变量覆盖 > 预设
        self.base_url = (os.environ.get("LLM_BASE_URL") or preset.get("base_url", "")).strip()
        self.model = (os.environ.get("LLM_MODEL") or preset.get("model", "")).strip()

    @property
    def endpoint(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    @property
    def is_configured(self) -> bool:
        # ollama 本地可不带 key
        return bool(self.base_url and self.model) and (
            bool(self.api_key) or self.provider == "ollama"
        )

    def describe(self) -> str:
        return f"provider={self.provider} model={self.model} base={self.base_url}"


def get_llm_config() -> LLMConfig:
    return LLMConfig()


async def call_llm(
    config: LLMConfig,
    messages: list[dict],
    tools: list[dict] | None = None,
    temperature: float = 0.1,
    timeout: float = 30,
) -> dict:
    """调用 OpenAI 兼容 Chat Completions,返回 choices[0](含 message + finish_reason)。

    Raises:
        向上抛 httpx 请求异常 / HTTPStatusError,由调用方处理。
    """
    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        payload["tools"] = tools

    headers = {"Authorization": f"Bearer {config.api_key}"}
    # ollama 本地若无 key,不带 Authorization(部分版本要求不带)
    if not config.api_key:
        headers = {}

    log.info("LLM call → %s", config.describe())
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(config.endpoint, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]
