# StoryPitch — AI-Powered Dynamic Story Game Platform

## Complete Project Overview

---

## What Is StoryPitch?

**StoryPitch** is an **AI-powered interactive story game platform** where players shape dynamic narratives through their choices. The system generates unique, branching stories in real time — no two playthroughs are the same.

**Who it's for:** Gamers, writers, educators, and anyone who wants infinite stories where every decision matters.

**Two interfaces:** Custom web UI + Telegram bot.

---

## The Core Loop

1. Player creates a character (name + personality traits)
2. Player picks a story theme (fantasy, sci‑fi, mystery, or custom)
3. AI generates the first scene with 3‑4 choice buttons
4. Player either clicks a button OR types a custom action
5. AI generates the next scene based on the player's choice, their traits, discovered clues, and the story's memory
6. Repeat forever

---

## Features

### Story Generation

| Feature | What It Does |
|---------|---------------|
| Dynamic AI | Every scene is generated fresh — no fixed branches |
| Dual input modes | Button choices (guided) OR free‑text actions (creative freedom) |
| Trait influence | Character traits (brave, curious, etc.) subtly affect narration without being stated directly |
| Clue system | Discovered clues unlock new paths and options |
| Context awareness | AI remembers past events, locations, characters, and inventory |

### Save & Load System

| Feature | What It Does |
|---------|---------------|
| Multiple save slots | Unlimited saves per session |
| Custom names | Player names each save (e.g., "Before the dragon") |
| Auto‑description | System generates a preview of the saved moment |
| Full state restore | Loading a save restores story, memory, and progress exactly |
| Timeline integrity | Loading a save deletes all future steps — prevents corrupted timelines |

### Memory System (World State)

The AI automatically tracks everything that matters:

| Category | What's Tracked |
|----------|----------------|
| NPCs | Name, personality, when first met, how many interactions, notes |
| Locations | Name, description, how many times visited, last visit |
| Inventory | Items collected, descriptions, when acquired |
| Relationships | Affinity score, trust score, notes about each NPC |
| Events | Important moments, step number, importance level |
| Discoveries | Clues found, significance level, step number |

Memory persists across saves and loads. Player can view all tracked memory in the UI.  
A **“Refresh Memory”** button triggers a deeper AI analysis of recent narrations to extract or update memory.

### Character Traits

| Feature | What It Does |
|---------|---------------|
| Trait selection | Player chooses traits at start (brave, curious, clever, cautious, friendly, mysterious, etc.) |
| Subtle influence | Traits never appear explicitly in narration — they guide the player's "inner voice" and available options |
| Evolution | Traits can change as the story progresses |

### Story History

| Feature | What It Does |
|---------|---------------|
| Full history | View complete story from first scene to current point |
| Export | Download entire adventure as formatted text (or JSON via API) |
| Sharing | Perfect for saving or sharing your unique story |

### Database Admin (For Power Users)

| Feature | What It Does |
|---------|---------------|
| View all users | See every registered user |
| View all sessions | See every story session |
| View all saves | See every save file |
| Filter & sort | Filter by user, sort by date or step count |
| Delete anything | Remove users, sessions, or saves |
| Clear all data | Wipe everything with confirmation |

---

## AI Model Support

StoryPitch works with two AI backends:

| Option | What It Is | Best For |
|--------|------------|----------|
| **Offline (LM Studio)** | Local AI running on your own computer | Privacy, no internet required, free |
| **Online (HuggingFace)** | Cloud AI via API | More model variety, no local GPU needed |

**Fallback behavior:** If the chosen model fails, StoryPitch automatically tries the other. If both fail, it uses intelligent fallback responses — the app never crashes.

---

## Interfaces

### Custom Web UI (HTML / JavaScript)

The web frontend is a **single, beautiful HTML page** with tabbed navigation:

| Tab | What It Does |
|-----|---------------|
| **Play** | Full story game: character setup, story display, choice cards (or custom action), save/load management, summary generation |
| **Memory** | View all tracked NPCs, locations, inventory, relationships, events, discoveries. “Refresh Memory” button invokes AI analysis |
| **History** | See the complete story from start to current point, export as `.txt` |
| **Telegram** | A simulator that behaves exactly like the real Telegram bot – setup wizard, inline keyboards, all commands |
| **Admin** | Database management: list users/sessions, delete, clear all data |
| **Settings** | Theme (light/dark), font size, API base URL (persistent) |

**Key UI features:**
- Choice buttons appear as beautiful, selectable cards (click to highlight, then press Continue).
- Global processing lock – when AI is thinking, a banner appears and all relevant buttons are disabled.
- Dark/light mode toggle, font size adjustment.
- Responsive design – works on desktop and mobile.

### Telegram Bot

The real Telegram bot (optional, runs separately) offers the same features:

| Feature | What It Does |
|---------|---------------|
| Inline buttons | Choice buttons inside Telegram |
| Free‑text input | Type actions as messages |
| Multi‑session | Multiple simultaneous stories per user |
| Full setup wizard | Model, character name, theme, traits selection |
| Commands | `/save`, `/load`, `/saves`, `/memory`, `/history`, `/reset`, `/new` |

