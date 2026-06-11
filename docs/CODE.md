# STORYPITCH – FROZEN MEMORY (Implementation Blueprint) – v2.0

## 1. Project Identity
- **Name:** StoryPitch (Persian: داستان پیچ – “story twist”)
- **Type:** AI‑powered interactive story game with save/load, memory, dual interfaces (custom web UI + Telegram bot), and database admin.
- **Tech stack:** FastAPI (backend), SQLite + SQLModel (database), LM Studio (local AI) + HuggingFace (online AI), custom HTML/CSS/JS frontend (replaces Gradio), python-telegram-bot (Telegram bot), httpx (async HTTP), python-dotenv (optional), aiofiles, uvicorn.

## 2. Directory & File Structure
```
StoryPitch/
├── api/
│   ├── auth.py          # API key middleware
│   └── main.py          # All FastAPI endpoints
├── db/
│   ├── db.py            # SQLModel models & CRUD
│   └── seed_data.py     # Seed test data
├── llm/
│   ├── adapters.py      # generate() with primary/fallback
│   └── manager.py       # LLMManager with cache, semaphore, fallback
├── story/
│   ├── logic.py         # start_session, advance_session
│   ├── memory.py        # StoryMemory class
│   ├── memory_analyzer.py # AI memory extraction
│   ├── parser.py        # parse_ai_output (9 strategies)
│   ├── postprocess.py   # normalize_ai_text_to_story
│   └── prompts.py       # build_fast_prompt, build_memory_analysis_prompt
├── ui/
│   ├── index.html       # Custom web frontend (tabbed, all features)
│   ├── gradio_ui.py     # (legacy – kept but not used)
│   └── telegram_bot.py  # Real Telegram bot with conversation handler
├── utils/
│   ├── api_utils.py     # ensure_api_running, health checks
│   ├── formatting.py    # console helpers (print_success, etc.)
│   ├── http_client.py   # create_async_client, create_sync_client
│   ├── log_cleaner.py   # background log cleaner (every 60s)
│   └── performance.py   # LRUCache, timed decorator, metrics
├── tests/               # 9 test files (all test_*.py)
├── config.py            # all env‑driven configuration
├── constants.py         # themes, traits, fallbacks, limits
├── db_manager.py        # CLI for database admin
├── run.py               # launcher (api/gradio/html/telegram/seed)
├── test.py              # runs all test files
├── requirements.txt     # dependencies
├── story.db             # SQLite database (created at runtime)
└── logs/
    └── story_maker.log  # rotating log file
```

## 3. Configuration (`config.py`)

| Section | Key | Default / Source | Purpose |
|---------|-----|------------------|---------|
| API | `API_HOST`, `API_PORT` | 127.0.0.1, 8000 | FastAPI binding |
| API | `API_KEY` | empty (optional) | auth token (if set) |
| DB | `DATABASE_URL` | `sqlite:///story.db` | SQLite path |
| LLM | `DEFAULT_MODEL` | `"local"` | `local` or `hf` |
| LLM (LM Studio) | `LM_STUDIO_URL` | `http://127.0.0.1:1234` | base URL |
| LLM (LM Studio) | `LM_STUDIO_MODEL` | `""` (auto-detect) | model ID |
| LLM (LM Studio) | `LM_STUDIO_USE_CHAT` | `True` | use `/v1/chat/completions` first |
| LLM (HF) | `HF_API_KEY` | from env | required for online |
| LLM (HF) | `HF_MODEL` | `"gpt2"` (can change) | model name |
| Generation | `LLM_MAX_TOKENS` | 1000 | max tokens per call |
| Generation | `LLM_TEMPERATURE` | 0.8 | creativity |
| Generation | `LLM_TOP_P` | 0.95 | nucleus sampling |
| Generation | `CACHE_TTL` | 300 sec | cache lifetime |
| Story | `STORY_CHOICES_COUNT` | 4 | number of choices |
| Story | `STORY_NARRATION_MIN/MAX_SENTENCES` | 5 / 10 | length guidance |
| Story | `STORY_COMPLEXITY` | `"medium"` | (reserved) |
| Network | `HTTP_TIMEOUT` | 300 sec | request timeout |
| Network | `MAX_CONCURRENT_LLM` | 4 | semaphore limit |
| Logging | `LOG_MAX_BYTES` | 5MB | rotation size |
| Logging | `LOG_BACKUP_COUNT` | 2 | backups kept |
| Logging | `LOG_RETENTION_MINUTES` | 60 | auto-delete old logs |
| Telegram | `TELEGRAM_TOKEN` | from env | bot token |

