"""Context Keeper screen — persistent AI memory, queryable by tap or voice."""

from __future__ import annotations

import asyncio
import logging

from devdash.screens.base import BaseScreen
from devdash.ui.widgets import BigButton
from devdash.ui import theme as T

log = logging.getLogger(__name__)

# Pre-set quick questions (no keyboard needed)
QUICK_QUESTIONS = [
    "Who owns this area?",
    "What broke last?",
    "Safe to refactor?",
    "Why this design?",
]


class ContextChatScreen(BaseScreen):
    name = "context_chat"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.answer: str = ""
        self.answer_lines: list[str] = []
        self.last_question: str = ""
        self._loading = False
        self._streaming_text = ""
        self._voice_available = False
        self._voice_input = None

    async def render(self):
        y = T.CONTENT_Y + 8

        # Header
        self.renderer.draw_text("🧠 Ask Copilot", 12, y, "heading", "text")

        # Voice mic button (if available)
        if self._voice_available:
            self.button_rects["voice"] = BigButton.draw(
                self.renderer, "🎤", self.config.display.width - 60, y - 4, 48, 36, color="accent"
            )
        y += 40

        if self._loading:
            self.renderer.draw_text("🤖 Thinking...", 40, y, "body", "info")
            y += 24
            if self._streaming_text:
                for line in self._streaming_text.split("\n")[-5:]:
                    self.renderer.draw_text(line[:55], 16, y, "body", "text")
                    y += 22
            return

        if self.answer_lines:
            # Show answer
            self.renderer.draw_text(f'Q: "{self.last_question}"', 16, y, "small", "text_dim")
            y += 24
            for line in self.answer_lines[:7]:
                self.renderer.draw_text(line[:55], 16, y, "body", "text",
                                        max_width=self.config.display.width - 32)
                y += 22
        else:
            # Show quick question buttons
            self.renderer.draw_text("Quick Questions:", 16, y, "body", "text_dim")
            y += 28

            btn_w = (self.config.display.width - 3 * T.CARD_MARGIN) // 2
            btn_h = 48

            for i, question in enumerate(QUICK_QUESTIONS):
                col = i % 2
                row = i // 2
                bx = T.CARD_MARGIN + col * (btn_w + T.CARD_MARGIN)
                by = y + row * (btn_h + 8)
                self.button_rects[f"q{i}"] = BigButton.draw(
                    self.renderer, question, bx, by, btn_w, btn_h, color="surface"
                )

    def on_enter(self):
        super().on_enter()
        self._check_voice()

    def _check_voice(self):
        """Auto-detect USB microphone."""
        try:
            from devdash.hardware.voice_input import VoiceInput
            if self._voice_input is None:
                self._voice_input = VoiceInput()
            self._voice_available = self._voice_input.mic_available
        except ImportError:
            self._voice_available = False

    def on_button_tap(self, button_name: str):
        if button_name == "voice":
            asyncio.create_task(self._voice_query())
        elif button_name.startswith("q"):
            idx = int(button_name[1:])
            if idx < len(QUICK_QUESTIONS):
                asyncio.create_task(self._ask_question(QUICK_QUESTIONS[idx]))

    async def _ask_question(self, question: str):
        self._loading = True
        self._streaming_text = ""
        self.last_question = question

        try:
            result = await self.copilot.ask_context_keeper(
                question=question,
                on_delta=lambda text: self._on_stream(text),
            )
            self.answer = result.get("answer", "")
            self.answer_lines = self.answer.split("\n")
        except Exception as e:
            log.error("Context query error: %s", e)
            self.answer_lines = ["Failed to get answer. Try again."]
        finally:
            self._loading = False

    async def _voice_query(self):
        """Record voice, transcribe locally, then ask Copilot."""
        if not self._voice_available or not self._voice_input:
            return

        try:
            # Load model if needed
            await self._voice_input.load_model()

            # Show recording indicator
            self._loading = True
            self._streaming_text = "🎤 Listening..."

            text = await self._voice_input.record_and_transcribe()
            if text:
                self._streaming_text = f'Heard: "{text}"\n🤖 Thinking...'
                await self._ask_question(text)
            else:
                self._loading = False
                self._streaming_text = ""
        except Exception as e:
            log.error("Voice input error: %s", e)
            self._loading = False

    def _on_stream(self, text: str):
        self._streaming_text += text
