import os
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response

from .config import DEEPSEEK_KEY
from .scraper_pool import ScraperPool
from .conversation import ConversationHistory
from .tool_executor import ToolExecutor
from .agent_loop import run_agent_loop

log = logging.getLogger("ole-agent")

app = FastAPI(title="OLE Agent")

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def index():
    return FileResponse("app/static/index.html")


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


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

    try:
        while True:
            text = await ws.receive_text()

            try:
                if text == "__STOP__":
                    agent_cancel.set()
                    continue

                agent_cancel.clear()

                if not DEEPSEEK_KEY:
                    await ws.send_json({"text": "未配置 DEEPSEEK_API_KEY，无法处理查询。请在 .env 中设置。"})
                    continue

                executor = ToolExecutor(scraper_pool=scraper_pool)
                reply = await run_agent_loop(
                    user_message=text,
                    history=conversation.get_for_prompt(),
                    executor=executor,
                    deepseek_key=DEEPSEEK_KEY,
                    on_thinking=_on_thinking,
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
