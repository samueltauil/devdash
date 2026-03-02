"""Mona — GitHub's octocat mascot as an animated DevDash avatar.

Drawn entirely with PyGame primitives so she scales to any size.
Reacts to voice states: idle (blinking), listening (wide eyes, glow),
thinking (wandering pupils, orbiting dots), speaking (animated mouth).
"""

from __future__ import annotations

import math
import time

import pygame

# ── Palette ──────────────────────────────────────────────────────────

BODY        = (52, 52, 72)
BODY_DARK   = (38, 38, 55)
BODY_LIGHT  = (68, 68, 90)
EAR_PINK    = (233, 69, 96)
EYE_WHITE   = (235, 235, 245)
PUPIL       = (25, 25, 40)
SHINE       = (200, 210, 230)
MOUTH_COLOR = (210, 75, 100)

GLOW_LISTEN = (41, 121, 255)
GLOW_THINK  = (255, 214, 0)
GLOW_SPEAK  = (0, 200, 83)
GLOW_HAPPY  = (233, 69, 96)

# ── States ───────────────────────────────────────────────────────────

IDLE      = "idle"
LISTENING = "listening"
THINKING  = "thinking"
SPEAKING  = "speaking"
HAPPY     = "happy"

# ── Helpers ──────────────────────────────────────────────────────────

def _i(val: float) -> int:
    return int(round(val))


# ── Avatar ───────────────────────────────────────────────────────────