Logging is configured via `configure_logging()` – uses `RotatingFileHandler` + `StreamHandler`, auto‑cleanup of old logs on startup and every 60s (background thread from `log_cleaner`).

## 4. Constants (`constants.py`)

| Category | Contents |
|----------|----------|
| **Themes** | `THEME_LIST` (64 themes: fantasy, sci‑fi, mystery, adventure, urban, historical, unique) |
| **Traits** | `TRAIT_LIST` (20 traits: Brave, Cautious, Clever, Curious, Charismatic, Honest, Deceptive, Patient, Impulsive, Resourceful, Analytical, Creative, Compassionate, Ruthless, Optimistic, Cynical, Loyal, Rebellious, Funny, Mysterious) |
| **Trait guidelines** | `TRAIT_GUIDELINES` – maps each trait to a description of how it influences AI choices (e.g., brave → “Bold, risky options”) |
| **Character names** | `CHARACTER_NAME_LIST` (80+ names) |
| **Story titles** | `STORY_TITLE_LIST` (50+ titles) |
| **Fallbacks** | `FALLBACK_NARRATION`, `FALLBACK_CHOICES`, `FALLBACK_CLUES`, `FALLBACK_RESPONSE`, `FALLBACK_AI_TEXT` |
| **Memory limits** | `MEMORY_MAX_EVENTS = 50`, `MEMORY_MAX_DISCOVERIES = 30`, `MEMORY_RECENT_EVENTS_KEEP = 30` |
| **Prompt context sizes** | `PROMPT_RECENT_NARRATIONS = 2`, `PROMPT_ACTIVE_NPCS = 2`, `PROMPT_KEY_ITEMS = 2`, `PROMPT_RECENT_DISCOVERIES = 1`, `PROMPT_IMPORTANT_EVENTS = 1`, `PROMPT_RECENT_CONSEQUENCES = 1`, `PROMPT_ACTIVE_RELATIONSHIPS = 1`, `PROMPT_INVENTORY_ITEMS = 1` |
| **Narration history** | `NARRATION_HISTORY_COUNT = 3` (kept in world state) |
| **Memory analysis** | `MEMORY_ANALYSIS_NARRATION_COUNT = 3` (used by refresh‑memory) |
| **Story arc steps** | `STORY_ARC_BEGINNING_END = 3`, `STORY_ARC_RISING_END = 8`, `STORY_ARC_CLIMAX_END = 12` |
| **Log separator** | `LOG_SEPARATOR = "=" * 100` |

## 5. Database Schema (`db/db.py`)

**Tables (SQLModel):**

- **`User`**
  - `id` (int, PK)
  - `username` (str)
  - `created_at` (datetime)

- **`SessionModel`** (renamed to avoid conflict)
  - `id` (int, PK)
  - `user_id` (int, FK → User)
  - `title` (str)
  - `world_state` (str, JSON serialized)
  - `current_step` (int)
  - `created_at` (datetime)
  - `updated_at` (datetime)
  - *method* `get_world_state()` – returns dict
  - *method* `set_world_state(obj)` – serializes

- **`Step`**
  - `id` (int, PK)
  - `session_id` (int, FK)
  - `step_index` (int)
  - `prompt` (str)
  - `ai_output` (str)
  - `user_input` (str, optional)
  - `created_at` (datetime)

- **`Snapshot`** (game saves)
  - `id` (int, PK)
  - `session_id` (int, FK)
  - `created_at` (datetime)
  - `title` (str) – user‑friendly name
  - `description` (str) – auto‑generated from last narration
  - `world_state` (str, JSON) – full state at save time
  - `current_step` (int)

