"""Mona — Official GitHub Octocat SVG rendered and animated.

Renders the real Octocat SVG via cairosvg at multiple sizes, then
overlays animated eyes, mouth, and state effects using PyGame.
"""

from __future__ import annotations

import io
import math
import os
import time
from pathlib import Path

import pygame

try:
    import cairosvg
    _HAS_CAIRO = True
except ImportError:
    _HAS_CAIRO = False

# ── States ───────────────────────────────────────────────────────────

IDLE      = "idle"
LISTENING = "listening"
THINKING  = "thinking"
SPEAKING  = "speaking"
HAPPY     = "happy"

# ── SVG element colors (from the official SVG) ───────────────────────

PUPIL_CLR = (173, 92, 81)     # #AD5C51
MOUTH_CLR = (173, 92, 81)
GLOW_MAP  = {
    LISTENING: (41, 121, 255),
    THINKING:  (255, 214, 0),
    SPEAKING:  (0, 200, 83),
    HAPPY:     (233, 69, 96),
}

# ── SVG source path ──────────────────────────────────────────────────

_SVG_PATH = Path(__file__).resolve().parent.parent / "assets" / "octocat.svg"

# The SVG viewBox is "−0.2 −1 379 334"  →  width≈379, height≈334
_SVG_W = 379.0
_SVG_H = 280.0  # cropped: body only, no puddle/shadow

# Key coordinates in SVG space (extracted from paths)
_LEFT_EYE_CX,  _LEFT_EYE_CY  = 142.5, 126.06
_RIGHT_EYE_CX, _RIGHT_EYE_CY = 236.93, 126.06
_EYE_RX, _EYE_RY             = 17.6, 25.336
_PUPIL_RX, _PUPIL_RY         = 11.734, 16.887
_NOSE_CX, _NOSE_CY, _NOSE_R  = 188.5, 148.56, 4.401
_MOUTH_CX, _MOUTH_CY         = 188.45, 162.0
_SVG_CX                       = 189.0

# ── Helpers ──────────────────────────────────────────────────────────

def _i(v):
    return int(round(v))


