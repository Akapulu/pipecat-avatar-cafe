"""Page and the empty-session error. Does not create a Daily room.

Run: python tests/test_server.py
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aiohttp.test_utils import TestClient, TestServer

from server import make_app


async def _run() -> None:
    saved = os.environ.pop("DAILY_API_KEY", None)
    app = make_app()
    async with TestClient(TestServer(app)) as client:
        page = await client.get("/")
        assert page.status == 200
        html = await page.text()
        assert "Akapulu Labs call" in html
        script = await client.get("/static/app.js")
        assert script.status == 200
        started = await client.post("/session", json={})
        assert started.status == 500
        body = await started.json()
        assert body["error"] == "DAILY_API_KEY is missing"
        extra = await client.post("/session", json={"avatar_id": "nope"})
        assert extra.status == 400
    if saved is not None:
        os.environ["DAILY_API_KEY"] = saved


if __name__ == "__main__":
    asyncio.run(_run())
    print("ok")
