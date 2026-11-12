# Sunday Bakehouse: an AI avatar that takes your order

A live AI barista on a cafe website. You talk, Hollis answers with a real face, and the page changes as you go: it jumps to sections, filters the menu by diet, highlights dishes, builds your order and places it.

Built with [Pipecat](https://github.com/pipecat-ai/pipecat) and [`pipecat-akapulu`](https://pypi.org/project/pipecat-akapulu/), which adds the face.

## How it works

Three participants join one Daily room: you in the browser, the voice bot, and the Akapulu Labs avatar.

1. `server.py` serves the page. **Start talking** calls `POST /session`.
2. `session.py` creates a private Daily room, mints tokens, and starts an Akapulu Labs live session.
3. `bot.py` joins and runs the pipeline: Deepgram Flux (listening + turn-taking) → `gpt-5.4-mini` → Cartesia Sonic 3.6 → `AkapuluAvatar`.
4. The avatar joins as its own participant and publishes the face and voice.
5. When the model calls a tool, the bot sends a small Daily app message (`label: "cafe"`). `web/app.js` updates the page.

Adding the face to a Pipecat bot is one processor:

```python
from pipecat_akapulu import AkapuluAvatar

avatar = AkapuluAvatar(session_id=session_id)
pipeline = Pipeline([transport.input(), stt, user_agg, llm, tts, avatar, transport.output(), assistant_agg])
```

## Tools

| Tool | What the page does |
|---|---|
| `show_section` | Scrolls to Coffee, Tea, Pastries or Breakfast |
| `filter_menu` | Dims everything that is not vegan / dairy-free / gluten-free / caffeine-free |
| `highlight_item` | Rings and scrolls to one item |
| `add_to_order`, `remove_from_order` | Updates the order card and item badges |
| `place_order` | Shows the pickup confirmation |

The menu lives in `menu.py`. The bot's prompt and the page both read it.

## Get your 5 keys

All five have a free tier or free credits.

| Key | Where to get it |
|---|---|
| `DAILY_API_KEY` | [dashboard.daily.co](https://dashboard.daily.co) → Developers |
| `AKAPULU_API_KEY` | [akapulu.com/api-keys](https://akapulu.com/api-keys/) → New key (20 free credits) |
| `DEEPGRAM_API_KEY` | [console.deepgram.com](https://console.deepgram.com) → API Keys |
| `OPENAI_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `CARTESIA_API_KEY` | [play.cartesia.ai/keys](https://play.cartesia.ai/keys) |

## Run

```bash
git clone https://github.com/Akapulu/pipecat-avatar-cafe && cd pipecat-avatar-cafe
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # DAILY, AKAPULU, OPENAI, DEEPGRAM, CARTESIA keys
python server.py
```

Open http://127.0.0.1:7860 and press **Start talking**. Tests: `pytest`.

## Cost

Akapulu Labs bills 1 credit per live minute with the Pipecat plugin. The free plan includes 20 credits. Starter is $48.97/month for 502 credits. See [pricing](https://akapulu.com/pricing).
