import os
import json
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .config import LLM_CONFIG
from .scraper_pool import ScraperPool
from .conversation import ConversationHistory
from .tool_executor import ToolExecutor
from .agent_loop import run_agent_loop

log = logging.getLogger("ole-agent")

PROJECT_ROOT = Path(__file__).parent.parent

app = FastAPI(title="OLE Agent")


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── 帮助文本 ──────────────────────────────────────────────

_INTENT_HELP = (
    "你好！你可以问我：\n"
    "  • 课程 — 查看课程列表\n"
    "  • 作业 — 查看待交作业\n"
    "  • 课表 — 查看即将上课\n"
    "  • 成绩 — 查看成绩\n"
    "  • 全部 — 查看所有信息\n"
    "  • 下载 COMP2090 课件 — 下载课程文件"
)


# ── WebSocket ──────────────────────────────────────────────

@app.websocket("/ws")
async def ws_chat(ws: WebSocket):
    await ws.accept()
    await ws.send_json({"text": _INTENT_HELP})

    scraper_pool = ScraperPool()
    conversation = ConversationHistory()
    agent_cancel = asyncio.Event()

    async def _on_thinking(text: str):
        try:
            await ws.send_json({"type": "thinking", "text": text})
        except Exception:
            pass

    async def _on_delta(text: str):
        try:
            await ws.send_json({"type": "delta", "text": text})
        except Exception:
            pass

    try:
        while True:
            text = await ws.receive_text()

            try:
                if text == "__STOP__":
                    agent_cancel.set()
                    continue

                if text.startswith("__RESTORE__"):
                    try:
                        conversation.load(json.loads(text[len("__RESTORE__"):]))
                        log.info("Restored conversation history: %d msgs", len(conversation.get_for_prompt()))
                    except Exception as e:
                        log.warning("Restore history failed: %s", e)
                    continue

                agent_cancel.clear()

                if not LLM_CONFIG.is_configured:
                    await ws.send_json({"text": f"未配置 LLM,无法处理查询。请在 .env 设置 LLM_PROVIDER + LLM_API_KEY(当前:{LLM_CONFIG.describe()})。"})
                    continue

                executor = ToolExecutor(scraper_pool=scraper_pool)
                reply = await run_agent_loop(
                    user_message=text,
                    history=conversation.get_for_prompt(),
                    executor=executor,
                    on_thinking=_on_thinking,
                    on_delta=_on_delta,
                    cancel_event=agent_cancel,
                )
                conversation.add("user", text)
                conversation.add("assistant", reply)
                await ws.send_json({"type": "final", "text": reply})

            except Exception as e:
                log.error("Message handling error: %s", e, exc_info=True)
                await ws.send_json({"text": f"处理时出错了: {e.__class__.__name__}。请换个说法再试，或输入「帮助」查看用法。"})

    except WebSocketDisconnect:
        pass
    finally:
        await scraper_pool.close()


# ── 前端 SPA ───────────────────────────────────────────────
# 生产:托管 frontend/dist(npm run build 产物)。
# dev:vite dev (5173) + vite.config proxy /ws → 这里 (8000),无需 dist。
# 必须在所有 API/WS 路由之后注册:app.frontend() 是 catch-all。

_FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    app.frontend("/", directory=str(_FRONTEND_DIST))