The web UI includes a **Telegram simulator tab** that mirrors the bot’s behaviour for testing and demonstration.

---

## Player Flow

### Step 1: Setup

Player provides (in the Play tab):
- Character name
- Character traits (select from list or type custom)
- Story theme (random, from list, or custom text)
- AI model preference (offline or online)

### Step 2: Story Begins

AI generates the opening scene with 3‑4 choice buttons.

### Step 3: Player Action

Player either:
- Clicks a choice button (highlights it) then presses **Continue** – guided path
- Switches to “Write Custom Action” mode, types an action, then presses **Continue** – creative path

### Step 4: AI Responds

AI generates:
- **Narration (5‑10 sentences)** – actual configured length
- New choice buttons (3‑4 options)
- Optional clues (hidden information)
- Matching emoji

### Step 5: Repeat

Steps 3‑4 repeat indefinitely. The story grows organically based on every decision.

### Step 6: Save Anytime

Player saves with custom name. Later loads restore exactly to that moment.

---

## What StoryPitch Does NOT Do

| Not a feature | Explanation |
|---------------|-------------|
| No pre‑written branches | Every scene is generated fresh by AI |
| No voice acting | Text‑only experience |
| No multiplayer | Single‑player only |
| No monetization | Free and open |
| No complex RPG mechanics | No stats, skill checks, or resource management |

---

## Technical Summary

| Layer | What It Is |
|-------|-------------|
| Backend | FastAPI — handles requests, sessions, AI routing, authentication |
| Database | SQLite — stores users, sessions, steps, snapshots |
| AI | LM Studio (offline) or HuggingFace (online) with cache & fallback |
| Web UI | Custom HTML/CSS/JS (no Gradio) – tabbed interface, responsive |
| Mobile UI | Telegram Bot API (real bot) + in‑page Telegram simulator |
| Memory | JSON stored in `world_state`, managed by `StoryMemory` class (automatic trimming) |
| Save system | Snapshots — complete world state saved, future steps deleted on load |
| Logging | Rotating file + automatic cleanup every 60 seconds |
| Processing lock | Global flag + banner to prevent concurrent LLM calls |

---

## Project Structure (Conceptual)

```
StoryPitch
├── API → Auth + Locking + Routing + Endpoints
├── Database → Users + Sessions + Steps + Snapshots
├── LLM → LM Studio + HuggingFace + Fallback + Cache
├── Story → Generator + Parser + Clues + Memory (NPCs, locations, inventory, relationships, events, discoveries)
├── UI → Custom Web UI (HTML/CSS/JS) + Telegram Bot
└── Utils → Logging + Formatting + Performance + HTTP Client + Log Cleaner
```

At runtime, a `story.db` file and a `logs/` folder are created.

---

## API Endpoints (Conceptual)

| Purpose | What It Does |
|---------|---------------|
| Health check | Confirms API is running |
| Create user | Registers a new player |
| Start session | Begins a new story with theme, traits, character name |
| Continue story | Sends player action → returns AI narration + new choices |
| Save game | Stores current story state with custom name |
| Load game | Restores story from a saved snapshot |
| Get all saves | Lists all save files for current session |
| Get memory | Returns tracked NPCs, locations, inventory, etc. |
| Refresh memory | Asks AI to analyze recent story and extract new memory |
| Get full story | Returns complete story history from start to current point |
| Summarize scene | AI generates a short summary of the current scene |
| List all users (admin) | Shows every registered user |
| List all sessions (admin) | Shows every story session |
| List all saves (admin) | Shows every save file |
| Delete user/session/save (admin) | Removes specific data |
| Clear all data (admin) | Deletes everything |

---

## Database Schema

| Table | What It Stores |
|-------|----------------|
| **User** | Username, when the account was created |
| **Session** | Story title, theme, character traits, character name, current step number, complete world state (JSON) |
| **Step** | Each story beat: player's action, AI's narration, available choices, any clues discovered |
| **Snapshot** | Each save file: custom name, auto‑generated description, complete world state, which step it was saved at |

**Relationships:**
- One User → many Sessions
- One Session → many Steps
- One Session → many Snapshots (saves)

---

## Summary

**StoryPitch is an AI‑powered interactive story game where every choice shapes a unique narrative — with full save/load, persistent memory, dual input modes, and both a custom web UI and a Telegram bot.**

- Dynamic AI storytelling — no fixed branches
- Button choices OR free‑text actions — switch anytime
- Game‑like save/load — multiple slots, custom names, full restore, timeline integrity
- Smart memory — tracks NPCs, locations, inventory, relationships, events, discoveries
- Traits influence without being stated directly
- Offline (LM Studio) + online (HuggingFace) AI support with fallback
- Beautiful custom web interface (HTML/CSS/JS) with dark mode and processing lock
- Telegram bot (real) + in‑page Telegram simulator
- Database admin for power users
- Export full story history as text

---

**Ready to create infinite adventures.** 🎭