class MonaAvatar:
    """Animated Mona: real Octocat SVG + dynamic overlays."""

    BLINK_EVERY = 3.6
    BLINK_DUR   = 0.13

    def __init__(self):
        self.state: str = IDLE
        self._t   = 0.0
        self._st  = 0.0
        self._bt  = 0.0
        self._prev = time.monotonic()
        self._cache: dict = {}
        self._svg_data: bytes | None = None
        self._load_svg()

    def _load_svg(self):
        """Read SVG file once."""
        try:
            self._svg_data = _SVG_PATH.read_bytes()
        except FileNotFoundError:
            self._svg_data = None

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

    # ── SVG rendering & caching ──────────────────────────────────────

    def _get(self, height: int) -> dict:
        """Get cached rendered SVG surface + metrics for a target height."""
        if height not in self._cache:
            self._cache[height] = self._render_svg(height)
        return self._cache[height]

    def _get_flipped(self, height: int) -> pygame.Surface:
        """Get horizontally flipped SVG surface (cached)."""
        key = f"flip_{height}"
        if key not in self._cache:
            c = self._get(height)
            self._cache[key] = pygame.transform.flip(c["surf"], True, False)
        return self._cache[key]

    def _render_svg(self, target_h: int) -> dict:
        """Render the SVG to a pygame Surface at the given height."""
        scale = target_h / _SVG_H
        target_w = _i(_SVG_W * scale)

        surf = None
        if _HAS_CAIRO and self._svg_data:
            try:
                png_data = cairosvg.svg2png(
                    bytestring=self._svg_data,
                    output_width=target_w,
                    output_height=target_h,
                )
                surf = pygame.image.load(io.BytesIO(png_data)).convert_alpha()
            except Exception:
                surf = None

        if surf is None:
            # Fallback: plain circle placeholder
            surf = pygame.Surface((target_w, target_h), pygame.SRCALPHA)
            pygame.draw.circle(surf, (52, 52, 72),
                               (target_w // 2, target_h // 2),
                               min(target_w, target_h) // 3)

        return {
            "surf": surf,
            "w": target_w,
            "h": target_h,
            "scale": scale,
        }

    # ── SVG-to-screen coordinate mapping ─────────────────────────────

    @staticmethod
    def _map(svg_x, svg_y, cx, cy, c):
        """Map SVG coordinates to screen coords given blit center."""
        s = c["scale"]
        # SVG origin is at viewBox corner; center offset
        sx = (svg_x - _SVG_CX) * s + cx
        sy = (svg_y + 1) * s + (cy - c["h"] // 2)  # +1 for viewBox y=-1
        return _i(sx), _i(sy)

    # ── Draw full ────────────────────────────────────────────────────

    def draw(self, surf: pygame.Surface, cx: int, cy: int, size: int = 72,
             facing: int = 0):
        """Draw Mona centered at (cx, cy). *size* = desired height in px.

        *facing*: 0 = forward, 1 = facing right, -1 = facing left.
        """
        self._tick()
        c = self._get(size)
        s = c["scale"]

        # Glow aura behind SVG
        self._glow(surf, cx, cy, size, s)

        # Blit the full SVG (or flipped version for sideways facing)
        bx = cx - c["w"] // 2
        by = cy - c["h"] // 2
        if facing == -1:
            surf.blit(self._get_flipped(size), (bx, by))
        else:
            surf.blit(c["surf"], (bx, by))

        # Overlay animated eyes only when facing forward
        if facing == 0:
            self._animated_eyes(surf, cx, cy, c)

            # Overlay animated mouth when speaking
            if self.state in (SPEAKING, HAPPY):
                self._animated_mouth(surf, cx, cy, c)

        # State effects
        self._effects(surf, cx, cy, s)

    # ── Draw mini ────────────────────────────────────────────────────

    def draw_mini(self, surf: pygame.Surface, cx: int, cy: int, size: int = 28):
        """Tiny Mona for the bottom bar — just the SVG scaled down."""
        self._tick()
        # For mini, crop to roughly the head area (upper 55% of SVG)
        head_h = _i(size * 0.55)
        c = self._get(size)
        s = c["scale"]

        # Mini glow
        gc = GLOW_MAP.get(self.state)
        if gc:
            pulse = 0.5 + 0.5 * math.sin(self._st * 3)
            gr = _i(size * 0.6)
            gs = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*gc, _i(22 * pulse)), (gr, gr), gr)
            surf.blit(gs, (cx - gr, cy - gr))

        # Blit SVG (offset up to show head centered)
        bx = cx - c["w"] // 2
        by = cy - _i(c["h"] * 0.35)
        surf.blit(c["surf"], (bx, by))

    # ── Animated eyes ────────────────────────────────────────────────

    def _animated_eyes(self, surf, cx, cy, c):
        """Overlay animated pupils on the SVG eyes."""
        s = c["scale"]

        # Blink check
        blink = ((self._bt % self.BLINK_EVERY)
                 > (self.BLINK_EVERY - self.BLINK_DUR)
                 and self.state == IDLE)

        # Pupil offset for gaze
        px, py = 0.0, 0.0
        if self.state == THINKING:
            px = 4.0 * math.sin(self._st * 1.5)
            py = -3.0 * math.cos(self._st * 1.5)
        elif self.state == SPEAKING:
            py = 1.5
        elif self.state == LISTENING:
            # Look slightly toward the user
            px = -1.0
            py = 1.0

        for eye_cx, eye_cy in [(_LEFT_EYE_CX, _LEFT_EYE_CY),
                                (_RIGHT_EYE_CX, _RIGHT_EYE_CY)]:
            # Screen position of eye center
            ex, ey = self._map(eye_cx, eye_cy, cx, cy, c)
            erx = _i(_EYE_RX * s)
            ery = _i(_EYE_RY * s)
            prx = _i(_PUPIL_RX * s)
            pry = _i(_PUPIL_RY * s)
            ppx = _i(px * s)
            ppy = _i(py * s)

            if blink:
                # Cover eye white with face color, draw closed line
                pygame.draw.ellipse(surf, (244, 203, 178),
                                    (ex - erx, ey - ery, erx * 2, ery * 2))
                pygame.draw.line(surf, PUPIL_CLR,
                                 (ex - erx + 2, ey), (ex + erx - 2, ey),
                                 max(2, _i(2 * s)))
            else:
                # Redraw eye white (covers original static pupils)
                pygame.draw.ellipse(surf, (255, 255, 255),
                                    (ex - erx, ey - ery, erx * 2, ery * 2))

                # Pupil at offset position
                pygame.draw.ellipse(surf, PUPIL_CLR,
                                    (ex + ppx - prx, ey + ppy - pry,
                                     prx * 2, pry * 2))

                # Highlight
                sh = max(1, _i(3.5 * s))
                pygame.draw.circle(surf, (255, 255, 255),
                                   (ex + ppx - _i(4 * s),
                                    ey + ppy - _i(5 * s)), sh)
                sh2 = max(1, _i(1.5 * s))
                pygame.draw.circle(surf, (255, 255, 255),
                                   (ex + ppx + _i(2 * s),
                                    ey + ppy + _i(3 * s)), sh2)

    # ── Animated mouth ───────────────────────────────────────────────

    def _animated_mouth(self, surf, cx, cy, c):
        s = c["scale"]
        mx, my = self._map(_MOUTH_CX, _MOUTH_CY, cx, cy, c)

        if self.state == SPEAKING:
            o = 0.3 + 0.7 * abs(math.sin(self._st * 5))
            h = max(2, _i(6 * s * o))
            w = _i(5 * s)
            # Cover original mouth
            pygame.draw.ellipse(surf, (244, 203, 178),
                                (mx - _i(12 * s), my - _i(4 * s),
                                 _i(24 * s), _i(8 * s)))
            # Open mouth
            pygame.draw.ellipse(surf, MOUTH_CLR,
                                (mx - w, my - h // 2, w * 2, h))
        elif self.state == HAPPY:
            w = _i(10 * s)
            rect = pygame.Rect(mx - w, my - _i(4 * s), w * 2, _i(10 * s))
            # Cover original
            pygame.draw.ellipse(surf, (244, 203, 178),
                                (mx - _i(12 * s), my - _i(4 * s),
                                 _i(24 * s), _i(10 * s)))
            # Big smile
            pygame.draw.arc(surf, MOUTH_CLR, rect,
                            math.pi + 0.3, 2 * math.pi - 0.3,
                            max(2, _i(2.5 * s)))

    # ── Glow aura ────────────────────────────────────────────────────

    def _glow(self, surf, cx, cy, size, s):
        gc = GLOW_MAP.get(self.state)
        if gc is None:
            return
        pulse = 0.5 + 0.5 * math.sin(self._st * 3)
        r = _i(size * 0.45 + 10 * pulse * s)
        gs = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        a = _i(25 + 25 * pulse)
        pygame.draw.circle(gs, (*gc, a), (r, r), r)
        surf.blit(gs, (cx - r, cy - r))

    # ── State effects ────────────────────────────────────────────────

    def _effects(self, surf, cx, cy, s):
        if self.state == THINKING:
            for i in range(3):
                phase = (self._st - i * 0.4) % 1.6
                if phase < 1.0:
                    frac = (min(1.0, phase / 0.2)
                            * max(0.0, 1 - (phase - 0.4) / 0.6))
                    r = max(1, _i((4 + i * 2) * s * frac))
                    dx = cx + _i(55 * s) + i * _i(12 * s)
                    dy = cy - _i(40 * s) - i * _i(8 * s)
                    a = _i(200 * frac)
                    ds = pygame.Surface((r * 2 + 2, r * 2 + 2),
                                        pygame.SRCALPHA)
                    pygame.draw.circle(ds, (*GLOW_MAP[THINKING], a),
                                       (r + 1, r + 1), r)
                    surf.blit(ds, (dx - r - 1, dy - r - 1))

        elif self.state == LISTENING:
            for i in range(3):
                phase = (self._st * 2 + i * 0.5) % 2.0
                if phase < 1.4:
                    arc_r = _i((20 + 22 * phase) * s)
                    a = _i(140 * (1 - phase / 1.4))
                    arc_s = pygame.Surface((arc_r * 2, arc_r * 2),
                                           pygame.SRCALPHA)
                    pygame.draw.arc(arc_s, (*GLOW_MAP[LISTENING], a),
                                    (0, 0, arc_r * 2, arc_r * 2),
                                    -0.5, 0.5, max(2, _i(2.5 * s)))
                    surf.blit(arc_s,
                              (cx + _i(50 * s) - arc_r, cy - _i(20 * s) - arc_r))

        elif self.state == HAPPY:
            for i in range(6):
                angle = self._st * 1.5 + i * (2 * math.pi / 6)
                dist = _i(60 * s)
                sx = cx + _i(dist * math.cos(angle))
                sy = cy + _i(dist * math.sin(angle))
                sz = max(1, _i(4 * s
                               * abs(math.sin(self._st * 3.5 + i * 1.2))))
                c = GLOW_MAP[HAPPY]
                w = max(1, _i(s))
                pygame.draw.line(surf, c, (sx - sz, sy), (sx + sz, sy), w)
                pygame.draw.line(surf, c, (sx, sy - sz), (sx, sy + sz), w)
                dsz = _i(sz * 0.6)
                pygame.draw.line(surf, c,
                                 (sx - dsz, sy - dsz), (sx + dsz, sy + dsz), 1)
                pygame.draw.line(surf, c,
                                 (sx - dsz, sy + dsz), (sx + dsz, sy - dsz), 1)
