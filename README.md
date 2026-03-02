# DevDash — Voice-First AI Developer Companion

> A Raspberry Pi 5 desk device with a 3.5" SPI LCD and USB microphone — talk to your repos using natural language, powered by GitHub's AI.

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)
![GitHub Models](https://img.shields.io/badge/github--models-AI-green)
![Raspberry Pi 5](https://img.shields.io/badge/raspberry--pi-5-red)

## What It Does

DevDash is a **voice-first conversational interface** that lives on your desk. Tap the mic, speak naturally, and get AI-powered answers about your GitHub repositories — all rendered on a 3.5" LCD with an animated Mona (Octocat) avatar.

- 🧠 **"What's failing in CI?"** → Fetches failed workflow runs, diagnoses errors
- 📋 **"Give me a standup"** → AI-generated briefing of recent repo activity
- 👆 **"Show me open PRs"** → Lists pull requests with context
- 🚀 **"Deploy to production"** → Safety checks + workflow trigger
- 💬 **"What does this project do?"** → General dev Q&A via AI

### How It Works

```
🎤 Voice → Whisper (local STT) → GitHub Models API (AI) → 3.5" LCD
```

1. **Tap** the mic button on the touchscreen
2. **Speak** your question naturally
3. **Whisper** transcribes locally on the Pi (fully offline STT)
4. **GitHub Models API** generates a contextual response
5. **Mona** reacts with animated expressions while thinking/speaking

---

## Hardware

| Item | Purpose |
|------|---------|
| **Raspberry Pi 5** (8GB recommended) | Runs the app + local Whisper model |
| **3.5" SPI LCD** (480×320, ILI9486) | Displays the UI via fbdev/X11 |
| **USB microphone** (e.g., Blue Yeti Nano) | Voice input |

No breadboard, no GPIO wiring — just plug in the screen and mic.

---

## Quick Start

### 1. Setup

```bash
git clone https://github.com/samueltauil/devdash.git
cd devdash

chmod +x setup.sh
./setup.sh
```

### 2. Configure

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml`:

| Setting | Description |
|---------|-------------|
| `github.token` | GitHub Personal Access Token (`repo`, `workflow` scopes) |
| `github.username` | Your GitHub username |
| `github.repos` | Repos to monitor, e.g., `["owner/repo"]` |
| `voice.model_size` | Whisper model: `tiny`, `base`, `small`, `medium` (default), `large` |

### 3. Run

```bash
source .venv/bin/activate
python -m devdash
```

### 4. Auto-Start (systemd)

```bash
sudo cp systemd/devdash.service /etc/systemd/system/
sudo systemctl enable --now devdash
```

> **Note:** The SPI LCD requires an X server on `:0`. See [Display Setup](#display-setup) below.

---

## Display Setup

The 3.5" SPI LCD uses the `fb_ili9486` framebuffer driver. DevDash renders via PyGame on an X11 display.

**X server config** (`/etc/X11/xorg.conf.d/99-spi-lcd.conf`):

```
Section "Device"
    Identifier "SPI LCD"
    Driver     "fbdev"
    Option     "fbdev" "/dev/fb0"
EndSection

Section "Screen"
    Identifier "Default Screen"
    Device     "SPI LCD"
    DefaultDepth 16
EndSection
```

> **Important:** Use `DefaultDepth 16` — the ILI9486 framebuffer is 16-bit. Using 24-bit will crash X.

Start X before DevDash:

```bash
sudo X :0 vt1 &
```

---

## Architecture

```
┌─────────────────────────────────────────┐
│              DevDash                    │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │   3.5" LCD (480×320)             │  │
│  │                                   │  │
│  │      ┌──────────────┐            │  │
│  │      │   🐙 Mona    │  ← SVG    │  │
│  │      │  (animated)  │    avatar  │  │
│  │      └──────────────┘            │  │
│  │       « DevDash »                │  │
│  │                                   │  │
│  │  ┌────────────────────────────┐  │  │
│  │  │  Chat bubbles (scroll)    │  │  │
│  │  └────────────────────────────┘  │  │
│  │  [  🎤 Tap to Speak  ]         │  │
│  └───────────────────────────────────┘  │
│                                         │
│  USB Mic ──► faster-whisper (local)     │
│          ──► GitHub Models API (AI)     │
│          ──► PyGithub (REST API)        │
│          ──► SQLite (cache + memory)    │
└─────────────────────────────────────────┘
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| UI | PyGame on X11 (480×320, dark theme) |
| Avatar | Official Octocat SVG via `cairosvg` with animated overlays |
| AI | GitHub Models API (GPT-4o-mini) with Copilot SDK support |
| Voice | `faster-whisper` — local Whisper model, fully offline STT |
| GitHub API | PyGithub — PRs, CI runs, commits, workflow dispatch |
| Storage | SQLite via `aiosqlite` — caching, AI memory, history |
| Config | YAML |
| Auto-start | systemd service |

## Project Structure

```
devdash/
├── main.py                 # Entry point, async event loop
├── config.py               # YAML config loader
├── database.py             # SQLite (cache, AI memory, history)
├── assets/
│   └── octocat.svg         # Official GitHub Octocat SVG
├── screens/
│   └── conversation.py     # Splash screen + voice chat interface
├── services/
│   ├── copilot_service.py  # AI chat (GitHub Models API / Copilot SDK)
│   ├── github_service.py   # GitHub REST API + polling
│   ├── voice_service.py    # USB mic + local Whisper STT
│   └── system_service.py   # CPU temp, memory, uptime
└── ui/
    ├── mona.py             # Animated Octocat avatar (SVG + effects)
    ├── renderer.py         # PyGame display + drawing helpers
    ├── touch.py            # Tap detection
    ├── widgets.py          # Chat bubbles, mic button
    └── theme.py            # Colors, fonts, layout constants
```

## AI Backend

DevDash uses a dual-backend approach for AI:

1. **GitHub Models API** (default) — Uses your GitHub token to call `models.inference.ai.azure.com`. Works out of the box with any GitHub account that has Models access.
2. **Copilot SDK** (optional) — If the `github-copilot-sdk` package is installed, DevDash uses it with tool-calling support for richer GitHub integration.

The AI maintains conversation history for contextual follow-up questions.

## License

MIT
