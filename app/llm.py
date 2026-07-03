"""LLM 抽象 — 统一 OpenAI 兼容的 Chat Completions 调用。

支持任意 OpenAI 兼容 provider(DeepSeek / GLM / OpenAI / Ollama / 自定义),
通过 .env 配置 LLM_PROVIDER + LLM_API_KEY(+ 可选 LLM_BASE_URL / LLM_MODEL 覆盖)。

预设 provider 的 base_url/model 只是默认值,均可被环境变量覆盖。
"""
import json
import os
import asyncio
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


_RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


async def call_llm(
    config: LLMConfig,
    messages: list[dict],
    tools: list[dict] | None = None,
    temperature: float = 0.1,
    timeout: float = 30,
    max_retries: int = 3,
) -> dict:
    """调用 OpenAI 兼容 Chat Completions,返回 choices[0](含 message + finish_reason)。

    可重试错误(连接 / 超时 / 429 / 5xx)指数退避重试 max_retries 次;
    不可重试(如 401 鉴权失败、其他 4xx)直接向上抛。
    """
    payload = {"model": config.model, "messages": messages, "temperature": temperature}
    if tools:
        payload["tools"] = tools

    headers = {"Authorization": f"Bearer {config.api_key}"}
    # ollama 本地若无 key,不带 Authorization(部分版本要求不带)
    if not config.api_key:
        headers = {}

    log.info("LLM call → %s", config.describe())
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(config.endpoint, headers=headers, json=payload)
                resp.raise_for_status()
                return resp.json()["choices"][0]
        except httpx.HTTPStatusError as e:
            if e.response.status_code in _RETRYABLE_STATUS and attempt < max_retries:
                wait = 2 ** attempt
                log.warning("LLM HTTP %d,%.1fs 后重试(%d/%d)", e.response.status_code, wait, attempt + 1, max_retries)
                await asyncio.sleep(wait)
                last_exc = e
                continue
            raise
        except (httpx.TimeoutException, httpx.TransportError) as e:
            if attempt < max_retries:
                wait = 2 ** attempt
                log.warning("LLM 网络错误 %s,%.1fs 后重试(%d/%d)", type(e).__name__, wait, attempt + 1, max_retries)
                await asyncio.sleep(wait)
                last_exc = e
                continue
            raise
    raise last_exc  # type: ignore[misc]


async def call_llm_stream(
    config: LLMConfig,
    messages: list[dict],
    tools: list[dict] | None = None,
    temperature: float = 0.1,
    timeout: float = 30,
    max_retries: int = 3,
    on_delta=None,
) -> tuple[dict, str]:
    """流式调用 OpenAI 兼容 Chat Completions(SSE)。

    on_delta(text) 实时推送 content 增量;返回 (assistant_msg, finish_reason)。
    assistant_msg 结构与非流式 choice["message"] 一致(role/content/tool_calls),
    流式分片到达的 tool_calls.arguments 已按 index 拼接完整。

    连接级重试(流开始前):连接/超时/429/5xx 退避重试 max_retries 次;
    流一旦开始(已推 delta)则不重试,中途异常向上抛。
    """
    payload = {"model": config.model, "messages": messages, "temperature": temperature, "stream": True}
    if tools:
        payload["tools"] = tools
    headers = {"Authorization": f"Bearer {config.api_key}"}
    if not config.api_key:
        headers = {}

    log.info("LLM stream → %s", config.describe())
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        started = False
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", config.endpoint, headers=headers, json=payload) as resp:
                    resp.raise_for_status()
                    started = True
                    content_parts: list[str] = []
                    tc_map: dict = {}
                    finish_reason = None
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choice = (chunk.get("choices") or [{}])[0]
                        delta = choice.get("delta") or {}
                        c = delta.get("content")
                        if c:
                            content_parts.append(c)
                            if on_delta:
                                await on_delta(c)
                        for tc in delta.get("tool_calls") or []:
                            idx = tc.get("index", 0)
                            slot = tc_map.setdefault(idx, {"id": None, "name": None, "arguments": []})
                            if tc.get("id"):
                                slot["id"] = tc["id"]
                            fn = tc.get("function") or {}
                            if fn.get("name"):
                                slot["name"] = fn["name"]
                            if fn.get("arguments"):
                                slot["arguments"].append(fn["arguments"])
                        if choice.get("finish_reason"):
                            finish_reason = choice["finish_reason"]
                    assistant_msg = {"role": "assistant", "content": "".join(content_parts)}
                    if tc_map:
                        assistant_msg["tool_calls"] = [
                            {"id": s["id"], "type": "function",
                             "function": {"name": s["name"], "arguments": "".join(s["arguments"])}}
                            for _, s in sorted(tc_map.items())
                        ]
                    return assistant_msg, finish_reason or "stop"
        except httpx.HTTPStatusError as e:
            if not started and e.response.status_code in _RETRYABLE_STATUS and attempt < max_retries:
                wait = 2 ** attempt
                log.warning("LLM stream HTTP %d,%.1fs 后重试(%d/%d)", e.response.status_code, wait, attempt + 1, max_retries)
                await asyncio.sleep(wait)
                last_exc = e
                continue
            raise
        except (httpx.TimeoutException, httpx.TransportError) as e:
            if not started and attempt < max_retries:
                wait = 2 ** attempt
                log.warning("LLM stream 网络错误 %s,%.1fs 后重试(%d/%d)", type(e).__name__, wait, attempt + 1, max_retries)
                await asyncio.sleep(wait)
                last_exc = e
                continue
            raise
    raise last_exc  # type: ignore[misc]
