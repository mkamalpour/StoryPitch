# 🎭 StoryPitch – AI‑Powered Interactive Story Game

**StoryPitch** is an AI‑powered interactive story game where every choice shapes a unique narrative. It runs locally with **LM Studio** (free, private) or online with **Hugging Face**. You can play via a beautiful **Gradio web UI** or a **Telegram bot**.

> ✅ **Production‑ready** – full save/load, persistent memory (NPCs, locations, inventory), dual input modes (buttons or free text), and a complete admin database manager.

---

## ⚡ Quick Start (3 commands)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Test everything (auto‑starts API, runs all tests)
python test.py

# 3. Start the game
python run.py both
```

Then open **http://127.0.0.1:7860** and begin your adventure! 🎉

---

## ✨ Features

- **Dynamic AI storytelling** – no fixed branches, every scene is generated fresh.
- **Dual input modes** – click button choices **or** type any custom action.
- **Character traits** – brave, curious, clever… influence the story without being stated directly.
- **Save & load system** – multiple named saves, full state restore, timeline integrity (loading deletes future steps).
- **Smart memory** – automatically tracks NPCs, locations, inventory, relationships, events, and discoveries.
- **Two interfaces** – Gradio web app + Telegram bot.
- **AI fallback** – works with LM Studio (local), Hugging Face (online), or even no AI (fallback responses).
- **Full database admin** – manage users, sessions, and saves from the UI.
- **Export stories** – download your adventure as a text file.

---

## 🎮 How to Play

1. **Create your character** – choose a name, pick traits (or add custom ones).
2. **Choose a theme** – random, from a list, or write your own.
3. **Start the story** – the AI generates the first scene with 3‑4 choices.
4. **Play your way** – click a button **or** type whatever you want to do.
5. **Save anytime** – give your save a name (e.g., “Before the Dragon”).
6. **Load any save** – restore exactly to that moment and make different choices.

---

## 🤖 AI Setup

### Option 1: LM Studio (local – recommended, free)

1. Download [LM Studio](https://lmstudio.ai/)
2. Load a model (e.g., **Mistral 7B**)
3. Go to the **Local Server** tab and click **Start Server** (default port `1234`)
4. Done – StoryPitch will auto‑detect it.

### Option 2: Hugging Face (online)

1. Get an API key from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. Set the environment variable:
   ```bash
   export HF_API_KEY="your_token_here"   # Linux/Mac
   # or
   $env:HF_API_KEY="your_token_here"     # Windows PowerShell
   ```
3. In `config.py`, set `DEFAULT_MODEL = "hf"`

### Option 3: No AI (fallback mode)

The game works even without any AI – it uses intelligent fallback responses. You can still play, but the stories will be simpler.

---

## 🚀 Running the Application

| Command | What it does |
|---------|--------------|
| `python run.py both` | Start **API + Gradio UI** (the normal way) |
| `python run.py api` | Start only the FastAPI backend |
| `python run.py gradio` | Start only the web UI (auto‑starts API if needed) |
| `python run.py telegram` | Start only the Telegram bot |
| `python run.py seed` | Seed test data into the database |
| `python run.py` | Interactive menu |

After starting, open:
- **Web UI:** http://127.0.0.1:7860
- **API docs:** http://127.0.0.1:8000/docs

---

## 🧪 Testing

```bash
# Run all tests (discovers every test_*.py in tests/)
python test.py

# Run a specific test
python tests/test_story_logic.py
```

All core features are tested – database, LLM, story logic, API, and UI dependencies.

---

## 📁 Project Structure (Simplified)

```
StoryPitch/
├── api/           # FastAPI backend (endpoints, auth)
├── db/            # SQLite database models + CRUD
├── llm/           # AI engine (LM Studio, Hugging Face, fallback)
├── story/         # Story logic, memory, prompts, parser
├── ui/            # Gradio web UI and Telegram bot
├── utils/         # Helpers: HTTP client, logging, performance, cache
├── tests/         # All test files
├── config.py      # Central configuration
├── constants.py   # Themes, traits, fallback texts
├── run.py         # Main launcher
└── requirements.txt
```

---

## 🔧 Configuration

Edit `config.py` to change:

- **API host/port** – `API_HOST`, `API_PORT`
- **LM Studio URL** – `LM_STUDIO_URL` (default `http://127.0.0.1:1234`)
- **Hugging Face model** – `HF_MODEL`
- **Story length** – `STORY_NARRATION_MIN_SENTENCES`, `STORY_NARRATION_MAX_SENTENCES`
- **Logging** – `LOG_LEVEL`, `LOG_RETENTION_MINUTES`

All settings have sensible defaults – you can start without changing anything.

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| **“Connection refused”** | Run `python run.py api` first, then the UI. |
| **LM Studio not responding** | Make sure a model is loaded and the Local Server is running (port 1234). |
| **Gradio won’t start** | `pip install gradio` or `pip install -r requirements.txt --force-reinstall` |
| **Database locked** | Close other programs that might be using `story.db`, then restart. |
| **Tests fail** | Run `python test.py` – the output tells you exactly what’s wrong. |

---

## 📄 License

This project is provided **as‑is** for educational and personal use.  
It is **100% free** – no monetisation, no analytics, no hidden costs.

---

## 🙏 Credits

**Created by Kamal** – with love for interactive storytelling and AI.  
Built on FastAPI, SQLModel, Gradio, LM Studio, and Hugging Face.

---

## 🌟 Quick Reference

```bash
python run.py both            # Start everything
python test.py                # Run all tests
python db_manager.py          # Manage database (list/delete users, sessions, saves)
```

**Now go create infinite adventures!** 🎭✨

