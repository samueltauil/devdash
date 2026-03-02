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

BODY        = (55, 55, 75)
BODY_DARK   = (40, 40, 58)
BODY_LIGHT  = (72, 72, 95)
EAR_INNER   = (80, 65, 85)
EYE_WHITE   = (240, 240, 248)
PUPIL       = (22, 22, 36)
SHINE       = (255, 255, 255)
MOUTH_COLOR = (180, 80, 105)

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

def _i(v: float) -> int:
    return int(round(v))


# ── Avatar ───────────────────────────────────────────────────────────

class MonaAvatar:
    """Animated Mona octocat.  Call *draw()* every frame."""

    BLINK_EVERY = 3.6
    BLINK_DUR   = 0.13

    def __init__(self):
        self.state: str = IDLE
        self._t   = 0.0
        self._st  = 0.0
        self._bt  = 0.0
        self._prev = time.monotonic()

    def set_state(self, state: str):
        if state != self.state:
            self.state = state
            self._st = 0.0

    def _tick(self):
        now = time.monotonic()
        dt = now - self._prev
        self._prev = now
        self._t  += dt
        self._st += dt
        self._bt += dt

    # ── public entry points ──────────────────────────────────────────

    def draw(self, surf: pygame.Surface, cx: int, cy: int, size: int = 72):
        """Full Mona centered at (cx, cy). *size* ≈ head diameter."""
        self._tick()
        s = size / 72.0
        hr = _i(24 * s)          # head radius

        self._glow(surf, cx, cy, s)
        self._tentacles(surf, cx, cy + _i(30 * s), s)
        self._body(surf, cx, cy + _i(24 * s), s)
        self._head(surf, cx, cy, hr)
        self._ears(surf, cx, cy, hr, s)
        self._eyes(surf, cx, cy, s)
        self._mouth(surf, cx, cy, s)
        self._effects(surf, cx, cy, s)

    def draw_mini(self, surf: pygame.Surface, cx: int, cy: int, size: int = 28):
        """Tiny Mona for the bottom bar."""
        self._tick()
        s = size / 72.0
        hr = _i(22 * s)

        # head
        pygame.draw.circle(surf, BODY, (cx, cy), hr)

        # ears — small rounded bumps
        for side in (-1, 1):
            tip_x = cx + side * _i(16 * s)
            tip_y = cy - hr - _i(4 * s)
            base_l = cx + side * _i(8 * s)
            base_r = cx + side * _i(20 * s)
            pygame.draw.polygon(surf, BODY, [
                (base_l, cy - hr + _i(3 * s)),
                (tip_x, tip_y),
                (base_r, cy - hr + _i(3 * s)),
            ])

        # eyes
        er = max(2, _i(6 * s))
        pr = max(1, _i(3 * s))
        for side in (-1, 1):
            ex = cx + side * _i(8 * s)
            ey = cy - _i(1 * s)
            pygame.draw.circle(surf, EYE_WHITE, (ex, ey), er)
            pygame.draw.circle(surf, PUPIL, (ex, ey), pr)

    # ── body parts ───────────────────────────────────────────────────

    def _head(self, surf, cx, cy, hr):
        pygame.draw.circle(surf, BODY, (cx, cy), hr)

    def _body(self, surf, cx, by, s):
        w, h = _i(44 * s), _i(14 * s)
        rect = pygame.Rect(cx - w // 2, by, w, h)
        pygame.draw.ellipse(surf, BODY, rect)

    def _ears(self, surf, cx, cy, hr, s):
        """Soft, rounded cat ears — wider than tall."""
        ear_h = _i(10 * s)      # how far ears poke above head
        ear_w = _i(14 * s)      # half-width of each ear

        for side in (-1, 1):
            # ear tip sits above and outward from head
            tip_x = cx + side * _i(17 * s)
            tip_y = cy - hr - ear_h + _i(2 * s)

            if self.state == LISTENING:
                tip_y -= _i(2 * s * abs(math.sin(self._st * 6)))

            # base points merge smoothly into the head circle
            base_inner = cx + side * _i(6 * s)
            base_outer = cx + side * _i(22 * s)
            base_y = cy - hr + _i(6 * s)

            # outer ear
            pts = [(base_inner, base_y), (tip_x, tip_y), (base_outer, base_y)]
            pygame.draw.polygon(surf, BODY, pts)
            # smooth the base into head with a small circle
            pygame.draw.circle(surf, BODY,
                (cx + side * _i(14 * s), cy - hr + _i(3 * s)), _i(6 * s))

            # inner ear (subtle, darker shade — not bright pink)
            inner_pts = [
                (base_inner + side * _i(3 * s), base_y - _i(1 * s)),
                (tip_x, tip_y + _i(4 * s)),
                (base_outer - side * _i(3 * s), base_y - _i(1 * s)),
            ]
            pygame.draw.polygon(surf, EAR_INNER, inner_pts)

    # ── eyes ─────────────────────────────────────────────────────────

    def _eyes(self, surf, cx, cy, s):
        spacing = _i(11 * s)
        ey = cy - _i(2 * s)
        er = _i(10 * s)          # eye radius — BIG
        pr = _i(5 * s)           # pupil radius

        if self.state == LISTENING:
            er = _i(11 * s)
            pr = _i(5.5 * s)

        # blink?
        blink = (self._bt % self.BLINK_EVERY) > (self.BLINK_EVERY - self.BLINK_DUR)
        blink = blink and self.state == IDLE

        # pupil offset
        px, py = 0, 0
        if self.state == THINKING:
            px = _i(3 * s * math.sin(self._st * 1.5))
            py = _i(-2 * s * math.cos(self._st * 1.5))
        elif self.state == SPEAKING:
            py = _i(1 * s)

        for side in (-1, 1):
            ex = cx + side * spacing
            if blink:
                pygame.draw.line(surf, EYE_WHITE,
                    (ex - _i(7*s), ey), (ex + _i(7*s), ey),
                    max(2, _i(2 * s)))
            else:
                # white of eye
                pygame.draw.circle(surf, EYE_WHITE, (ex, ey), max(2, er))
                # pupil
                pygame.draw.circle(surf, PUPIL,
                    (ex + px, ey + py), max(1, pr))
                # primary highlight (top-left)
                sh = max(1, _i(2.5 * s))
                pygame.draw.circle(surf, SHINE,
                    (ex + px - _i(3 * s), ey + py - _i(3 * s)), sh)
                # secondary highlight (bottom-right, smaller)
                sh2 = max(1, _i(1.2 * s))
                pygame.draw.circle(surf, SHINE,
                    (ex + px + _i(1.5 * s), ey + py + _i(1.5 * s)), sh2)

    # ── mouth ────────────────────────────────────────────────────────

    def _mouth(self, surf, cx, cy, s):
        my = cy + _i(11 * s)

        if self.state == HAPPY:
            rect = pygame.Rect(cx - _i(7*s), my - _i(3*s), _i(14*s), _i(8*s))
            pygame.draw.arc(surf, MOUTH_COLOR, rect,
                            math.pi + 0.4, 2*math.pi - 0.4, max(2, _i(2*s)))
        elif self.state == SPEAKING:
            o = 0.3 + 0.7 * abs(math.sin(self._st * 5))
            h = max(2, _i(4 * s * o))
            w = _i(4 * s)
            pygame.draw.ellipse(surf, MOUTH_COLOR,
                pygame.Rect(cx - w, my, w * 2, h))
        elif self.state == LISTENING:
            pygame.draw.circle(surf, MOUTH_COLOR,
                (cx, my + _i(1*s)), max(2, _i(2.5*s)))
        else:
            # gentle smile
            rect = pygame.Rect(cx - _i(5*s), my - _i(1*s), _i(10*s), _i(5*s))
            pygame.draw.arc(surf, MOUTH_COLOR, rect,
                            math.pi + 0.5, 2*math.pi - 0.5, max(1, _i(1.5*s)))

    # ── tentacles ────────────────────────────────────────────────────

    def _tentacles(self, surf, cx, top_y, s):
        speed = 4.5 if self.state == SPEAKING else 2.0
        amp   = 3.5*s if self.state == SPEAKING else 2.0*s

        for i in range(5):
            tx = cx - _i(16*s) + i * _i(8*s)
            wave = math.sin(self._t * speed + i * 0.8) * amp

            prev = (tx, top_y)
            for j in range(1, 4):
                t = j / 3
                jx = _i(tx + wave * t * t)
                jy = _i(top_y + 10 * s * t)
                w = max(1, _i((3 - j * 0.7) * s))
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
        r = _i((34 + 8 * pulse) * s)
        g = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        a = _i(20 + 20 * pulse)
        pygame.draw.circle(g, (*color, a), (r, r), r)
        surf.blit(g, (cx - r, cy - r))

    # ── state-specific fx ────────────────────────────────────────────

    def _effects(self, surf, cx, cy, s):
        if self.state == THINKING:
            for i in range(3):
                delay = i * 0.35
                phase = (self._st - delay) % 1.4
                if phase < 0.9:
                    frac = min(1.0, phase/0.2) * max(0.0, 1-(phase-0.5)/0.4)
                    r = max(1, _i(3 * s * frac))
                    dx = cx + _i(26*s) + i * _i(8*s)
                    dy = cy - _i(16*s)
                    pygame.draw.circle(surf, GLOW_THINK, (dx, dy), r)

        elif self.state == LISTENING:
            for i in range(3):
                phase = (self._st * 2 + i * 0.5) % 1.8
                if phase < 1.2:
                    arc_r = _i((14 + 16*phase) * s)
                    a = _i(140 * (1 - phase / 1.2))
                    gs = pygame.Surface((arc_r*2, arc_r*2), pygame.SRCALPHA)
                    pygame.draw.arc(gs, (*GLOW_LISTEN, a),
                        (0, 0, arc_r*2, arc_r*2),
                        -0.5, 0.5, max(2, _i(2*s)))
                    surf.blit(gs, (cx + _i(24*s) - arc_r, cy - arc_r))

        elif self.state == HAPPY:
            for i in range(5):
                angle = self._st * 1.8 + i * (2*math.pi / 5)
                dist = _i(32*s)
                sx = cx + _i(dist * math.cos(angle))
                sy = cy + _i(dist * math.sin(angle))
                sz = max(1, _i(2.5*s * abs(math.sin(self._st*4 + i))))
                pygame.draw.line(surf, GLOW_HAPPY, (sx-sz, sy), (sx+sz, sy), 1)
                pygame.draw.line(surf, GLOW_HAPPY, (sx, sy-sz), (sx, sy+sz), 1)
