"""Create a private Daily room and an Akapulu live session.

The browser token joins as You. The avatar token joins as Avatar. The bot
token is an owner token and does not set a Daily user name.

Avatar, This is AI, and the Akapulu Labs API origin are fixed for this example.
Set DAILY_API_KEY, AKAPULU_API_KEY, and OPENAI_API_KEY.
"""

import json
import os
import time
import uuid

import aiohttp
from pipecat.transports.daily.utils import (
    DailyMeetingTokenParams,
    DailyMeetingTokenProperties,
    DailyRESTHelper,
    DailyRoomParams,
    DailyRoomProperties,
)

ROOM_TTL_SECS = 2 * 60 * 60
USER_NAME = "You"
AVATAR_NAME = "Avatar"
# Clara (public catalog). This is AI off.
AVATAR_ID = "1f777f64-3758-4a7d-9cbc-c64ae654f7d1"
SHOW_AI_LABEL = False
AKAPULU_API_ORIGIN = "https://akapulu.com"
_DAILY_API = "https://api.daily.co/v1"


def required(name: str) -> str:
    value = os.environ.get(name)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{name} is missing")
    return value.strip()


def api_origin() -> str:
    """Production by default. AKAPULU_API_URL overrides for harnesses."""
    raw = os.environ.get("AKAPULU_API_URL")
    if raw is None:
        return AKAPULU_API_ORIGIN
    origin = raw.strip().rstrip("/")
    if not (origin.startswith("https://") or origin.startswith("http://")):
        raise RuntimeError("AKAPULU_API_URL must be an http(s) origin")
    return origin


def daily_api_url(raw: str | None) -> str:
    if raw is None:
        return _DAILY_API
    url = raw.strip().rstrip("/")
    if not url.startswith("https://"):
        raise RuntimeError("DAILY_API_URL must be an https URL")
    return url


def live_session_body(
    *,
    room_url: str,
    avatar_token: str,
) -> dict:
    if not isinstance(room_url, str) or not room_url.startswith("https://"):
        raise RuntimeError("Daily room url is missing")
    if not isinstance(avatar_token, str) or not avatar_token:
        raise RuntimeError("Daily avatar token is missing")
    return {
        "avatar_id": AVATAR_ID,
        "show_ai_label": SHOW_AI_LABEL,
        "room_url": room_url,
        "avatar_token": avatar_token,
    }


async def _token(rest: DailyRESTHelper, room_url: str, *, owner: bool, properties) -> str:
    token = await rest.get_token(
        room_url,
        expiry_time=ROOM_TTL_SECS,
        owner=owner,
        params=DailyMeetingTokenParams(properties=properties),
    )
    if not isinstance(token, str) or not token:
        raise RuntimeError("Daily meeting token was empty")
    return token


async def create_call(http: aiohttp.ClientSession) -> tuple[str, str, str, str]:
    """Return room_url, bot token, browser token, and Akapulu session id."""
    daily_key = required("DAILY_API_KEY")
    akapulu_key = required("AKAPULU_API_KEY")
    origin = api_origin()
    rest = DailyRESTHelper(
        daily_api_key=daily_key,
        daily_api_url=daily_api_url(os.environ.get("DAILY_API_URL")),
        aiohttp_session=http,
    )
    room = await rest.create_room(
        DailyRoomParams(
            privacy="private",
            properties=DailyRoomProperties(
                exp=time.time() + ROOM_TTL_SECS,
                eject_at_room_exp=True,
                enable_prejoin_ui=False,
                enable_chat=False,
                max_participants=3,
            ),
        )
    )
    if not isinstance(room.url, str) or not room.url.startswith("https://"):
        raise RuntimeError("Daily room has no url")
    room_url = room.url
    bot_token = await _token(
        rest,
        room_url,
        owner=True,
        properties=DailyMeetingTokenProperties(is_owner=True),
    )
    user_token = await _token(
        rest,
        room_url,
        owner=False,
        properties=DailyMeetingTokenProperties(is_owner=False, user_name=USER_NAME),
    )
    avatar_token = await _token(
        rest,
        room_url,
        owner=False,
        properties=DailyMeetingTokenProperties(
            is_owner=False,
            user_name=AVATAR_NAME,
            enable_screenshare=False,
            start_video_off=False,
            start_audio_off=False,
            permissions={
                "hasPresence": True,
                "canSend": ["video", "audio"],
                "canAdmin": False,
            },
        ),
    )
    body = live_session_body(
        room_url=room_url,
        avatar_token=avatar_token,
    )
    url = f"{origin}/api/live-sessions/"
    async with http.post(
        url,
        headers={
            "Authorization": f"Bearer {akapulu_key}",
            "Content-Type": "application/json",
        },
        json=body,
    ) as response:
        raw = await response.text()
        if response.status != 200:
            raise RuntimeError(f"POST /api/live-sessions/ returned {response.status} {raw}")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("POST /api/live-sessions/ is not JSON") from exc
    if not isinstance(payload, dict) or "session_id" not in payload:
        raise RuntimeError("POST /api/live-sessions/ is missing session_id")
    session_id = payload["session_id"]
    try:
        session_id = str(uuid.UUID(str(session_id)))
    except ValueError as exc:
        raise RuntimeError("POST /api/live-sessions/ session_id must be a UUID") from exc
    return room_url, bot_token, user_token, session_id
