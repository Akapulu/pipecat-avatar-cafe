"""Voice-stack constants and the language lock. Does not open a call.

Run: python tests/test_voice.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipecat.frames.frames import STTUpdateSettingsFrame, TranscriptionFrame, TTSUpdateSettingsFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.transcriptions.language import Language

import bot


def test_voice_stack():
    assert bot.SPEAKER_MODEL == "gpt-5.4-mini"
    assert bot.SONIC_MODEL == "sonic-3.6"
    assert bot.SONIC_VOICE_ID == "f786b574-daa5-4673-aa0c-cbe3e8534c02"
    assert bot.FLUX_MODEL == "flux-general-multi"
    assert bot.EAGER_EOT_THRESHOLD == 0.5
    assert bot.Language.EN in bot.FLUX_LANGUAGES
    assert bot.Language.ZH not in bot.FLUX_LANGUAGES


def test_spoken_language_locks_and_rejects_a_missing_language():
    class Recording(bot.SpokenLanguage):
        def __init__(self):
            super().__init__()
            self.pushed = []

        async def push_frame(self, frame, direction=FrameDirection.DOWNSTREAM):
            self.pushed.append((frame, direction))

    processor = Recording()
    missing = TranscriptionFrame("hello", "browser", "2026-10-25T00:00:00Z", None, finalized=True)
    try:
        asyncio.run(processor.process_frame(missing, FrameDirection.DOWNSTREAM))
    except RuntimeError as exc:
        assert "no language" in str(exc)
    else:
        raise AssertionError("missing language was accepted")
    assert processor.pushed == []

    processor = Recording()
    english = TranscriptionFrame(
        "hello", "browser", "2026-10-25T00:00:00Z", Language.EN, finalized=True
    )
    asyncio.run(processor.process_frame(english, FrameDirection.DOWNSTREAM))
    assert processor.pushed == [(english, FrameDirection.DOWNSTREAM)]

    processor.pushed.clear()
    switched = TranscriptionFrame(
        "hello", "browser", "2026-10-25T00:00:00Z", Language.JA, finalized=True
    )
    asyncio.run(processor.process_frame(switched, FrameDirection.DOWNSTREAM))
    assert isinstance(processor.pushed[0][0], STTUpdateSettingsFrame)
    assert processor.pushed[0][0].delta.language_hints == [Language.JA]
    assert isinstance(processor.pushed[1][0], TTSUpdateSettingsFrame)
    assert processor.pushed[1][0].delta.language == Language.JA


if __name__ == "__main__":
    test_voice_stack()
    test_spoken_language_locks_and_rejects_a_missing_language()
    print("ok")
