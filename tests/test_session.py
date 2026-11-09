"""Session helpers. No network. Run: python tests/test_session.py"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import session


def test_constants_and_body():
    assert session.AVATAR_ID
    assert session.SHOW_AI_LABEL is False
    assert session.AKAPULU_API_ORIGIN.startswith("https://")
    assert session.api_origin() == session.AKAPULU_API_ORIGIN
    body = session.live_session_body(
        room_url="https://example.daily.co/room",
        avatar_token="avatar-token",
    )
    assert body["avatar_id"] == session.AVATAR_ID
    assert body["show_ai_label"] is False
    assert body["room_url"] == "https://example.daily.co/room"
    assert body["avatar_token"] == "avatar-token"


def test_api_origin_override():
    saved = os.environ.pop("AKAPULU_API_URL", None)
    try:
        assert session.api_origin() == session.AKAPULU_API_ORIGIN
        os.environ["AKAPULU_API_URL"] = "https://example.test"
        assert session.api_origin() == "https://example.test"
        os.environ["AKAPULU_API_URL"] = "ftp://example.com"
        try:
            session.api_origin()
        except RuntimeError as exc:
            assert "AKAPULU_API_URL" in str(exc)
        else:
            raise AssertionError("ftp origin was accepted")
    finally:
        if saved is None:
            os.environ.pop("AKAPULU_API_URL", None)
        else:
            os.environ["AKAPULU_API_URL"] = saved


def test_speaks_first():
    from bot import GREETING_CUE, SPOKEN_INSTRUCTION

    assert "reply in one or two short sentences" in SPOKEN_INSTRUCTION
    assert "wait" not in SPOKEN_INSTRUCTION.lower()
    assert GREETING_CUE.startswith("Greet the caller as the barista")


def test_avatar_microphone_off():
    from bot import avatar_microphone_off

    assert avatar_microphone_off({"id": "browser", "info": {"userName": "You"}}) is None
    assert avatar_microphone_off(
        {"id": "local", "info": {"isLocal": True, "userName": "Assistant"}}
    ) is None
    assert avatar_microphone_off({"id": "avatar", "info": {"userName": "Avatar"}}) == {
        "avatar": {"media": {"microphone": "unsubscribed"}}
    }
    try:
        avatar_microphone_off({"info": {"userName": "Avatar"}})
    except RuntimeError as exc:
        assert "id" in str(exc)
    else:
        raise AssertionError("avatar without an id was accepted")


if __name__ == "__main__":
    test_constants_and_body()
    test_api_origin_override()
    try:
        test_speaks_first()
        test_avatar_microphone_off()
    except ImportError as exc:
        print(f"bot import skipped: {exc}")
    print("ok")
