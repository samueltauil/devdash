"""YAML-based configuration loader."""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

log = logging.getLogger(__name__)

CONFIG_PATH = Path("config.yaml")


@dataclass
class GitHubConfig:
    token: str = ""
    username: str = ""
    repos: list[str] = field(default_factory=list)
    poll_interval: int = 120


@dataclass
class CopilotConfig:
    cli_path: str = "copilot"
    model: str = "gpt-4.1"


@dataclass
class DisplayConfig:
    width: int = 480
    height: int = 320
    fps: int = 30
    fullscreen: bool = True


@dataclass
class GPIOConfig:
    led_pin: int = 18
    led_count: int = 8
    led_brightness: int = 50
    button_pin: int = 17
    buzzer_pin: int = 13


@dataclass
class DeployConfig:
    repo: str = ""
    workflow: str = "deploy.yml"
    ref: str = "main"
    environment: str = "production"
    min_confidence: int = 70


@dataclass
class StandupConfig:
    schedule_hour: int = 8
    lookback_hours: int = 16


@dataclass
class ThemeConfig:
    background: str = "#1a1a2e"
    surface: str = "#16213e"
    primary: str = "#0f3460"
    accent: str = "#e94560"
    text: str = "#eaeaea"
    text_dim: str = "#8892a0"
    success: str = "#00c853"
    warning: str = "#ffd600"
    error: str = "#ff1744"
    info: str = "#2979ff"

    def color(self, name: str) -> tuple[int, int, int]:
        """Convert a hex color string to an RGB tuple."""
        hex_str = getattr(self, name, self.text)
        hex_str = hex_str.lstrip("#")
        return (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))


@dataclass
class AppConfig:
    github: GitHubConfig = field(default_factory=GitHubConfig)
    copilot: CopilotConfig = field(default_factory=CopilotConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    gpio: GPIOConfig = field(default_factory=GPIOConfig)
    deploy: DeployConfig = field(default_factory=DeployConfig)
    standup: StandupConfig = field(default_factory=StandupConfig)
    theme: ThemeConfig = field(default_factory=ThemeConfig)


def _merge_dict_to_dataclass(dc, d: dict):
    """Recursively merge a dict into a dataclass instance."""
    for key, value in d.items():
        if hasattr(dc, key):
            attr = getattr(dc, key)
            if isinstance(value, dict) and hasattr(attr, "__dataclass_fields__"):
                _merge_dict_to_dataclass(attr, value)
            else:
                setattr(dc, key, value)


def load_config(path: Optional[Path] = None) -> AppConfig:
    """Load configuration from YAML file, with env var overrides."""
    path = path or CONFIG_PATH
    config = AppConfig()

    if path.exists():
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
        _merge_dict_to_dataclass(config, raw)
        log.info("Loaded config from %s", path)
    else:
        log.warning("No config.yaml found — using defaults")

    # Environment variable overrides
    if token := os.environ.get("GITHUB_TOKEN"):
        config.github.token = token
    if copilot_path := os.environ.get("COPILOT_CLI_PATH"):
        config.copilot.cli_path = copilot_path

    return config
