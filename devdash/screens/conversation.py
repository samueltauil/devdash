"""Conversation screen — voice-first chat with animated Mona avatar."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime

import pygame

from devdash.config import AppConfig
from devdash.ui.renderer import Renderer
from devdash.ui.mona import MonaAvatar, IDLE, LISTENING, THINKING, SPEAKING, HAPPY
from devdash.services.voice_service import VoiceState

log = logging.getLogger(__name__)

# Layout
STATUS_H   = 28
BOTTOM_H   = 60
CONTENT_PAD = 10
MSG_GAP     = 8
BUBBLE_PAD  = 10
MAX_BUBBLE_W = 430

# Idle wander animation timing
WANDER_PAUSE   = 5.0    # seconds idle at center before wandering
WANDER_WALK    = 3.0    # seconds to walk to a side
WANDER_WAIT    = 1.5    # seconds to pause at the side
WANDER_RETURN  = 3.0    # seconds to walk back to center


@dataclass
class Message:
    role: str
    text: str
    ts: float = field(default_factory=time.time)


class ConversationScreen:
    def __init__(self, config: AppConfig, renderer: Renderer,
                 copilot_service, voice_service, system_service):
        self.config = config
        self.r = renderer
        self.copilot = copilot_service
        self.voice = voice_service
        self.system = system_service

        self.messages: list[Message] = []
        self.scroll_y = 0
        self._stream_buf = ""
        self._streaming = False
        self._mic_rect: pygame.Rect | None = None
        self._happy_until = 0.0

        self.mona = MonaAvatar()
        self._splash_start = time.time()
        # Wander state: "idle" | "walk_out" | "pause_side" | "walk_back"
        self._wander_state = "idle"
        self._wander_timer = 0.0
        self._wander_dir = 1       # 1 = right, -1 = left
        self._wander_x = 0.0       # normalized offset from center (-1..1)

    # ── helpers ──────────────────────────────────────────────────────

    @property
    def _in_splash(self) -> bool:
        return len(self.messages) == 0

    def _wrap(self, text: str, font_key: str = "body",
              max_w: int = MAX_BUBBLE_W - 2 * BUBBLE_PAD) -> list[str]:
        font = self.r.fonts.get(font_key, self.r.fonts["body"])
        out: list[str] = []
        for para in text.split("\n"):
            if not para:
                out.append("")
                continue
            cur = ""
            for word in para.split():
                test = f"{cur} {word}".strip()
                if font.size(test)[0] > max_w:
                    if cur:
                        out.append(cur)
                    cur = word
                else:
                    cur = test
            if cur:
                out.append(cur)
        return out or [""]

    def _msg_h(self, msg: Message) -> int:
        return len(self._wrap(msg.text)) * 20 + 2 * BUBBLE_PAD + MSG_GAP

    def _total_h(self) -> int:
        h = sum(self._msg_h(m) for m in self.messages)
        if self._streaming and self._stream_buf:
            h += len(self._wrap(self._stream_buf)) * 20 + 2 * BUBBLE_PAD + MSG_GAP
        return h

    @staticmethod
    def _cpu_temp() -> str:
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return f"{int(f.read().strip()) / 1000:.0f}°C"
        except (FileNotFoundError, ValueError):
            return ""

    # ── Mona state sync ──────────────────────────────────────────────

    def _sync_mona(self):
        if time.time() < self._happy_until:
            self.mona.set_state(HAPPY)
            return
        vs = self.voice.state if self.voice.mic_available else VoiceState.IDLE
        if vs == VoiceState.RECORDING:
            self.mona.set_state(LISTENING)
        elif vs == VoiceState.TRANSCRIBING:
            self.mona.set_state(THINKING)
        elif self._streaming:
            self.mona.set_state(SPEAKING)
        else:
            self.mona.set_state(IDLE)

    # ── render ───────────────────────────────────────────────────────

    def render(self):
        self._sync_mona()
        self.r.clear()

        # ── status bar ───────────────────────────────────────────────
        self._draw_status_bar()

        if self._in_splash:
            self._draw_splash()
        else:
            self._draw_chat()

        # ── bottom bar (Mona + mic) ──────────────────────────────────
        self._draw_bottom_bar()

        self.r.flip()

    # ── status bar ───────────────────────────────────────────────────

    def _draw_status_bar(self):
        self.r.draw_rect(0, 0, self.r.width, STATUS_H, "surface", border_radius=0)
        # accent stripe
        pygame.draw.rect(self.r.screen,
            self.r.colors.get("accent", (233,69,96)),
            pygame.Rect(0, STATUS_H - 2, self.r.width, 2))

        ts = datetime.now().strftime("%H:%M")
        self.r.draw_text(ts, 10, 5, "small", "text_dim")
        self.r.draw_text("DevDash", self.r.width // 2 - 28, 5, "small", "text")
        temp = self._cpu_temp()
        if temp:
            self.r.draw_text(temp, self.r.width - 42, 5, "small", "text_dim")
        # status dot
        dot_col = self.r.colors.get("success", (0,200,83))
        pygame.draw.circle(self.r.screen, dot_col, (self.r.width - 12, STATUS_H // 2), 4)

    # ── splash (no messages yet) ─────────────────────────────────────

    def _draw_splash(self):
        center_x = self.r.width // 2
        center_y = (STATUS_H + self.r.height - BOTTOM_H) // 2

        # Mona + title sizing
        avail = self.r.height - STATUS_H - BOTTOM_H - 40
        mona_h = min(avail, 180)
        title_font = self.r.fonts.get("large", self.r.fonts["heading"])
        title_text = "DevDash"
        title_h = title_font.get_height()
        gap = 4
        total_h = mona_h + gap + title_h
        mona_cy = center_y - total_h // 2 + mona_h // 2
        ty = mona_cy + mona_h // 2 + gap

        # ── Wander disabled — Mona stays centered ────────────────────
        mona_x = center_x

        # Draw Mona
        self.mona.draw(self.r.screen, mona_x, mona_cy, size=mona_h)

        # Title stays centered (doesn't follow Mona)
        accent = self.r.colors.get("accent", (233, 69, 96))
        info = self.r.colors.get("info", (41, 121, 255))
        letters = title_text
        spacing = 3
        total_tw = sum(title_font.size(ch)[0] for ch in letters) + spacing * (len(letters) - 1)
        lx = center_x - total_tw // 2

        t_val = time.time()
        for idx, ch in enumerate(letters):
            t = idx / max(1, len(letters) - 1)
            phase = 0.5 + 0.5 * math.sin(t * math.pi + t_val * 0.8)
            r = int(accent[0] + (info[0] - accent[0]) * phase)
            g = int(accent[1] + (info[1] - accent[1]) * phase)
            b = int(accent[2] + (info[2] - accent[2]) * phase)

            glow = title_font.render(ch, True, (r, g, b))
            glow.set_alpha(40)
            self.r.screen.blit(glow, (lx - 1, ty - 1))
            self.r.screen.blit(glow, (lx + 1, ty + 1))

            letter = title_font.render(ch, True, (r, g, b))
            self.r.screen.blit(letter, (lx, ty))

            lx += title_font.size(ch)[0] + spacing

    # ── chat mode ────────────────────────────────────────────────────

    def _draw_chat(self):
        top = STATUS_H
        bot = self.r.height - BOTTOM_H
        area_h = bot - top

        total = self._total_h()
        self.scroll_y = max(0, total - area_h)

        clip = pygame.Rect(0, top, self.r.width, area_h)
        self.r.screen.set_clip(clip)

        y = top - self.scroll_y
        for msg in self.messages:
            y = self._draw_msg(msg, y)

        if self._streaming and self._stream_buf:
            y = self._draw_msg(Message(role="assistant", text=self._stream_buf), y)

        self.r.screen.set_clip(None)

    def _draw_msg(self, msg: Message, y: int) -> int:
        lines = self._wrap(msg.text)
        bh = len(lines) * 20 + 2 * BUBBLE_PAD

        if msg.role == "user":
            bx = self.r.width - MAX_BUBBLE_W - CONTENT_PAD
            bg = "primary"
            # user indicator dot
            dot_x = self.r.width - CONTENT_PAD + 4
            pygame.draw.circle(self.r.screen,
                self.r.colors.get("info", (41,121,255)),
                (dot_x, y + 14), 4)
        else:
            bx = CONTENT_PAD
            bg = "surface"
            # Mona indicator dot
            dot_x = CONTENT_PAD - 8
            pygame.draw.circle(self.r.screen,
                self.r.colors.get("accent", (233,69,96)),
                (dot_x, y + 14), 4)

        self.r.draw_rect(bx, y, MAX_BUBBLE_W, bh, bg, border_radius=10)
        ty = y + BUBBLE_PAD
        for line in lines:
            self.r.draw_text(line, bx + BUBBLE_PAD, ty, "body", "text")
            ty += 20
        return y + bh + MSG_GAP

    # ── bottom bar ───────────────────────────────────────────────────

    def _draw_bottom_bar(self):
        by = self.r.height - BOTTOM_H
        self.r.draw_rect(0, by, self.r.width, BOTTOM_H, "surface", border_radius=0)
        # top accent line
        pygame.draw.rect(self.r.screen,
            self.r.colors.get("primary", (15,52,96)),
            pygame.Rect(0, by, self.r.width, 1))

        # Mona mini avatar (left side)
        mona_cx = 32
        mona_cy = by + BOTTOM_H // 2
        self.mona.draw_mini(self.r.screen, mona_cx, mona_cy, size=36)

        # Mic button (right of Mona)
        vs = self.voice.state if self.voice.mic_available else VoiceState.IDLE
        if vs == VoiceState.RECORDING:
            label, color = "Recording...", "error"
        elif vs == VoiceState.TRANSCRIBING:
            label, color = "Transcribing...", "warning"
        elif self._streaming:
            label, color = "Thinking...", "info"
        elif not self.voice.mic_available:
            label, color = "No mic detected", "text_dim"
        else:
            label, color = "Tap to Speak", "primary"

        btn_x = 68
        btn_w = self.r.width - btn_x - 12
        btn_h = BOTTOM_H - 16
        btn_y = by + 8
        self._mic_rect = self.r.draw_button(
            label, btn_x, btn_y, btn_w, btn_h, color)

    # ── interaction ──────────────────────────────────────────────────

    def handle_tap(self, x: int, y: int):
        if (self._mic_rect
                and self._mic_rect.collidepoint(x, y)
                and self.voice.state == VoiceState.IDLE
                and not self._streaming
                and self.voice.mic_available):
            asyncio.create_task(self._voice_flow())

    async def _voice_flow(self):
        text = await self.voice.record_and_transcribe(
            max_seconds=self.config.voice.max_record_seconds,
        )
        if not text:
            return

        self.messages.append(Message(role="user", text=text))

        self._streaming = True
        self._stream_buf = ""

        def on_delta(delta: str):
            self._stream_buf += delta

        try:
            result = await self.copilot.chat(text, on_delta=on_delta)
            answer = result.get("answer",
                                self._stream_buf or "Sorry, I couldn't process that.")
            self.messages.append(Message(role="assistant", text=answer))
            # flash happy expression briefly
            self._happy_until = time.time() + 1.5
        except Exception as e:
            log.error("Copilot error: %s", e)
            self.messages.append(Message(role="assistant", text=f"Error: {e}"))
        finally:
            self._streaming = False
            self._stream_buf = ""