**CRUD operations (key ones):**

- `create_user(username) → User`
- `create_session(user_id, title, world_state) → SessionModel`
- `get_session(session_id) → SessionModel | None`
- `update_session(session_id, world_state, current_step) → SessionModel`
- `save_step(session_id, step_index, prompt, ai_output, user_input) → Step`
- `get_steps(session_id) → List[Step]` (ordered by step_index)
- `reset_session(session_id) → SessionModel` (clears world state, deletes all steps)
- `create_snapshot(session_id, title, description) → Snapshot | None` (auto‑generates description from last step if empty)
- `load_snapshot(session_id, snapshot_id=None) → SessionModel | None`  
  **Critical logic:** Restores session’s `world_state` and `current_step` from snapshot, **deletes the step at the restored index** (so the player can make a different choice) and deletes all steps with index > restored step. This preserves timeline integrity.
- `get_session_snapshots(session_id) → List[Snapshot]` (ordered newest first)
- `get_snapshot_details(snapshot_id) → Snapshot | None`
- `rename_snapshot(snapshot_id, new_title) → bool`
- `update_snapshot_description(snapshot_id, new_description) → bool`
- `delete_snapshot(snapshot_id) → bool`
- Admin: `get_all_users()`, `get_all_sessions()`, `get_all_snapshots()`, `delete_user(id)`, `delete_session(id)`, `delete_snapshot(id)`

## 6. LLM Manager (`llm/manager.py`)

**Class `LLMManager`**
- Constructor: `default_model = DEFAULT_MODEL`
- Method `generate(prompt, model=None, max_tokens=None) → str`  
  - Uses in‑memory TTL cache (`_cache`, `_cache_lock`) with SHA256 key (`model+prompt`).
  - Semaphore (`_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM)`) to limit concurrent calls.
  - Model selection: `"local"` (LM Studio) or `"hf"` (HuggingFace).
  - **LM Studio logic:**  
    - Uses `LM_STUDIO_URL`, optional API key.  
    - Auto‑detects model if `LM_STUDIO_MODEL` empty: calls `/v1/models` and picks first ID.  
    - Tries `/v1/chat/completions` (if `LM_STUDIO_USE_CHAT`) then `/v1/completions`.  
    - Payload includes `max_tokens`, `temperature` from config.
  - **HuggingFace logic:**  
    - Uses `HF_API_KEY`, endpoint `https://api-inference.huggingface.co/models/{HF_MODEL}`.  
    - Retries up to 3 times.
  - **Fallback generator** `_fallback(prompt)`:  
    - Looks for keywords `"start"`, `"explore"`, `"fight"` in prompt and returns themed narration+choices+clues.  
    - Default returns `FALLBACK_AI_TEXT` (from constants).
  - Caches successful responses.

**Function `generate(prompt, primary, fallback, max_tokens)`** from `adapters.py`:
- Calls `llm.generate` with `primary` model; if exception, tries `fallback` (defaults to the other model). If both fail, re‑raises (caller handles fallback).
- Used by story logic.

## 7. Story Core (`story/logic.py`)

**`start_session(user_id, title, theme, traits, character_name, model) → dict`**
- Creates `world_state` dict with: `theme`, `traits`, `character_name`, `clues`, `consequences`, `discoveries`, `relationships`, `inventory`, `objectives`, `story_arc` (`"beginning"`), `world_rules`.
- Calls `build_fast_prompt(sess, user_input=None)` – uses minimal context (recent narrations, current location, active NPCs) and strict JSON format instruction.
- Calls `generate` (via `adapters.generate`) with retry (2 attempts).
- Parses output with `normalize_ai_text_to_story` (postprocess).
- Updates world state: `last_narration`, `last_choices`, appends to `narration_history`, adds clues.
- **Memory extraction** (if AI returned `memory` field):  
  - Uses `StoryMemory(world_state)` to add NPCs, locations, inventory, events, discoveries with step=1.
- Saves first step (step_index=1) via `save_step`.
- Returns `{"session_id": sess.id, "narration": ..., "choices": ..., "clues": ...}`.

