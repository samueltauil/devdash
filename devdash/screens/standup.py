"""Morning Standup screen — AI-generated daily briefing."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from devdash.screens.base import BaseScreen
from devdash.ui.widgets import BigButton
from devdash.ui import theme as T

log = logging.getLogger(__name__)


class StandupScreen(BaseScreen):
    name = "standup"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.content: str = ""
        self.content_lines: list[str] = []
        self.scroll_offset = 0
        self._loading = False
        self._streaming_text = ""
        self._generated_today = False

    async def render(self):
        y = T.CONTENT_Y + 8

        # Header
        today = datetime.now().strftime("%a %b %d")
        self.renderer.draw_text("☀ Morning Standup", 12, y, "heading", "text")
        self.renderer.draw_text(today, self.config.display.width - 100, y + 4, "small", "text_dim")
        y += 36

        if self._loading:
            self.renderer.draw_text("🤖 Copilot generating standup...", 40, y + 40, "body", "info")
            if self._streaming_text:
                # Show live text
                lines = self._streaming_text.split("\n")
                for line in lines[-6:]:  # Show last 6 lines
                    self.renderer.draw_text(line[:55], 16, y, "body", "text",
                                            max_width=self.config.display.width - 32)
                    y += 22
            return

        if not self.content_lines:
            self.renderer.draw_text("Tap to generate today's standup", 60, y + 60, "body", "text_dim")
            self.button_rects["generate"] = BigButton.draw(
                self.renderer, "Generate Standup", 140, y + 100, 200, color="primary", icon="☀"
            )
            return

        # Show standup content (scrollable)
        visible_lines = 8
        start = self.scroll_offset
        end = min(start + visible_lines, len(self.content_lines))

        for i in range(start, end):
            line = self.content_lines[i]
            color = "text"
            if line.startswith("🚢") or line.startswith("⚠") or line.startswith("📋"):
                color = "accent"
            self.renderer.draw_text(line[:55], 16, y, "body", color,
                                    max_width=self.config.display.width - 32)
            y += 22

        if end < len(self.content_lines):
            self.renderer.draw_text("↓ scroll for more", self.config.display.width // 2 - 60,
                                    y + 4, "small", "text_dim")

        # Copy button
        btn_y = self.config.display.height - T.NAV_BAR_HEIGHT - T.BUTTON_HEIGHT - 8
        self.button_rects["copy"] = BigButton.draw(
            self.renderer, "📋 Copy to Clipboard", 120, btn_y, 240, color="primary"
        )

    def on_enter(self):
        super().on_enter()
        if not self._generated_today:
            # Check if we have a cached standup for today
            asyncio.create_task(self._load_cached())

    async def _load_cached(self):
        today = datetime.now().strftime("%Y-%m-%d")
        standup = await self.db.get_latest_standup()
        if standup and standup.get("date") == today:
            self.content = standup["content"]
            self.content_lines = self.content.split("\n")
            self._generated_today = True

    async def refresh_data(self):
        pass  # Standup is generated on-demand

    def on_button_tap(self, button_name: str):
        if button_name == "generate":
            asyncio.create_task(self._generate_standup())
        elif button_name == "copy":
            self._copy_to_clipboard()

    def on_swipe_up(self, gesture):
        if self.content_lines:
            self.scroll_offset = min(self.scroll_offset + 3,
                                     max(0, len(self.content_lines) - 6))

    def on_swipe_down(self, gesture):
        self.scroll_offset = max(0, self.scroll_offset - 3)

    async def _generate_standup(self):
        self._loading = True
        self._streaming_text = ""
        try:
            result = await self.copilot.generate_standup(
                repos=self.config.github.repos,
                lookback_hours=self.config.standup.lookback_hours,
                on_delta=lambda text: self._on_stream(text),
            )
            self.content = result.get("standup", "")
            self.content_lines = self.content.split("\n")
            self._generated_today = True

            # Cache it
            today = datetime.now().strftime("%Y-%m-%d")
            await self.db.save_standup(today, self.content)
        except Exception as e:
            log.error("Standup generation error: %s", e)
            self.content_lines = ["Standup generation failed. Tap to retry."]
        finally:
            self._loading = False

    def _on_stream(self, text: str):
        self._streaming_text += text

    def _copy_to_clipboard(self):
        """Copy standup text to system clipboard."""
        try:
            import subprocess
            process = subprocess.Popen(["xclip", "-selection", "clipboard"],
                                       stdin=subprocess.PIPE)
            process.communicate(self.content.encode())
            log.info("Standup copied to clipboard")
        except Exception:
            log.warning("Clipboard copy failed — xclip not available")
