"""对话历史管理 — 保留最近 N 轮，防止上下文膨胀"""

MAX_HISTORY_PAIRS = 12  # 12 user + 12 assistant = 最多 24 条(轻量版,后续可升级摘要/检索)


class ConversationHistory:
    def __init__(self):
        self._messages: list[dict] = []

    def add(self, role: str, content: str):
        self._messages.append({"role": role, "content": content})
        self._trim()

    def get_for_prompt(self) -> list[dict]:
        return list(self._messages)

    def clear(self):
        self._messages.clear()

    def load(self, messages: list[dict]):
        """从外部加载历史(前端 localStorage 恢复),过滤无效条目并裁剪到窗口。"""
        self._messages = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
        self._trim()

    def _trim(self):
        budget = MAX_HISTORY_PAIRS * 2
        if len(self._messages) > budget:
            self._messages = self._messages[-budget:]