**`advance_session(session_id, user_input, choice_index, model) → dict`**
- **Smart input handling:** If `choice_index` is provided, fetches last step’s choices and maps to the actual choice text (1‑based). Otherwise uses `user_input` string. Exactly one must be provided.
- Builds fast prompt with `user_input` (the chosen or typed action).
- Calls `generate` (retry 2 attempts).
- Parses with `normalize_ai_text_to_story`.
- Updates world state: `last_narration`, `last_choices`, `last_action`, appends to `narration_history`, adds clues, appends to `consequences`.
- Updates `step_count`, adjusts `story_arc` based on thresholds (`beginning` ≤3, `rising` ≤8, `climax` ≤12, else `resolution`).
- **Memory extraction** (if AI returned `memory`):  
  - Uses `StoryMemory` to add NPCs, locations, items, events, discoveries with `step=step_index` (current step+1).
- Updates session (new `current_step`), saves step.
- Returns `{"narration": ..., "choices": ..., "clues": ..., "step_index": new_step}`.

## 8. Memory System (`story/memory.py`)

**Class `StoryMemory`** – wraps `world_state["memory"]` (auto‑created if missing).

**Data structures inside `world_state["memory"]`:**

- `npcs`: dict `name → {description, personality, first_met_step, last_seen_step, interactions}`
- `locations`: dict `name → {description, first_visited_step, last_visited_step, visited_count}`
- `events`: list of `{step, description, importance, timestamp}` – trimmed to `MEMORY_MAX_EVENTS`, keeps high/critical + last `MEMORY_RECENT_EVENTS_KEEP`
- `relationships`: dict `npc_name → {affinity (-100..100), trust (-100..100), notes, updated_step}`
- `inventory`: list of `{item, description, acquired_step}`
- `discoveries`: list of `{step, discovery, significance}` – trimmed to `MEMORY_MAX_DISCOVERIES` (keeps most recent)

**Key methods:**
- `add_npc(name, description, personality, step)`
- `add_location(name, description, step)`
- `add_event(description, step, importance)`
- `set_relationship(npc_name, affinity, trust, notes)`
- `adjust_relationship(npc_name, affinity_change, trust_change)`
- `add_item(item, description, step)`, `remove_item(item)`, `has_item(item)`
- `add_discovery(discovery, significance, step)`
- `get_context_for_prompt()` → returns `recent_npcs`, `recent_locations`, `important_events`, `inventory`, `key_relationships` (only those with affinity/trust magnitude >30).

## 9. Memory Analyzer (`story/memory_analyzer.py`)

**`analyze_and_refresh_memory(session_id, model) → dict`**
- Builds prompt via `build_memory_analysis_prompt(session)` – includes last `MEMORY_ANALYSIS_NARRATION_COUNT` narrations and asks for structured JSON (NPCs, locations, inventory, relationships, events, discoveries).
- Calls LLM with `max_tokens=3000` (to avoid truncation).
- Parses result with `_super_smart_parse_memory_json(ai_text)` – uses 5 strategies:
  1. Look for `{"npcs"` or `{"locations"` markers and extract to matching brace.
  2. Scan all `{` positions and extract balanced braces.
  3. Regex patterns for JSON-like structures.
  4. Attempt to complete truncated JSON by adding missing braces/brackets.
  5. Infer from reasoning text (capitalized words as NPCs, location phrases).
- Updates `world_state["memory"]` via `StoryMemory` methods.
- Returns `{"success": bool, "message": str, "memory": dict, "summary": str}`.

## 10. Parser & Postprocessor (`story/parser.py`, `story/postprocess.py`)

