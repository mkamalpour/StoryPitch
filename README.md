# StoryPitch

An interactive fiction workspace with local AI, branching checkpoints, and persistent story memory. Create a character, choose a setting, and shape the next scene through suggested choices or your own actions.

## Features

- Responsive browser interface with readable story layouts, dark mode, and session recovery.
- Local LM Studio generation, optional Hugging Face chat models, and a built-in demo that needs no model or API key.
- Named checkpoints that restore both the scene and its story timeline, including alternative branches.
- Character, location, inventory, relationship, event, and discovery tracking.
- Story history, scene summaries, and JSON/text export.
- Optional Gradio and Telegram clients; database administration through the UI or CLI.

## Setup

Python **3.11** is recommended and verified. Use an existing compatible environment and the single dependency file; its bounds keep the Gradio 5 client compatible with FastAPI and Pydantic.

```powershell
conda activate base  # Or activate another existing compatible environment.
# Optional dependency setup; requires explicit permission and connectivity.
python -m pip install -r requirements.txt
python run.py
```

On macOS/Linux, activate an existing compatible environment before using the same Python commands.

The launcher opens the browser once the server is ready, chooses a nearby free port if needed, and stops its child processes when you press Ctrl+C. The UI and API share one loopback address. Choose **Built-in demo** to try the complete workflow without a model.

```text
python run.py api --no-browser   # API only; /docs contains the endpoint reference
python run.py gradio            # Alternative browser client
python run.py telegram          # Requires your Telegram bot token
python -m db.manage             # Database administration against the configured API
python test.py                 # Isolated regression checks
```

`python run.py both` is an alias for the browser app. `python run.py seed` explicitly adds sample records to the configured database.

## Models and configuration

Create an optional `.env` in the project root. Existing environment variables take precedence. Never commit credentials or your story database.

```dotenv
# Local text-generation server; load a model in LM Studio first.
LM_STUDIO_URL=http://127.0.0.1:1234
# Leave empty to select an available text model automatically.
LM_STUDIO_MODEL=
DEFAULT_MODEL=local
OFFLINE_MODE=true

# Optional shared key: protects story and administrative API routes.
API_KEY=
# Optional Telegram client, only started by the telegram launch command.
TELEGRAM_TOKEN=
```

LM Studio URLs with or without `/v1` work. Unsupported chat routes can fall back to the completion route. Unavailable providers use the built-in demo rather than blocking the story indefinitely; the demo uses templates and does not provide model-quality storytelling.

For hosted generation, set `OFFLINE_MODE=false`, `HF_API_KEY` and `HF_MODEL` to a chat model available through [Hugging Face Inference Providers](https://huggingface.co/docs/inference-providers/en/index), then select Hugging Face in the UI. Cloud requests occur only when that provider is selected; offline mode prevents them. Availability and account access depend on your provider configuration.

Other useful settings: `API_PORT` (default 8000), `API_BASE` for standalone clients, `DATABASE_URL` for alternative storage, `HTTP_TIMEOUT` (default 300 seconds), and `STORYPITCH_LOG_DIR`. The launcher binds to `127.0.0.1`. This is a local application with a shared operator key, not a multi-user hosted service with account isolation.

## Data and verification

Stories live in `story.db`; rotating logs live in `logs/`. Both stay local and are ignored by Git, alongside virtual environments, caches, editor files and `.env`. Existing databases receive an additive checkpoint-history migration. Older checkpoints retain their available timeline; scenes already missing from an old database cannot be reconstructed automatically.

`python test.py` uses temporary SQLite storage and mocked/offline models. It never runs against your saved stories, Telegram, or a live model server. Original manual scripts are grouped under `tests/manual/` and excluded from pytest because some modify data or contact live services.

## Project layout

```text
api/       FastAPI routes, validation and optional key protection
story/     Story progression, response parsing and memory
llm/       Model requests and offline fallback
ui/        Browser app, Gradio and Telegram clients
db/        SQLite models, checkpoints, seeding and management
utils/     Shared HTTP, formatting and performance helpers
tests/     Isolated regressions and preserved manual checks
config.py  Environment-based settings
run.py     Launcher
```

A previously hardcoded Telegram token has been removed from the current source. Revoke that token through BotFather before configuring a replacement; earlier Git commits still contain it.

Current lightweight check (Windows, existing Conda base / Python 3.13.5): **22 passed**. No dependency installs, model downloads, live publishing, or heavy datasets were used.

No license file is included.