class MonaAvatar:
    """Animated Mona octocat.  Call *draw()* every frame."""

    BLINK_EVERY = 3.6   # seconds between blinks
    BLINK_DUR   = 0.13  # how long a blink lasts

    def __init__(self):
        self.state: str = IDLE
        self._t   = 0.0          # global clock
        self._st  = 0.0          # time-in-current-state
        self._bt  = 0.0          # blink timer
        self._prev = time.monotonic()

    def set_state(self, state: str):
        if state != self.state:
            self.state = state
            self._st = 0.0

    # ── tick ─────────────────────────────────────────────────────────

    def _tick(self):
        now = time.monotonic()
        dt = now - self._prev
        self._prev = now
        self._t  += dt
        self._st += dt
        self._bt += dt

    # ── public draw entry points ─────────────────────────────────────

    def draw(self, surf: pygame.Surface, cx: int, cy: int, size: int = 72):
        """Full Mona at *(cx, cy)* with *size* ≈ head diameter."""
        self._tick()
        s = size / 72.0

        self._glow(surf, cx, cy, s)
        self._tentacles(surf, cx, cy + _i(32*s), s)
        self._body(surf, cx, cy + _i(24*s), s)
        self._head(surf, cx, cy, s)
        self._ears(surf, cx, cy, _i(22*s), s)
        self._eyes(surf, cx, cy, s)
        self._mouth(surf, cx, cy, s)
        self._effects(surf, cx, cy, s)

    def draw_mini(self, surf: pygame.Surface, cx: int, cy: int, size: int = 28):
        """Tiny Mona for the bottom bar — head + ears + eyes only."""
        self._tick()
        s = size / 72.0
        hr = _i(22 * s)

        pygame.draw.circle(surf, BODY, (cx, cy), hr)

        # mini ears
        for side in (-1, 1):
            bx = cx + side * _i(12*s)
            pts = [
                (bx, cy - hr + _i(4*s)),
                (bx + side * _i(6*s), cy - hr - _i(8*s)),
                (bx + side * _i(11*s), cy - hr + _i(4*s)),
            ]
            pygame.draw.polygon(surf, BODY, pts)
            inner = [
                (bx + side * _i(2*s), cy - hr + _i(4*s)),
                (bx + side * _i(6*s), cy - hr - _i(4*s)),
                (bx + side * _i(9*s), cy - hr + _i(4*s)),
            ]
            pygame.draw.polygon(surf, EAR_PINK, inner)

        # mini eyes
        er = max(2, _i(5*s))
        pr = max(1, _i(2.5*s))
        for side in (-1, 1):
            ex = cx + side * _i(8*s)
            ey = cy - _i(2*s)
            pygame.draw.circle(surf, EYE_WHITE, (ex, ey), er)
            pygame.draw.circle(surf, PUPIL, (ex, ey), pr)

        # mini mouth
        mr = max(1, _i(2*s))
        rect = pygame.Rect(cx - _i(5*s), cy + _i(4*s), _i(10*s), _i(5*s))
        pygame.draw.arc(surf, MOUTH_COLOR, rect,
                        math.pi + 0.6, 2*math.pi - 0.6, max(1, _i(1.2*s)))

    # ── body parts ───────────────────────────────────────────────────

    def _head(self, surf, cx, cy, s):
        pygame.draw.circle(surf, BODY, (cx, cy), _i(22*s))

    def _body(self, surf, cx, by, s):
        w, h = _i(42*s), _i(16*s)
        r = pygame.Rect(cx - w//2, by, w, h)
        pygame.draw.ellipse(surf, BODY, r)
        pygame.draw.ellipse(surf, BODY_LIGHT, r, max(1, _i(s)))

    def _ears(self, surf, cx, cy, hr, s):
        ear_h = _i(12*s)
        for side in (-1, 1):
            bx = cx + side * _i(14*s)
            by = cy - hr + _i(6*s)
            tx = cx + side * _i(18*s)
            ty = cy - hr - ear_h + _i(4*s)

            # wiggle when listening
            if self.state == LISTENING:
                ty += _i(math.sin(self._st * 8) * 2 * s * side)

            outer = [
                (bx - side * _i(6*s), by),
                (tx, ty),
                (bx + side * _i(6*s), by),
            ]
            pygame.draw.polygon(surf, BODY, outer)

            inner = [
                (bx - side * _i(3*s), by - _i(1*s)),
                (tx - side * _i(1*s), ty + _i(4*s)),
                (bx + side * _i(3*s), by - _i(1*s)),
            ]
            pygame.draw.polygon(surf, EAR_PINK, inner)

    # ── eyes ─────────────────────────────────────────────────────────

    def _eyes(self, surf, cx, cy, s):
        spacing = _i(10*s)
        ey = cy - _i(2*s)
        erx, ery = _i(8*s), _i(9*s)
        pr = _i(4.5*s)

        # state tweaks
        if self.state == LISTENING:
            erx, ery, pr = _i(9*s), _i(10*s), _i(5*s)

        # blink?
        blink = (self._bt % self.BLINK_EVERY) > (self.BLINK_EVERY - self.BLINK_DUR)
        blink = blink and self.state == IDLE

        # pupil offset
        px, py = 0, 0
        if self.state == THINKING:
            px = _i(3*s * math.sin(self._st * 1.5))
            py = _i(-2*s * math.cos(self._st * 1.5))
        elif self.state == SPEAKING:
            py = _i(1*s)

        for side in (-1, 1):
            ex = cx + side * spacing
            if blink:
                # closed-eye arc
                pygame.draw.line(surf, EYE_WHITE,
                    (ex - erx, ey), (ex + erx, ey), max(2, _i(2*s)))
            else:
                rect = pygame.Rect(ex - erx, ey - ery, erx*2, ery*2)
                pygame.draw.ellipse(surf, EYE_WHITE, rect)
                pygame.draw.circle(surf, PUPIL, (ex + px, ey + py), max(1, pr))
                # primary shine
                sr = max(1, _i(2*s))
                pygame.draw.circle(surf, SHINE,
                    (ex + px - _i(2*s), ey + py - _i(2*s)), sr)
                # secondary shine (smaller, lower-right)
                sr2 = max(1, _i(1*s))
                pygame.draw.circle(surf, (255, 255, 255),
                    (ex + px + _i(1*s), ey + py + _i(1*s)), sr2)

    # ── mouth ────────────────────────────────────────────────────────

    def _mouth(self, surf, cx, cy, s):
        my = cy + _i(10*s)

        if self.state == HAPPY:
            rect = pygame.Rect(cx - _i(8*s), my - _i(4*s), _i(16*s), _i(10*s))
            pygame.draw.arc(surf, MOUTH_COLOR, rect,
                            math.pi + 0.3, 2*math.pi - 0.3, max(2, _i(2*s)))
        elif self.state == SPEAKING:
            o = 0.3 + 0.7 * abs(math.sin(self._st * 5))
            h = max(2, _i(5*s*o))
            w = _i(5*s)
            pygame.draw.ellipse(surf, MOUTH_COLOR,
                pygame.Rect(cx - w, my, w*2, h))
        elif self.state == LISTENING:
            pygame.draw.circle(surf, MOUTH_COLOR, (cx, my + _i(2*s)),
                               max(2, _i(3*s)))
        else:
            rect = pygame.Rect(cx - _i(6*s), my - _i(2*s), _i(12*s), _i(6*s))
            pygame.draw.arc(surf, MOUTH_COLOR, rect,
                            math.pi + 0.5, 2*math.pi - 0.5, max(1, _i(1.5*s)))

    # ── tentacles ────────────────────────────────────────────────────

    def _tentacles(self, surf, cx, top_y, s):
        speed = 5.0 if self.state == SPEAKING else 2.5
        amp   = 4*s if self.state == SPEAKING else 2.5*s

        for i in range(5):
            tx = cx - _i(16*s) + i * _i(8*s)
            wave = math.sin(self._t * speed + i * 0.7) * amp

            prev = (tx, top_y)
            for j in range(1, 4):
                t = j / 3
                jx = _i(tx + wave * t * t)
                jy = _i(top_y + 12*s * t)
                w = max(1, _i((3.5 - j) * s))
                pygame.draw.line(surf, BODY_LIGHT, prev, (jx, jy), w)
                prev = (jx, jy)

    # ── glow / aura ──────────────────────────────────────────────────

    def _glow(self, surf, cx, cy, s):
        cmap = {
            LISTENING: GLOW_LISTEN, THINKING: GLOW_THINK,
            SPEAKING:  GLOW_SPEAK,  HAPPY:    GLOW_HAPPY,
        }
        color = cmap.get(self.state)
        if color is None:
            return

        pulse = 0.5 + 0.5 * math.sin(self._st * 3)
        r = _i((32 + 8 * pulse) * s)
        g = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        a = _i(22 + 22 * pulse)
        pygame.draw.circle(g, (*color, a), (r, r), r)
        surf.blit(g, (cx - r, cy - r))

    # ── state-specific fx ────────────────────────────────────────────

    def _effects(self, surf, cx, cy, s):
        if self.state == THINKING:
            # orbiting thought dots
            for i in range(3):
                delay = i * 0.35
                phase = (self._st - delay) % 1.4
                if phase < 0.9:
                    alpha = min(1.0, phase / 0.2) * max(0.0, 1 - (phase - 0.5) / 0.4)
                    r = max(1, _i(3*s*alpha))
                    dx = cx + _i(22*s) + i * _i(8*s)
                    dy = cy - _i(14*s)
                    pygame.draw.circle(surf, GLOW_THINK, (dx, dy), r)

        elif self.state == LISTENING:
            # sound-wave arcs radiating right
            for i in range(3):
                phase = (self._st * 2 + i * 0.5) % 1.8
                if phase < 1.2:
                    arc_r = _i((12 + 16*phase) * s)
                    a = _i(160 * (1 - phase / 1.2))
                    gs = pygame.Surface((arc_r*2, arc_r*2), pygame.SRCALPHA)
                    pygame.draw.arc(gs, (*GLOW_LISTEN, a),
                        (0, 0, arc_r*2, arc_r*2),
                        -0.6, 0.6, max(2, _i(2*s)))
                    surf.blit(gs, (cx + _i(22*s) - arc_r, cy - arc_r))

        elif self.state == HAPPY:
            # sparkle stars
            for i in range(5):
                angle = self._st * 1.8 + i * (2*math.pi / 5)
                dist = _i(30*s)
                sx = cx + _i(dist * math.cos(angle))
                sy = cy + _i(dist * math.sin(angle))
                sz = max(1, _i(2.5*s * abs(math.sin(self._st * 4 + i))))
                pygame.draw.line(surf, GLOW_HAPPY, (sx-sz, sy), (sx+sz, sy), 1)
                pygame.draw.line(surf, GLOW_HAPPY, (sx, sy-sz), (sx, sy+sz), 1)