**`parse_ai_output(ai_text)`** (parser.py) – ultimate parser with 9 strategies:
- Unicode garbage fix, code fence removal, whitespace normalization.
- Strips reasoning text, extracts JSON via:
  - Brace balancing from first `{`
  - Content wrapper (`"content": "{...}"`)
  - Reasoning markers (`OUTPUT:`, `JSON:`, ````json`)
  - OpenAI wrapper (choices[0].message.content)
  - Truncated response handler (adds missing braces)
- Falls back to text‑based extraction of paragraphs and numbered/bulleted choices.
- Returns dict with `narration`, `choices`, `clues`, `memory` (validated structure).

**`normalize_ai_text_to_story(ai_text, max_choices=4, max_narration_chars=1200)`** (postprocess.py):
- Calls `parse_ai_output`, then:
  - Truncates narration at sentence boundary.
  - Cleans choices (remove duplicates, numbering/bullets, truncate to 150 chars).
  - Ensures memory structure (lists for npcs, locations, items, events, discoveries).
- If main parser fails or returns insufficient content, uses internal `_simple_parse` fallback.

## 11. Prompts (`story/prompts.py`)

**`build_fast_prompt(session, user_input, max_choices=None)`**
- Ultra‑lean, instructs LLM to output **ONLY JSON** with no extra text.
- Includes a complete example JSON.
- Provides context: theme, character, traits (max 3), current location, active NPCs (max 2), story arc, last narration (200 chars), and player action.
- Adds investigation hint if user input contains look/search/examine/investigate.
- Ends with opening brace `{"narration": "` to encourage completion.
- Used for all story generation turns.

**`build_memory_analysis_prompt(session, narration_count=3)`**
- Lists the last N narrations.
- Asks for JSON with fields: npcs, locations, inventory, relationships, events, discoveries.
- Gives example format.
- Used only for “Refresh Memory” button.

**Helper functions (internal):**
- `_get_recent_narrations(state, count)`
- `_get_current_location(state)`
- `_get_active_npcs(state, count)`
- `_get_key_items(state, count)`
- `_get_character_development(state)`
- `_get_recent_discoveries(state, count)`
- `_get_important_events(state, count)`
- `_get_recent_consequences(state, count)`
- `_get_active_relationships(state, count)`
- `_get_inventory_items(state, count)`
- `_get_current_objectives(state)`

## 12. APIs (`api/main.py`)

**Core endpoints (all require `X-API-Key` if `API_KEY` set):**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | health check |
| POST | `/api/user` | create user |
| POST | `/api/session/start` | start new session |
| GET | `/api/session/{id}/state` | get current state |
| GET | `/api/session/{id}/processing` | check if session is busy |
| POST | `/api/session/{id}/step` | advance story (handles 409 conflict) |
| POST | `/api/session/{id}/reset` | reset session |
| POST | `/api/session/{id}/save` | create snapshot (save) |
| POST | `/api/session/{id}/load` | load latest snapshot (deprecated) |
| POST | `/api/session/{id}/load/{snapshot_id}` | load specific snapshot |
| GET | `/api/session/{id}/snapshots` | list saves |
| GET | `/api/session/{id}/history` | list steps |
| GET | `/api/session/{id}/story-full` | full story with narration+user actions |
| GET | `/api/session/{id}/memory` | get memory (NPCs, locations, inventory, relationships, events, discoveries) |
| POST | `/api/session/{id}/refresh-memory` | trigger AI memory extraction |
| POST | `/api/session/{id}/summarize` | generate summary of a scene |
| GET | `/api/session/{id}/export?fmt=json|text` | export story |
| GET | `/api/admin/users` | list all users |
| GET | `/api/admin/sessions` | list all sessions |
| GET | `/api/admin/snapshots` | list all snapshots |
| DELETE | `/api/admin/user/{user_id}` | delete user |
| DELETE | `/api/admin/session/{session_id}` | delete session |
| DELETE | `/api/admin/snapshot/{snapshot_id}` | delete snapshot |
| POST | `/api/admin/clear-all` | delete all data |
| GET | `/api/admin/ping-lmstudio` | test LM Studio connection |
| GET | `/api/performance` | get cache & performance stats |

**Middleware & Concurrency:**
- CORS middleware (allow all origins).
- Session‑level locks (`_session_locks`) and processing flags (`_session_processing`) to prevent race conditions. Any `/step` or `/refresh-memory` returns 409 if session already processing.
- Request logging middleware (method, path, status code, duration).

## 13. Custom Web UI (`ui/index.html`)

**Main layout:** A single HTML file with tabbed navigation (Play, Memory, History, Telegram, Admin, Settings). No Gradio.

**Play tab:** Two‑column layout – setup (username, character name, story title, theme selection, traits, AI model) on the left; story display, clues, choice buttons (as selectable cards), custom action textarea, Continue button, save/load management on the right. Mode selector: “Use Button Choices” (choice cards) vs “Write Custom Action” (textarea). Summary generation accordion.

**Memory tab:** Displays NPCs, locations, inventory, relationships, events, discoveries (as markdown). “Refresh Memory” button calls `POST /api/session/{id}/refresh-memory` (AI‑powered) and updates all six categories.

**History tab:** Shows full story (from `/api/session/{id}/story-full`) with export as `.txt`.

**Telegram tab:** Full simulator of the real Telegram bot – setup wizard (model → character name → theme selection (random/list/custom) → trait selection with checkmarks) using inline keyboards. After session start, displays choice buttons and action buttons (Save, Memory, History, Reset). Also supports text commands (`/new`, custom actions). All API calls that hit the LLM are wrapped in a global processing lock.

**Admin tab:** Simple lists for users and sessions (refresh, delete, clear all data).

**Settings tab:** Theme (light/dark), font size, API base URL (persisted in localStorage).

**Key UI features:**
- Choice cards (`.choice-card`) – click to select (highlight), then press Continue.
- Global processing lock (`isProcessing` flag) – shows a fixed banner and disables all relevant buttons during any API call that may invoke the LLM (start session, continue, refresh memory, summary, Telegram actions). Prevents multiple simultaneous requests.
- Dark/light mode, font size adjustment, localStorage persistence.
- Responsive design (mobile‑friendly).

**JavaScript helpers (excerpts):**
- `apiCall(endpoint, method, body)` – fetch wrapper with error handling.
- `displayStory(narration, choices, clues)` – renders story, choice cards, clues.
- `sendContinue()` – reads selected choice or custom action, calls `/step` with lock.
- `startSession()` – calls `/user` and `/session/start` with lock.
- `refreshMemory()` – calls `/refresh-memory` with lock.
- `refreshHistory()` – calls `/story-full` (no lock, simple).
- Telegram simulator state machine (`teleState`, `teleTempData`) – handles setup wizard and game commands, all wrapped with lock.

## 14. Telegram Bot (`ui/telegram_bot.py`) – unchanged (real bot). The web UI’s Telegram tab simulates its behavior exactly.

## 15. Utilities

### `utils/http_client.py`
- `get_headers(api_key)` → dict with `x-api-key` if key provided.
- `create_async_client(api_key, timeout)` → `httpx.AsyncClient` with headers and timeout.
- `create_sync_client(api_key, timeout)` → `httpx.Client`.

### `utils/api_utils.py`
- `check_api_health(timeout=2)` – GET `/api/health`.
- `wait_for_api_ready(max_wait=30, check_interval=0.5)` – polls health.
- `start_api_server()` – launches `api.main` as subprocess.
- `stop_api_server()` – terminates subprocess.
- `ensure_api_running()` → `(is_running, was_started)` – starts API if needed.

### `utils/log_cleaner.py`
- Background daemon thread that calls `clear_all_logs()` every `interval` seconds (default 60). `clear_all_logs()` finds all `.log*` files in `logs/` and truncates them to zero length.
- `start_log_cleaner(interval)`, `stop_log_cleaner()`.

### `utils/performance.py`
- `LRUCache` class (OrderedDict) with `get`, `set`, `clear`, `get_stats`.
- Global caches: `_context_cache`, `_memory_cache`.
- Decorator `timed_function` (logs warnings if >1s).
- Functions: `cached_context`, `cache_context`, `cached_memory_summary`, `cache_memory_summary`, `clear_session_cache`, `clear_all_caches`, `get_cache_stats`.
- `optimize_world_state(world_state, max_events)` – trims events and discoveries.
- `PerformanceMonitor` class and global instance; `record_metric`, `get_performance_stats`.

### `utils/formatting.py`
- `print_section_header(title, width)`, `print_success(msg)`, `print_error(msg)`, `print_warning(msg)`, `print_info(msg)`, `print_step(step_num, total, desc)`, `format_duration(seconds)`.

## 16. Database Manager CLI (`db_manager.py`)
- Interactive menu: list users, list sessions, list snapshots, delete user, delete session, delete snapshot, clear all data.
- Uses `create_async_client` to call admin endpoints.

## 17. Main Launcher (`run.py`)

**Updated to support the custom HTML frontend:**  
- Command‑line arguments: `html` (starts API + static server on `ui/`), `gradio` (legacy), `telegram`, `seed`, `help`.
- `run.py` with no arguments shows an interactive menu (choice 1 = HTML, 2 = Gradio, 3 = Telegram, 4 = Seed, etc.).
- The `html` option starts the FastAPI backend and a Python HTTP server (`http.server`) serving the `ui/` folder on a free port (default 8080). Opens the browser automatically.
- The launcher includes port conflict resolution (finds free ports for API and static server) and runs all services in one terminal (no extra windows).

## 18. Test Runner (`test.py`)
- Discovers all `tests/test_*.py` files, runs each as a subprocess, reports summary.

## 19. Tests Overview

| Test File | Coverage |
|-----------|----------|
| `test_api_advanced.py` | session reset, snapshot save/load, history, export (JSON/text), admin endpoints, LM Studio ping, root endpoint |
| `test_database_advanced.py` | world state serialization (complex JSON, Unicode), session reset with steps, admin queries, step ordering, snapshot operations (create/load/delete), edge cases (invalid IDs, None state) |
| `test_game_flow.py` | LM Studio direct, LLM Manager, story logic, API endpoints with detailed step tracking |
| `test_integration_advanced.py` | multi‑step progression (10 steps), save/load/restore workflow, concurrent sessions (3 users), story arc progression, world state persistence, complete user journey |
| `test_llm_advanced.py` | cache functionality (key generation, hit/miss), fallback generator (start/explore/fight keywords), concurrency control (10 concurrent requests), model selection (local/hf/fallback), response validation, error handling (empty/long/special prompts) |
| `test_parser_components.py` | JSON parser (valid, whitespace, memory extraction), prompt builder (session context), postprocessor (markdown wrap, plain JSON, memory preservation) |
| `test_story_logic.py` | session start, advancement, multiple advances, world state persistence, cleanup |
| `test_ui_dependencies.py` | Gradio import, Telegram bot import |
| `test_utils.py` | HTTP client (headers, async/sync client), formatting utilities (duration, print functions), constants import, config import |

## 20. Key Runtime Behaviors

- **Database** – `init_db()` called automatically on first use (using thread‑safe lock). Tables created if not exist.
- **Session locks** – `asyncio.Lock` per session, plus processing flag to reject concurrent requests (returns 409).
- **Save/load timeline integrity** – `load_snapshot` deletes the step at the restored index **and all later steps**, preventing branching timeline corruption.
- **Memory extraction** – Two ways:
  1. **Automatic** – When AI returns `memory` field in its JSON (from `parse_ai_output` → `normalize_ai_text_to_story`), `StoryMemory` updates are applied during `start_session` and `advance_session`.
  2. **Manual** – User clicks “Refresh Memory” button → calls `/refresh-memory` endpoint → `analyze_and_refresh_memory` → AI analyzes last N narrations and updates memory.
- **Fallback chain** – AI generation: primary model → fallback model → intelligent fallback generator → hardcoded `FALLBACK_AI_TEXT`. Story parsing: main parser (9 strategies) → internal `_simple_parse`.
- **Log cleanup** – Automatic background thread truncates all log files every 60 seconds; also runs on startup.
- **Concurrency** – LLM semaphore (max 4) prevents overloading local/cloud endpoints. API session‑level locks prevent race conditions on the same session.
- **Frontend processing lock** – Global `isProcessing` flag, banner, and button disabling ensure that no two LLM‑heavy operations run simultaneously (including Telegram tab actions). Prevents race conditions and duplicate API calls.

---

**This frozen memory now accurately describes the current StoryPitch implementation (custom HTML frontend, Telegram simulator, global lock, updated launcher). In future chats, paste this document, and I will instantly understand your entire project.** 🎭