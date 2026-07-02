"""对话历史管理 — 保留最近 N 轮，防止上下文膨胀"""

MAX_HISTORY_PAIRS = 6  # 6 user + 6 assistant = 最多 12 条消息


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

    def _trim(self):
        budget = MAX_HISTORY_PAIRS * 2
        if len(self._messages) > budget:
            self._messages = self._messages[-budget:]
