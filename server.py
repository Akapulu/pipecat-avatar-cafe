"""Local page and one voice call.

GET / serves the page. POST /session creates the Daily room and the Akapulu
session, starts the bot, and returns the browser token. The server listens
on 127.0.0.1:7860. One call at a time.
"""

import asyncio
from pathlib import Path

import aiohttp
from aiohttp import web
from dotenv import load_dotenv
from loguru import logger

from bot import run_bot
from menu import menu_for_page
from session import create_call

HOST = "127.0.0.1"
PORT = 7860
WEB = Path(__file__).resolve().parent / "web"


async def index(_request: web.Request) -> web.FileResponse:
    page = WEB / "index.html"
    if not page.is_file():
        raise RuntimeError("web/index.html is missing")
    return web.FileResponse(page)


async def menu(_request: web.Request) -> web.Response:
    return web.json_response(menu_for_page())


async def start_session(request: web.Request) -> web.Response:
    if request.content_type == "application/json":
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "session body must be JSON"}, status=400)
        if body not in ({}, None):
            return web.json_response({"error": "session body must be empty"}, status=400)
    elif request.content_length not in (None, 0):
        return web.json_response({"error": "Content-Type must be application/json"}, status=400)
    lock: asyncio.Lock = request.app["lock"]
    async with lock:
        task: asyncio.Task | None = request.app["bot_task"]
        if task is not None and not task.done():
            return web.json_response({"error": "a call is already running"}, status=409)
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as http:
            room_url, bot_token, user_token, session_id = await create_call(http)
        bot_task = asyncio.create_task(run_bot(room_url, bot_token, session_id))

        def _finished(done: asyncio.Task) -> None:
            if done.cancelled():
                return
            exc = done.exception()
            if exc is not None:
                logger.error("voice bot failed: {}", exc)

        bot_task.add_done_callback(_finished)
        request.app["bot_task"] = bot_task
    return web.json_response(
        {"room_url": room_url, "token": user_token, "session_id": session_id}
    )


@web.middleware
async def errors(request: web.Request, handler):
    try:
        return await handler(request)
    except asyncio.CancelledError:
        raise
    except web.HTTPException:
        raise
    except RuntimeError as exc:
        logger.error("{}", exc)
        return web.json_response({"error": str(exc)}, status=500)
    except Exception as exc:
        logger.exception("request failed")
        return web.json_response({"error": str(exc)}, status=500)


async def _close_bot(app: web.Application) -> None:
    task: asyncio.Task | None = app["bot_task"]
    if task is None or task.done():
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def make_app() -> web.Application:
    app = web.Application(middlewares=[errors])
    app["lock"] = asyncio.Lock()
    app["bot_task"] = None
    app.on_cleanup.append(_close_bot)
    app.router.add_get("/", index)
    app.router.add_get("/menu.json", menu)
    app.router.add_post("/session", start_session)
    app.router.add_static("/static", WEB, show_index=False)
    return app


def main() -> None:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    web.run_app(make_app(), host=HOST, port=PORT)


if __name__ == "__main__":
    main()
