"""Cafe barista bot. Audio out and video out stay off.

Tools let the model drive the page: show a section, filter the menu,
highlight a dish, add or remove items, and place the order. Each tool
sends a small Daily app message (label "cafe") that web/app.js renders.

Deepgram Flux hears the caller. gpt-5.4-mini speaks. Cartesia Sonic 3.6
speaks each finished sentence. The Akapulu worker publishes the face and
the played audio. When the participant named Avatar joins, this bot turns
that microphone off. The browser stays subscribed to it.
"""

import asyncio
import os

from loguru import logger
from pipecat.adapters.llm.schemas.function_schema import FunctionSchema
from pipecat.adapters.llm.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import (
    LLMRunFrame,
    STTUpdateSettingsFrame,
    TranscriptionFrame,
    TTSUpdateSettingsFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.flux.stt import DeepgramFluxSTTService
from pipecat.services.openai.responses.llm import OpenAIResponsesLLMService
from pipecat.services.tts_service import TextAggregationMode
from pipecat.transcriptions.language import Language
from pipecat.services.llm_service import FunctionCallParams
from pipecat.transports.daily.transport import (
    DailyOutputTransportMessageUrgentFrame,
    DailyParams,
    DailyTransport,
)
from pipecat.workers.runner import WorkerRunner
from pipecat_akapulu import AkapuluAvatar

from menu import CAFE_NAME, ITEMS_BY_ID, SECTIONS, TAGS, menu_for_prompt
from session import AVATAR_NAME, USER_NAME

SAMPLE_RATE = 24000
SETUP_TIMEOUT_SECS = 180.0
USER_JOIN_TIMEOUT_SECS = 180.0
SPEAKER_MODEL = "gpt-5.4-mini"
SONIC_MODEL = "sonic-3.6"
# Carson, Curious Conversationalist. Male Sonic voice for Hollis.
SONIC_VOICE_ID = "86e30c1d-714b-4074-a1f2-1cb6b552fb49"
FLUX_MODEL = "flux-general-multi"
EAGER_EOT_THRESHOLD = 0.5
# Codes flux-general-multi returns, and the only codes this bot will lock.
FLUX_LANGUAGES = frozenset(
    {
        Language.DE,
        Language.EN,
        Language.ES,
        Language.FR,
        Language.HI,
        Language.IT,
        Language.JA,
        Language.NL,
        Language.PT,
        Language.RU,
    }
)
SPOKEN_INSTRUCTION = f"""You are Hollis, the friendly barista at {CAFE_NAME}, taking an order on the cafe's website.
You are speaking out loud, so reply in one or two short sentences. No lists, no markdown, no prices unless asked.
Speak the language of the caller's latest turn.

Use your tools to drive the page while you talk:
- show_section when you start talking about a part of the menu.
- filter_menu when the caller mentions a diet (vegan, dairy-free, gluten-free, caffeine-free). Use "all" to clear it.
- highlight_item when you describe or recommend one item.
- add_to_order and remove_from_order whenever the order changes. Never say you added something without calling the tool.
- place_order only after the caller confirms the order is complete and gives a name for pickup.
Only offer items on this menu. Use the exact item ids.

Menu:
{menu_for_prompt()}"""
GREETING_CUE = "Greet the caller as the barista in one or two sentences and ask what they are in the mood for."

TOOLS = ToolsSchema(
    standard_tools=[
        FunctionSchema(
            name="show_section",
            description="Scroll the page to one menu section.",
            properties={"section": {"type": "string", "enum": list(SECTIONS)}},
            required=["section"],
        ),
        FunctionSchema(
            name="filter_menu",
            description="Show only items with a diet tag, or 'all' to show everything.",
            properties={"tag": {"type": "string", "enum": [*TAGS, "all"]}},
            required=["tag"],
        ),
        FunctionSchema(
            name="highlight_item",
            description="Highlight one item on the page while you describe it.",
            properties={"item_id": {"type": "string", "enum": list(ITEMS_BY_ID)}},
            required=["item_id"],
        ),
        FunctionSchema(
            name="add_to_order",
            description="Add an item to the caller's order.",
            properties={
                "item_id": {"type": "string", "enum": list(ITEMS_BY_ID)},
                "quantity": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            required=["item_id", "quantity"],
        ),
        FunctionSchema(
            name="remove_from_order",
            description="Remove an item from the caller's order.",
            properties={"item_id": {"type": "string", "enum": list(ITEMS_BY_ID)}},
            required=["item_id"],
        ),
        FunctionSchema(
            name="place_order",
            description="Place the order once the caller confirms it and gives a pickup name.",
            properties={"name": {"type": "string"}},
            required=["name"],
        ),
    ]
)


class CafeOrder:
    """Holds the order and turns each tool call into a page update."""

    def __init__(self, transport: DailyTransport):
        self._transport = transport
        self.lines: dict[str, int] = {}

    def total(self) -> float:
        return round(sum(ITEMS_BY_ID[i]["price"] * q for i, q in self.lines.items()), 2)

    def summary(self) -> str:
        if not self.lines:
            return "The order is empty."
        parts = [f"{q} x {ITEMS_BY_ID[i]['name']}" for i, q in self.lines.items()]
        return f"Order: {', '.join(parts)}. Total ${self.total():.2f}."

    async def _send(self, event: str, **data) -> None:
        message = {"label": "cafe", "event": event, **data}
        await self._transport.output().send_message(
            DailyOutputTransportMessageUrgentFrame(message=message)
        )

    async def _send_order(self) -> None:
        await self._send("order", lines=self.lines, total=self.total())

    async def show_section(self, params: FunctionCallParams) -> None:
        section = params.arguments["section"]
        await self._send("section", section=section)
        await params.result_callback(f"Showing {SECTIONS[section]}.")

    async def filter_menu(self, params: FunctionCallParams) -> None:
        tag = params.arguments["tag"]
        await self._send("filter", tag=tag)
        await params.result_callback("Showing the full menu." if tag == "all" else f"Showing {TAGS[tag]} items.")

    async def highlight_item(self, params: FunctionCallParams) -> None:
        item_id = params.arguments["item_id"]
        await self._send("highlight", item_id=item_id)
        await params.result_callback(f"Highlighted {ITEMS_BY_ID[item_id]['name']}.")

    async def add_to_order(self, params: FunctionCallParams) -> None:
        item_id = params.arguments["item_id"]
        quantity = int(params.arguments["quantity"])
        self.lines[item_id] = self.lines.get(item_id, 0) + quantity
        await self._send("highlight", item_id=item_id)
        await self._send_order()
        await params.result_callback(self.summary())

    async def remove_from_order(self, params: FunctionCallParams) -> None:
        self.lines.pop(params.arguments["item_id"], None)
        await self._send_order()
        await params.result_callback(self.summary())

    async def place_order(self, params: FunctionCallParams) -> None:
        if not self.lines:
            await params.result_callback("The order is empty. Ask what they would like first.")
            return
        name = params.arguments["name"].strip() or "Guest"
        await self._send("placed", name=name, total=self.total(), ready_minutes=8)
        await params.result_callback(f"Order placed for {name}. {self.summary()} Ready in about 8 minutes.")


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{name} is missing")
    return value.strip()


def _daily_user_name(participant: dict) -> str:
    info = participant.get("info")
    if not isinstance(info, dict):
        raise RuntimeError("Daily participant has no info")
    name = info.get("userName")
    if not isinstance(name, str) or not name:
        raise RuntimeError("Daily participant has no userName")
    return name


def avatar_microphone_off(participant: dict) -> dict | None:
    """The one Daily subscription change. None for every participant except Avatar."""
    if _daily_user_name(participant) != AVATAR_NAME:
        return None
    participant_id = participant.get("id")
    if not isinstance(participant_id, str) or not participant_id:
        raise RuntimeError("Daily participant has no id")
    return {participant_id: {"media": {"microphone": "unsubscribed"}}}


class SpokenLanguage(FrameProcessor):
    """Lock Flux and Sonic to the language of the latest committed turn.

    The call starts in English. A committed turn in another Flux language
    switches Flux and Sonic. A committed turn with no Flux language, or a
    language outside the Flux set, raises. The same language does not send
    another update.
    """

    def __init__(self):
        super().__init__()
        self._locked = Language.EN

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if (
            direction == FrameDirection.DOWNSTREAM
            and isinstance(frame, TranscriptionFrame)
            and frame.finalized
        ):
            language = frame.language
            if language not in FLUX_LANGUAGES:
                raise RuntimeError(f"Flux committed a turn with no language: {language!r}")
            if language != self._locked:
                self._locked = language
                await self.push_frame(
                    STTUpdateSettingsFrame(
                        delta=DeepgramFluxSTTService.Settings(language_hints=[language])
                    ),
                    FrameDirection.UPSTREAM,
                )
                await self.push_frame(
                    TTSUpdateSettingsFrame(
                        delta=CartesiaTTSService.Settings(language=language)
                    ),
                    FrameDirection.DOWNSTREAM,
                )
        await self.push_frame(frame, direction)


async def run_bot(room_url: str, token: str, session_id: str) -> None:
    """Join the Daily room and run the voice pipeline until the browser leaves."""
    if not isinstance(room_url, str) or not room_url.startswith("https://"):
        raise RuntimeError("Daily room url is missing")
    if not isinstance(token, str) or not token:
        raise RuntimeError("Daily bot token is missing")
    if not isinstance(session_id, str) or not session_id:
        raise RuntimeError("session_id is missing")

    transport = DailyTransport(
        room_url,
        token,
        "Assistant",
        DailyParams(
            audio_in_enabled=True,
            audio_out_enabled=False,
            video_out_enabled=False,
        ),
    )
    stt = DeepgramFluxSTTService(
        api_key=_required("DEEPGRAM_API_KEY"),
        enable_eager_end_of_turn=True,
        settings=DeepgramFluxSTTService.Settings(
            model=FLUX_MODEL,
            language_hints=[Language.EN],
            eager_eot_threshold=EAGER_EOT_THRESHOLD,
        ),
    )
    spoken_language = SpokenLanguage()
    llm = OpenAIResponsesLLMService(
        api_key=_required("OPENAI_API_KEY"),
        service_tier="priority",
        settings=OpenAIResponsesLLMService.Settings(
            model=SPEAKER_MODEL,
            system_instruction=SPOKEN_INSTRUCTION,
            reasoning=OpenAIResponsesLLMService.ReasoningConfig(effort="none"),
        ),
    )
    # One sentence is one Sonic clip. Delay 0 keeps Cartesia from stacking
    # its buffer on top of that wait.
    tts = CartesiaTTSService(
        api_key=_required("CARTESIA_API_KEY"),
        sample_rate=SAMPLE_RATE,
        text_aggregation_mode=TextAggregationMode.SENTENCE,
        max_buffer_delay_ms=0,
        settings=CartesiaTTSService.Settings(
            model=SONIC_MODEL,
            voice=SONIC_VOICE_ID,
            language=Language.EN,
        ),
    )
    order = CafeOrder(transport)
    for tool in TOOLS.standard_tools:
        llm.register_function(tool.name, getattr(order, tool.name))
    avatar = AkapuluAvatar(session_id=session_id)
    context = LLMContext([{"role": "developer", "content": GREETING_CUE}], tools=TOOLS)
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(context)
    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            spoken_language,
            user_aggregator,
            llm,
            tts,
            avatar,
            transport.output(),
            assistant_aggregator,
        ]
    )
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            audio_out_sample_rate=SAMPLE_RATE,
            enable_metrics=True,
        ),
        setup_timeout_secs=SETUP_TIMEOUT_SECS,
    )
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)

    joined = asyncio.Event()

    @transport.event_handler("on_joined")
    async def on_joined(_transport, _data):
        logger.info("Voice bot joined Daily")

    @transport.event_handler("on_participant_joined")
    async def on_participant_joined(_transport, participant):
        if not isinstance(participant, dict):
            raise RuntimeError("Daily participant is not an object")
        info = participant.get("info")
        if isinstance(info, dict) and info.get("isLocal") is True:
            return
        name = _daily_user_name(participant)
        logger.info("Daily participant joined {}", name)
        settings = avatar_microphone_off(participant)
        if settings is not None:
            error = await transport.update_subscriptions(participant_settings=settings)
            if error:
                raise RuntimeError(f"Daily avatar microphone unsubscribe failed: {error}")
            return
        if name != USER_NAME:
            raise RuntimeError(f"Daily participant {name} is not the browser or the avatar")
        if joined.is_set():
            raise RuntimeError("Daily browser joined twice")
        joined.set()
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(_transport, participant):
        # Avatar can leave on a worker fault. Only the browser ending the call
        # should stop this bot.
        if not isinstance(participant, dict):
            raise RuntimeError("Daily participant is not an object")
        name = _daily_user_name(participant)
        logger.info("Daily participant left {}", name)
        if name != USER_NAME:
            return
        await runner.cancel()

    async def leave_if_alone() -> None:
        try:
            await asyncio.wait_for(joined.wait(), USER_JOIN_TIMEOUT_SECS)
        except TimeoutError:
            logger.info("Browser did not join")
            await runner.cancel()

    wait_task = asyncio.create_task(leave_if_alone())
    try:
        await runner.run()
    finally:
        wait_task.cancel()
        try:
            await wait_task
        except asyncio.CancelledError:
            pass
