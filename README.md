# DevDash — Voice-First Developer Companion

> A Raspberry Pi 5 desk device with a 3.5" LCD and USB microphone — talk to your repos, powered by the GitHub Copilot SDK.

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)
![Copilot SDK](https://img.shields.io/badge/copilot--sdk-powered-green)
![Raspberry Pi 5](https://img.shields.io/badge/raspberry--pi-5-red)

## What It Does

DevDash is a **voice-first conversational interface** that lets you interact with your GitHub repositories using natural language. Just tap the mic and speak:

- 🧠 **"What's failing in CI?"** → Fetches failed runs, diagnoses errors, suggests fixes
- 📋 **"Give me a standup"** → AI-generated briefing of overnight activity across repos
- 👆 **"Show me open PRs"** → Lists PRs with AI risk analysis
- 🚀 **"Deploy to production"** → Safety checks + workflow trigger
- 🧩 **"How does auth work in this repo?"** → Searches codebase context, remembers answers

All powered by a single Copilot SDK agent with persistent memory.

---

## 🔌 Hardware Requirements

| Item | Purpose |
|------|---------|
| **Raspberry Pi 5** (8GB recommended) | Runs the app + local Whisper model |
| **3.5" SPI LCD screen** | Displays conversation UI (480×320) |
| **USB microphone** | Voice input for hands-free interaction |

That's it — no breadboard, no wiring, no GPIO components.

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/samueltauil/devdash.git
cd devdash

# Run setup (installs dependencies)
chmod +x setup.sh
./setup.sh

# Copy and edit config
cp config.example.yaml config.yaml
# Edit config.yaml with your GitHub token and repos

# Run DevDash
source .venv/bin/activate
python -m devdash
```

## Configuration

Copy `config.example.yaml` to `config.yaml` and set:

- `github.token` — Personal access token with `repo`, `workflow` scopes
- `github.repos` — List of repos to monitor (e.g., `owner/repo`)
- `voice.model_size` — Whisper model: `tiny`, `base`, `small`, `medium` (default), `large`

## Architecture

```
┌─────────────────────────────────────┐
│          DevDash Voice-First        │
│                                     │
│  ┌───────────────────────────────┐  │
│  │   3.5" LCD (480×320)         │  │
│  │   ┌─────────────────────┐    │  │
│  │   │  Conversation View  │    │  │
│  │   │  (scrollable)       │    │  │
│  │   │                     │    │  │
│  │   │  User: "what's      │    │  │
│  │   │  failing in CI?"    │    │  │
│  │   │                     │    │  │
│  │   │  Copilot: "Build    │    │  │
│  │   │  #42 in repo/x..."  │    │  │
│  │   └─────────────────────┘    │  │
│  │   [  🎤 Tap to Speak  ]     │  │
│  └───────────────────────────────┘  │
│                                     │
│  USB Mic ──► Whisper (local STT)    │
│          ──► Copilot SDK            │
│          ──► GitHub API             │
│          ──► SQLite                 │
└─────────────────────────────────────┘
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| UI | PyGame (480×320, dark theme, conversation view) |
| AI Engine | [GitHub Copilot SDK](https://github.com/github/copilot-sdk) |
| Voice | `faster-whisper` (local Whisper model, fully offline) |
| API | PyGithub + GitHub REST API |
| Storage | SQLite (caching + AI memory) |
| Config | YAML |
| Auto-start | systemd service |

## Project Structure

```
devdash/
├── main.py                 # Entry point, async event loop
├── config.py               # YAML config loader
├── database.py             # SQLite (cache, AI memory, history)
├── screens/
│   └── conversation.py     # Unified voice chat interface
├── services/
│   ├── copilot_service.py  # Copilot SDK — single unified agent
│   ├── github_service.py   # GitHub API + caching
│   ├── voice_service.py    # USB mic + local Whisper STT
│   └── system_service.py   # CPU temp, memory, uptime
└── ui/
    ├── renderer.py         # PyGame display + drawing
    ├── touch.py            # Tap detection
    ├── widgets.py          # Chat bubbles, mic button
    └── theme.py            # Colors, layout constants
```

## License

MIT
