"""Conversation screen — unified voice-first chat interface."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime

import pygame

from devdash.config import AppConfig
from devdash.ui.renderer import Renderer
from devdash.services.voice_service import VoiceState

log = logging.getLogger(__name__)

MIC_BUTTON_H = 56
STATUS_BAR_H = 32
CONTENT_PAD = 8
MSG_GAP = 6
BUBBLE_PAD = 10
MAX_BUBBLE_W = 440  # 480 - margins


@dataclass
class Message:
    role: str  # "user" or "assistant"
    text: str
    timestamp: float = field(default_factory=time.time)


class ConversationScreen:
    def __init__(self, config: AppConfig, renderer: Renderer,
                 copilot_service, voice_service, system_service):
        self.config = config
        self.r = renderer
        self.copilot = copilot_service
        self.voice = voice_service
        self.system = system_service
        self.messages: list[Message] = []
        self.scroll_offset = 0
        self._streaming_text = ""
        self._is_streaming = False
        self._mic_rect: pygame.Rect | None = None

        self.messages.append(Message(
            role="assistant",
            text=("👋 Hi! I'm DevDash. Tap the mic and ask me "
                  "anything — CI status, PRs, standup, deploys, or code questions."),
        ))

    # ── Text wrapping ──

    def _wrap_text(self, text: str, font_key: str = "body",
                   max_w: int = MAX_BUBBLE_W - 2 * BUBBLE_PAD) -> list[str]:
        font = self.r.fonts.get(font_key, self.r.fonts["body"])
        lines: list[str] = []
        for paragraph in text.split("\n"):
            if not paragraph:
                lines.append("")
                continue
            words = paragraph.split()
            cur = ""
            for word in words:
                test = f"{cur} {word}".strip()
                if font.size(test)[0] > max_w:
                    if cur:
                        lines.append(cur)
                    cur = word
                else:
                    cur = test
            if cur:
                lines.append(cur)
        return lines or [""]

    def _msg_height(self, msg: Message) -> int:
        return len(self._wrap_text(msg.text)) * 20 + 2 * BUBBLE_PAD + MSG_GAP

    def _total_height(self) -> int:
        h = sum(self._msg_height(m) for m in self.messages)
        if self._is_streaming and self._streaming_text:
            h += len(self._wrap_text(self._streaming_text)) * 20 + 2 * BUBBLE_PAD + MSG_GAP
        return h

    # ── Rendering ──

    def render(self):
        self.r.clear()

        # Status bar
        time_str = datetime.now().strftime("%H:%M  %a %b %d")
        cpu_temp = self._read_cpu_temp()
        self.r.draw_status_bar(time_str, cpu_temp, "success")

        # Content area
        content_top = STATUS_BAR_H
        content_bot = self.r.height - MIC_BUTTON_H
        content_h = content_bot - content_top

        total = self._total_height()
        self.scroll_offset = max(0, total - content_h)

        clip = pygame.Rect(0, content_top, self.r.width, content_h)
        self.r.screen.set_clip(clip)

        y = content_top - self.scroll_offset
        for msg in self.messages:
            y = self._draw_bubble(msg, y)

        if self._is_streaming and self._streaming_text:
            y = self._draw_bubble(
                Message(role="assistant", text=self._streaming_text), y
            )

        self.r.screen.set_clip(None)

        # Mic button
        self._draw_mic_button()
        self.r.flip()

    def _draw_bubble(self, msg: Message, y: int) -> int:
        lines = self._wrap_text(msg.text)
        bubble_h = len(lines) * 20 + 2 * BUBBLE_PAD

        if msg.role == "user":
            bx = self.r.width - MAX_BUBBLE_W - CONTENT_PAD
            bg = "primary"
        else:
            bx = CONTENT_PAD
            bg = "surface"

        self.r.draw_rect(bx, y, MAX_BUBBLE_W, bubble_h, bg, border_radius=12)
        ty = y + BUBBLE_PAD
        for line in lines:
            self.r.draw_text(line, bx + BUBBLE_PAD, ty, "body", "text")
            ty += 20
        return y + bubble_h + MSG_GAP

    def _draw_mic_button(self):
        y = self.r.height - MIC_BUTTON_H
        self.r.draw_rect(0, y, self.r.width, MIC_BUTTON_H, "surface", border_radius=0)

        state = self.voice.state if self.voice.mic_available else VoiceState.IDLE

        if state == VoiceState.RECORDING:
            label, color = "🔴 Recording...", "error"
        elif state == VoiceState.TRANSCRIBING:
            label, color = "⏳ Transcribing...", "warning"
        elif self._is_streaming:
            label, color = "🧠 Thinking...", "info"
        elif not self.voice.mic_available:
            label, color = "🎤 No mic detected", "text_dim"
        else:
            label, color = "🎤 Tap to Speak", "primary"

        btn_w, btn_h = 280, MIC_BUTTON_H - 8
        btn_x = (self.r.width - btn_w) // 2
        btn_y = y + 4
        self._mic_rect = self.r.draw_button(label, btn_x, btn_y, btn_w, btn_h, color)

    # ── Interaction ──

    def handle_tap(self, x: int, y: int):
        if (self._mic_rect and self._mic_rect.collidepoint(x, y)
                and self.voice.state == VoiceState.IDLE
                and not self._is_streaming
                and self.voice.mic_available):
            asyncio.create_task(self._voice_flow())

    async def _voice_flow(self):
        """Record → transcribe → Copilot → display."""
        text = await self.voice.record_and_transcribe(
            max_seconds=self.config.voice.max_record_seconds,
        )
        if not text:
            return

        self.messages.append(Message(role="user", text=text))

        self._is_streaming = True
        self._streaming_text = ""

        def on_delta(delta: str):
            self._streaming_text += delta

        try:
            result = await self.copilot.chat(text, on_delta=on_delta)
            answer = result.get("answer", self._streaming_text or "Sorry, I couldn't process that.")
            self.messages.append(Message(role="assistant", text=answer))
        except Exception as e:
            log.error("Copilot error: %s", e)
            self.messages.append(Message(role="assistant", text=f"Error: {e}"))
        finally:
            self._is_streaming = False
            self._streaming_text = ""

    # ── Helpers ──

    @staticmethod
    def _read_cpu_temp() -> str:
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return f"{int(f.read().strip()) / 1000:.0f}°C"
        except (FileNotFoundError, ValueError):
            return ""
