# DevDash — The Physical Developer Companion

> An always-on Raspberry Pi 5 desk device that bridges the gap between your codebase and the physical world — powered by the GitHub Copilot SDK.

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)
![Copilot SDK](https://img.shields.io/badge/copilot--sdk-powered-green)
![Raspberry Pi 5](https://img.shields.io/badge/raspberry--pi-5-red)

## What It Does

DevDash turns a Raspberry Pi 5 with a 3.5" touch screen into an AI-powered developer companion that GitHub Desktop literally cannot be:

| Feature | Description |
|---------|-------------|
| 🧠 **CI Auto-Diagnosis** | Copilot reads CI logs, traces errors to commits, suggests fixes, creates fix PRs |
| 👆 **Swipe PR Triage** | Tinder-style: swipe right to approve, left to reject, with AI risk scoring |
| 🚨 **Ambient LED Status** | NeoPixel LEDs glow green/yellow/red based on repo health — visible across the room |
| 📋 **Morning Standup** | AI-generated briefing of overnight activity across all your repos |
| 🔘 **Smart Deploy Button** | Physical button + Copilot safety analysis before triggering deploys |
| 🧩 **Context Keeper** | Persistent AI memory about your codebase, queryable by voice or tap |

## Hardware Requirements

- Raspberry Pi 5 (4GB+ RAM)
- 3.5" SPI/HDMI touch screen (480×320)
- WS2812B NeoPixel LED strip (8 LEDs)
- Momentary push button + 10kΩ resistor
- Piezo buzzer (passive, optional)
- Breadboard + jumper wires
- USB microphone (optional, enables voice input)

## Quick Start

```bash
# Clone the repo
git clone https://github.com/yourusername/raspi-demo.git
cd raspi-demo

# Run setup (installs dependencies, configures GPIO)
chmod +x setup.sh
./setup.sh

# Copy and edit config
cp config.example.yaml config.yaml
# Edit config.yaml with your GitHub token and repos

# Run DevDash
python -m devdash
```

## Configuration

Copy `config.example.yaml` to `config.yaml` and set:

- `github.token` — Personal access token with `repo`, `workflow` scopes
- `github.repos` — List of repos to monitor (e.g., `owner/repo`)
- `gpio.led_pin` — NeoPixel data pin (default: 18)
- `gpio.button_pin` — Deploy button pin (default: 17)
- `gpio.buzzer_pin` — Buzzer pin (default: 13)

## Architecture

DevDash uses a single `CopilotClient` with multiple specialized AI sessions:

- **CI Diagnosis Agent** — Custom tools for log fetching, code reading, PR creation
- **PR Triage Agent** — Diff analysis, risk scoring, review submission
- **Standup Agent** — Cross-repo activity aggregation
- **Deploy Agent** — Safety checks with physical button confirmation (pre-tool hooks)
- **Context Keeper** — Infinite sessions with persistent SQLite memory

All interactions are zero-keyboard: swipe, tap, physical button, or voice.

## Tech Stack

- **UI**: PyGame (480×320 touch-optimized, dark theme)
- **AI**: GitHub Copilot SDK (`github-copilot-sdk`)
- **Voice**: `faster-whisper` (local Whisper model, fully offline)
- **Hardware**: `rpi_ws281x` (NeoPixels), `RPi.GPIO` (button/buzzer)
- **API**: PyGithub + GitHub REST API
- **Storage**: SQLite (caching + AI memory)
- **Config**: YAML

## License

MIT
