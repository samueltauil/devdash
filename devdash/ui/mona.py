"""Mona — GitHub's octocat mascot with 3D-shaded rendering.

Proportions derived from the official Octocat SVG.
Signature vertical-oval eyes (height ≈ 1.5× width).
Rendered with numpy sphere shading, anti-aliased edges,
specular highlights, and ambient occlusion.
"""

from __future__ import annotations

import math
import time

import pygame
import pygame.gfxdraw

try:
    import numpy as np
    _NP = True
except ImportError:
    _NP = False

# ── Palette ──────────────────────────────────────────────────────────

BODY     = (62, 58, 82)
BODY_HI  = (90, 84, 110)
BODY_LO  = (35, 33, 48)
EAR_IN   = (82, 65, 90)
FACE_CLR = (78, 72, 98)
EYE_W    = (245, 245, 252)
PUPIL_C  = (90, 50, 60)
NOSE_CLR = (155, 82, 92)
MOUTH_C  = (150, 72, 90)

GLOW_MAP = {
    "listening": (41, 121, 255),
    "thinking":  (255, 214, 0),
    "speaking":  (0, 200, 83),
    "happy":     (233, 69, 96),
}

# ── States ───────────────────────────────────────────────────────────

IDLE      = "idle"
LISTENING = "listening"
THINKING  = "thinking"
SPEAKING  = "speaking"
HAPPY     = "happy"

# ── Helpers ──────────────────────────────────────────────────────────

def _i(v):
    return int(round(v))

def _lerp(a, b, t):
    return a + (b - a) * t


# ── Avatar ───────────────────────────────────────────────────────────

class MonaAvatar:
    """Animated Mona octocat with 3D rendering.  Call *draw()* every frame."""

    BLINK_EVERY = 3.6
    BLINK_DUR   = 0.13

    def __init__(self):
        self.state: str = IDLE
        self._t   = 0.0
        self._st  = 0.0
        self._bt  = 0.0
        self._prev = time.monotonic()
        self._cache: dict = {}

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

    # ── Pre-rendering (numpy-accelerated 3D shading) ─────────────────

    @staticmethod
    def _sphere(radius, color, light=(-0.35, -0.5, 0.75),
                amb=0.32, spc=0.45, shin=40):
        """Render a 3D-lit sphere to a surface."""
        pad = 2
        sz = (radius + pad) * 2
        surf = pygame.Surface((sz, sz), pygame.SRCALPHA)
        if not _NP or radius < 3:
            pygame.draw.circle(surf, color, (sz // 2, sz // 2), radius)
            return surf
        cx = cy = sz // 2
        lx, ly, lz = light
        lm = math.sqrt(lx * lx + ly * ly + lz * lz)
        lx, ly, lz = lx / lm, ly / lm, lz / lm
        xg, yg = np.mgrid[0:sz, 0:sz]
        dx = (xg - cx).astype(np.float32) / radius
        dy = (yg - cy).astype(np.float32) / radius
        d2 = dx * dx + dy * dy
        mask = d2 < 1.0
        dz = np.zeros_like(d2)
        dz[mask] = np.sqrt(1.0 - d2[mask])
        # Diffuse
        diff = np.clip(dx * lx + dy * ly + dz * lz, 0, 1)
        # Blinn-Phong specular
        hx, hy, hz = lx, ly, lz + 1.0
        hm = math.sqrt(hx * hx + hy * hy + hz * hz)
        hx, hy, hz = hx / hm, hy / hm, hz / hm
        spec = np.clip(dx * hx + dy * hy + dz * hz, 0, 1) ** shin
        inten = amb + (1 - amb) * diff
        r = np.clip(color[0] * inten + 255 * spc * spec, 0, 255)
        g = np.clip(color[1] * inten + 255 * spc * spec, 0, 255)
        b = np.clip(color[2] * inten + 255 * spc * spec, 0, 255)
        # Anti-aliased edge
        edge = np.clip((1.0 - np.sqrt(d2)) * radius, 0, 1.5) / 1.5
        alpha = np.where(mask, (edge * 255).astype(np.uint8), 0)
        px = pygame.surfarray.pixels3d(surf)
        pa = pygame.surfarray.pixels_alpha(surf)
        px[:, :, 0] = np.where(mask, r.astype(np.uint8), 0)
        px[:, :, 1] = np.where(mask, g.astype(np.uint8), 0)
        px[:, :, 2] = np.where(mask, b.astype(np.uint8), 0)
        pa[:, :] = alpha
        del px, pa
        return surf

    @staticmethod
    def _ellipsoid(hw, hh, color, light=(-0.25, -0.4, 0.85),
                   amb=0.30, spc=0.25):
        """Render a 3D-lit ellipsoid."""
        pad = 2
        w = (hw + pad) * 2
        h = (hh + pad) * 2
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        if not _NP or hw < 3:
            pygame.draw.ellipse(surf, color, (pad, pad, hw * 2, hh * 2))
            return surf
        cx, cy = w // 2, h // 2
        lx, ly, lz = light
        lm = math.sqrt(lx * lx + ly * ly + lz * lz)
        lx, ly, lz = lx / lm, ly / lm, lz / lm
        xg, yg = np.mgrid[0:w, 0:h]
        dx = (xg - cx).astype(np.float32) / hw
        dy = (yg - cy).astype(np.float32) / hh
        d2 = dx * dx + dy * dy
        mask = d2 < 1.0
        dz = np.zeros_like(d2)
        dz[mask] = np.sqrt(1.0 - d2[mask])
        diff = np.clip(dx * lx + dy * ly + dz * lz, 0, 1)
        inten = amb + (1 - amb) * diff
        r = np.clip(color[0] * inten, 0, 255)
        g = np.clip(color[1] * inten, 0, 255)
        b = np.clip(color[2] * inten, 0, 255)
        edge = np.clip((1.0 - np.sqrt(d2)) * min(hw, hh), 0, 1.5) / 1.5
        alpha = np.where(mask, (edge * 255).astype(np.uint8), 0)
        px = pygame.surfarray.pixels3d(surf)
        pa = pygame.surfarray.pixels_alpha(surf)
        px[:, :, 0] = np.where(mask, r.astype(np.uint8), 0)
        px[:, :, 1] = np.where(mask, g.astype(np.uint8), 0)
        px[:, :, 2] = np.where(mask, b.astype(np.uint8), 0)
        pa[:, :] = alpha
        del px, pa
        return surf

    @staticmethod
    def _soft_shadow(hw, hh, max_a=35):
        """Gaussian-ish drop shadow."""
        pad = 6
        w = (hw + pad) * 2
        h = (hh + pad) * 2
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        if _NP:
            cx, cy = w // 2, h // 2
            xg, yg = np.mgrid[0:w, 0:h]
            d2 = ((xg - cx).astype(np.float32) / hw) ** 2 \
               + ((yg - cy).astype(np.float32) / hh) ** 2
            a = np.clip((1.0 - d2) ** 2 * max_a, 0, max_a).astype(np.uint8)
            pa = pygame.surfarray.pixels_alpha(surf)
            pa[:, :] = a
            del pa
        else:
            for i in range(max(hw, hh), 0, -2):
                t = 1 - i / max(hw, hh)
                pygame.draw.ellipse(surf, (0, 0, 0, int(max_a * t * t)),
                    (w // 2 - hw, h // 2 - hh, hw * 2, hh * 2))
        return surf

    @staticmethod
    def _glow_surf(radius, color, max_a=50):
        """Radial glow surface."""
        sz = radius * 2
        surf = pygame.Surface((sz, sz), pygame.SRCALPHA)
        if _NP:
            cx = radius
            xg, yg = np.mgrid[0:sz, 0:sz]
            d2 = ((xg - cx) ** 2 + (yg - cx) ** 2).astype(np.float32) \
               / (radius * radius)
            mask = d2 < 1.0
            a = np.clip((1.0 - d2) ** 1.5 * max_a, 0, max_a).astype(np.uint8)
            px = pygame.surfarray.pixels3d(surf)
            pa = pygame.surfarray.pixels_alpha(surf)
            px[:, :, 0] = color[0]
            px[:, :, 1] = color[1]
            px[:, :, 2] = color[2]
            pa[:, :] = np.where(mask, a, 0)
            del px, pa
        else:
            for r in range(radius, 0, -2):
                t = r / radius
                pygame.draw.circle(surf, (*color, int(max_a * (1 - t) ** 1.5)),
                                   (radius, radius), r)
        return surf

    # ── Cache ────────────────────────────────────────────────────────

    def _get(self, size):
        if size not in self._cache:
            self._build(size)
        return self._cache[size]

    def _build(self, size):
        s = size / 72.0
        c = {"s": s}
        hr = max(3, _i(28 * s))
        c["head"] = self._sphere(hr, BODY)
        c["hr"] = hr
        bw, bh = max(3, _i(24 * s)), max(3, _i(9 * s))
        c["body"] = self._ellipsoid(bw, bh, BODY)
        c["bw"], c["bh"] = bw, bh
        c["shadow"] = self._soft_shadow(_i(26 * s), _i(7 * s))
        c["sw"], c["sh"] = _i(26 * s), _i(7 * s)
        for state, col in GLOW_MAP.items():
            gr = _i(40 * s)
            c[f"g_{state}"] = self._glow_surf(gr, col)
            c[f"gr_{state}"] = gr
        self._cache[size] = c

    # ── Draw full ────────────────────────────────────────────────────

    def draw(self, surf: pygame.Surface, cx: int, cy: int, size: int = 72):
        """Full 3D Mona centered at (cx, cy). *size* ≈ head diameter."""
        self._tick()
        c = self._get(size)
        s = c["s"]
        hr = c["hr"]

        # 1 — Drop shadow
        sw, sh = c["sw"], c["sh"]
        surf.blit(c["shadow"], (cx - sw - 6, cy + _i(36 * s) - sh - 6))

        # 2 — State glow
        gk = f"g_{self.state}"
        if gk in c:
            pulse = 0.6 + 0.4 * math.sin(self._st * 3)
            gr = c[f"gr_{self.state}"]
            g = c[gk].copy()
            g.set_alpha(_i(255 * pulse))
            surf.blit(g, (cx - gr, cy - gr))

        # 3 — Tentacles
        self._tentacles(surf, cx, cy + _i(30 * s), s)

        # 4 — Body
        bw, bh = c["bw"], c["bh"]
        surf.blit(c["body"], (cx - bw - 2, cy + _i(22 * s) - bh - 2))

        # 5 — Head-body ambient occlusion
        ao_w = _i(20 * s)
        if ao_w > 1:
            ao = pygame.Surface((ao_w * 2, _i(6 * s) * 2), pygame.SRCALPHA)
            pygame.draw.ellipse(ao, (0, 0, 0, 18), ao.get_rect())
            surf.blit(ao, (cx - ao_w, cy + _i(18 * s) - _i(6 * s)))

        # 6 — Head sphere
        surf.blit(c["head"], (cx - hr - 2, cy - hr - 2))

        # 7 — Ears
        self._ears(surf, cx, cy, hr, s)

        # 8 — Face region (subtle lighter area)
        fw, fh = _i(18 * s), _i(14 * s)
        if fw > 2:
            fs = pygame.Surface((fw * 2, fh * 2), pygame.SRCALPHA)
            pygame.draw.ellipse(fs, (*FACE_CLR, 22), fs.get_rect())
            surf.blit(fs, (cx - fw, cy - _i(2 * s) - fh))

        # 9 — Eyes  (vertical ovals — Octocat signature!)
        self._eyes(surf, cx, cy, s)

        # 10 — Nose
        self._nose(surf, cx, cy, s)

        # 11 — Mouth
        self._mouth(surf, cx, cy, s)

        # 12 — Rim highlight
        rs = pygame.Surface((hr * 2 + 4, hr * 2 + 4), pygame.SRCALPHA)
        try:
            pygame.draw.arc(rs, (255, 255, 255, 35),
                            (2, 2, hr * 2, hr * 2),
                            0.6, 2.0, max(1, _i(1.5 * s)))
        except Exception:
            pass
        surf.blit(rs, (cx - hr - 2, cy - hr - 2))

        # 13 — State effects
        self._effects(surf, cx, cy, s)

    # ── Draw mini ────────────────────────────────────────────────────

    def draw_mini(self, surf: pygame.Surface, cx: int, cy: int, size: int = 28):
        """Tiny Mona for the bottom bar."""
        self._tick()
        s = size / 72.0
        key = f"mini_{size}"
        if key not in self._cache:
            hr = max(3, _i(26 * s))
            self._cache[key] = {"head": self._sphere(hr, BODY), "hr": hr}
        mc = self._cache[key]
        hr = mc["hr"]

        # Mini glow
        gc = GLOW_MAP.get(self.state)
        if gc:
            pulse = 0.5 + 0.5 * math.sin(self._st * 3)
            gr = _i(hr * 1.4)
            gs = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*gc, _i(20 * pulse)), (gr, gr), gr)
            surf.blit(gs, (cx - gr, cy - gr))

        # Head
        surf.blit(mc["head"], (cx - hr - 2, cy - hr - 2))

        # Mini ears
        for side in (-1, 1):
            tip_x = cx + side * _i(12 * s)
            tip_y = cy - hr - _i(4 * s)
            bl = cx + side * _i(4 * s)
            br = cx + side * _i(16 * s)
            by = cy - hr + _i(4 * s)
            pygame.draw.polygon(surf, BODY,
                                [(bl, by), (tip_x, tip_y), (br, by)])
            pygame.draw.circle(surf, BODY,
                               (cx + side * _i(10 * s), cy - hr + _i(2 * s)),
                               _i(4 * s))

        # Mini eyes (vertical ovals)
        erx, ery = max(2, _i(5 * s)), max(2, _i(7 * s))
        prx, pry = max(1, _i(3 * s)), max(1, _i(4.5 * s))
        for side in (-1, 1):
            ex = cx + side * _i(9 * s)
            ey = cy
            pygame.draw.ellipse(surf, EYE_W,
                                (ex - erx, ey - ery, erx * 2, ery * 2))
            pygame.draw.ellipse(surf, PUPIL_C,
                                (ex - prx, ey - pry, prx * 2, pry * 2))
            sr = max(1, _i(1.5 * s))
            pygame.draw.circle(surf, (255, 255, 255),
                               (ex - _i(1.5 * s), ey - _i(2 * s)), sr)

        # Mini nose
        nr = max(1, _i(1.5 * s))
        try:
            pygame.gfxdraw.filled_circle(surf, cx, cy + _i(5 * s), nr, NOSE_CLR)
            pygame.gfxdraw.aacircle(surf, cx, cy + _i(5 * s), nr, NOSE_CLR)
        except Exception:
            pygame.draw.circle(surf, NOSE_CLR, (cx, cy + _i(5 * s)), nr)

    # ── Ears ─────────────────────────────────────────────────────────

    def _ears(self, surf, cx, cy, hr, s):
        """Short, wide cat ears — subtle rounded bumps on the head."""
        for side in (-1, 1):
            tip_x = cx + side * _i(16 * s)
            tip_y = cy - hr - _i(2 * s)

            if self.state == LISTENING:
                tip_y -= _i(1.5 * s * abs(math.sin(self._st * 5)))

            base_in = cx + side * _i(8 * s)
            base_out = cx + side * _i(24 * s)
            base_y = cy - hr + _i(6 * s)

            # Outer ear — wide, very short
            pts = [(base_in, base_y), (tip_x, tip_y), (base_out, base_y)]
            pygame.draw.polygon(surf, BODY, pts)

            # Slight rounding at tip (not too round — cat ears, not mouse)
            pygame.draw.circle(surf, BODY,
                               (tip_x, tip_y + _i(2 * s)),
                               max(2, _i(3 * s)))

            # Large blend circle to merge base seamlessly into head
            pygame.draw.circle(surf, BODY,
                               (cx + side * _i(15 * s), cy - hr + _i(3 * s)),
                               _i(9 * s))

            # Very subtle inner ear shadow (no pink, just slightly darker)
            ipts = [
                (base_in + side * _i(5 * s), base_y - _i(2 * s)),
                (tip_x, tip_y + _i(5 * s)),
                (base_out - side * _i(5 * s), base_y - _i(2 * s)),
            ]
            inner_shade = tuple(max(0, c - 8) for c in BODY)
            pygame.draw.polygon(surf, inner_shade, ipts)

    # ── Eyes (signature vertical ovals) ──────────────────────────────

    def _eyes(self, surf, cx, cy, s):
        """Glossy vertical-oval eyes — the Octocat's most distinctive feature.

        From the SVG: eye is a tall oval, pupil is 2/3 size, no iris ring.
        Big white area with smaller dark pupil = signature look.
        """
        ecx = _i(13 * s)     # eye center x offset
        erx = _i(7 * s)      # eye horizontal radius  (big)
        ery = _i(10 * s)     # eye vertical radius    (1.43× → tall oval)
        prx = _i(4.5 * s)    # pupil horizontal radius (≈2/3 of eye)
        pry = _i(6.5 * s)    # pupil vertical radius

        if self.state == LISTENING:
            erx = _i(7.5 * s)
            ery = _i(10.5 * s)

        blink = ((self._bt % self.BLINK_EVERY)
                 > (self.BLINK_EVERY - self.BLINK_DUR)
                 and self.state == IDLE)

        # Pupil offset for gaze direction
        px, py = 0, 0
        if self.state == THINKING:
            px = _i(3 * s * math.sin(self._st * 1.5))
            py = _i(-2 * s * math.cos(self._st * 1.5))
        elif self.state == SPEAKING:
            py = _i(1 * s)

        for side in (-1, 1):
            ex = cx + side * ecx
            ey = cy

            if blink:
                pygame.draw.line(surf, EYE_W,
                                 (ex - erx, ey), (ex + erx, ey),
                                 max(2, _i(2.5 * s)))
                continue

            # Eye socket shadow
            sock = pygame.Rect(ex - erx - _i(s), ey - ery - _i(s),
                               (erx + _i(s)) * 2, (ery + _i(s)) * 2)
            ss = pygame.Surface((sock.width, sock.height), pygame.SRCALPHA)
            pygame.draw.ellipse(ss, (0, 0, 0, 25), ss.get_rect())
            surf.blit(ss, sock)

            # White of eye (vertical oval — large, bright, dominant)
            pygame.draw.ellipse(surf, EYE_W,
                                (ex - erx, ey - ery, erx * 2, ery * 2))
            try:
                pygame.gfxdraw.aaellipse(surf, ex, ey,
                                         max(1, erx), max(1, ery),
                                         (210, 210, 218))
            except Exception:
                pass

            # Subtle gradient (brighter upper region)
            gw, gh = _i(erx * 0.8), _i(ery * 0.5)
            if gw > 1 and gh > 1:
                grad = pygame.Surface((gw * 2, gh * 2), pygame.SRCALPHA)
                pygame.draw.ellipse(grad, (255, 255, 255, 25), grad.get_rect())
                surf.blit(grad, (ex - gw - _i(s), ey - ery))

            # Pupil (vertical oval, warm dark brown — matches SVG #AD5C51)
            pygame.draw.ellipse(surf, PUPIL_C,
                                (ex + px - prx, ey + py - pry,
                                 prx * 2, pry * 2))
            try:
                pygame.gfxdraw.aaellipse(surf, ex + px, ey + py,
                                         max(1, prx), max(1, pry), PUPIL_C)
            except Exception:
                pass

            # Primary highlight (large, upper-left)
            sh1 = max(1, _i(2.5 * s))
            sh1x = ex + px - _i(2.5 * s)
            sh1y = ey + py - _i(3.5 * s)
            try:
                pygame.gfxdraw.filled_circle(surf, sh1x, sh1y, sh1,
                                             (255, 255, 255))
                pygame.gfxdraw.aacircle(surf, sh1x, sh1y, sh1,
                                        (255, 255, 255))
            except Exception:
                pygame.draw.circle(surf, (255, 255, 255), (sh1x, sh1y), sh1)

            # Secondary highlight (small, lower-right)
            sh2 = max(1, _i(1.3 * s))
            sh2x = ex + px + _i(1.5 * s)
            sh2y = ey + py + _i(2.5 * s)
            try:
                pygame.gfxdraw.filled_circle(surf, sh2x, sh2y, sh2,
                                             (255, 255, 255, 180))
            except Exception:
                pygame.draw.circle(surf, (255, 255, 255), (sh2x, sh2y), sh2)

    # ── Nose ─────────────────────────────────────────────────────────

    def _nose(self, surf, cx, cy, s):
        """Small nose between the eyes — matches Octocat SVG."""
        nr = max(1, _i(2 * s))
        ny = cy + _i(10 * s)
        try:
            pygame.gfxdraw.filled_circle(surf, cx, ny, nr, NOSE_CLR)
            pygame.gfxdraw.aacircle(surf, cx, ny, nr, NOSE_CLR)
        except Exception:
            pygame.draw.circle(surf, NOSE_CLR, (cx, ny), nr)

    # ── Mouth ────────────────────────────────────────────────────────

    def _mouth(self, surf, cx, cy, s):
        my = cy + _i(14 * s)

        if self.state == HAPPY:
            rect = pygame.Rect(cx - _i(7 * s), my - _i(3 * s),
                               _i(14 * s), _i(8 * s))
            pygame.draw.arc(surf, MOUTH_C, rect,
                            math.pi + 0.4, 2 * math.pi - 0.4,
                            max(2, _i(2 * s)))
        elif self.state == SPEAKING:
            o = 0.3 + 0.7 * abs(math.sin(self._st * 5))
            h = max(2, _i(5 * s * o))
            w = _i(4 * s)
            pygame.draw.ellipse(surf, MOUTH_C,
                                pygame.Rect(cx - w, my, w * 2, h))
            if h > 3:
                pygame.draw.ellipse(surf, (130, 55, 72),
                                    pygame.Rect(cx - w + _i(s), my + _i(s),
                                                w * 2 - _i(2 * s),
                                                h - _i(2 * s)))
        elif self.state == LISTENING:
            r = max(1, _i(2.5 * s))
            try:
                pygame.gfxdraw.filled_circle(surf, cx, my + _i(s), r, MOUTH_C)
                pygame.gfxdraw.aacircle(surf, cx, my + _i(s), r, MOUTH_C)
            except Exception:
                pygame.draw.circle(surf, MOUTH_C, (cx, my + _i(s)), r)
        else:
            rect = pygame.Rect(cx - _i(5 * s), my - _i(1 * s),
                               _i(10 * s), _i(5 * s))
            pygame.draw.arc(surf, MOUTH_C, rect,
                            math.pi + 0.5, 2 * math.pi - 0.5,
                            max(1, _i(1.5 * s)))

    # ── Tentacles ────────────────────────────────────────────────────

    def _tentacles(self, surf, cx, top_y, s):
        """Smooth 3D-shaded tapered tentacles."""
        speed = 4.5 if self.state == SPEAKING else 2.0
        amp = 4 * s if self.state == SPEAKING else 2.5 * s

        for i in range(5):
            tx = cx - _i(18 * s) + i * _i(9 * s)
            wave = math.sin(self._t * speed + i * 0.8) * amp

            segs = 8
            for j in range(segs):
                t = j / segs
                jx = _i(tx + wave * t * t)
                jy = _i(top_y + 14 * s * t)
                r = max(1, _i((4.0 - j * 0.45) * s))
                # Side-dependent shading
                st = 0.5 + 0.3 * math.sin(wave * 0.1 + j * 0.3)
                color = tuple(_i(_lerp(BODY_LO[k], BODY_HI[k], st))
                              for k in range(3))
                try:
                    pygame.gfxdraw.filled_circle(surf, jx, jy, r, color)
                    pygame.gfxdraw.aacircle(surf, jx, jy, r, color)
                except Exception:
                    pygame.draw.circle(surf, color, (jx, jy), r)

    # ── State effects ────────────────────────────────────────────────

    def _effects(self, surf, cx, cy, s):
        if self.state == THINKING:
            for i in range(3):
                phase = (self._st - i * 0.4) % 1.6
                if phase < 1.0:
                    frac = (min(1.0, phase / 0.2)
                            * max(0.0, 1 - (phase - 0.4) / 0.6))
                    r = max(1, _i((3 + i) * s * frac))
                    dx = cx + _i(30 * s) + i * _i(10 * s)
                    dy = cy - _i(20 * s) - i * _i(5 * s)
                    a = _i(200 * frac)
                    ds = pygame.Surface((r * 2 + 2, r * 2 + 2),
                                        pygame.SRCALPHA)
                    pygame.draw.circle(ds, (*GLOW_MAP["thinking"], a),
                                       (r + 1, r + 1), r)
                    surf.blit(ds, (dx - r - 1, dy - r - 1))

        elif self.state == LISTENING:
            for i in range(3):
                phase = (self._st * 2 + i * 0.5) % 2.0
                if phase < 1.4:
                    arc_r = _i((16 + 18 * phase) * s)
                    a = _i(140 * (1 - phase / 1.4))
                    arc_s = pygame.Surface((arc_r * 2, arc_r * 2),
                                           pygame.SRCALPHA)
                    pygame.draw.arc(arc_s, (*GLOW_MAP["listening"], a),
                                    (0, 0, arc_r * 2, arc_r * 2),
                                    -0.5, 0.5, max(2, _i(2 * s)))
                    surf.blit(arc_s,
                              (cx + _i(28 * s) - arc_r, cy - arc_r))

        elif self.state == HAPPY:
            for i in range(6):
                angle = self._st * 1.5 + i * (2 * math.pi / 6)
                dist = _i(38 * s)
                sx = cx + _i(dist * math.cos(angle))
                sy = cy + _i(dist * math.sin(angle))
                sz = max(1, _i(3 * s
                               * abs(math.sin(self._st * 3.5 + i * 1.2))))
                c = GLOW_MAP["happy"]
                w = max(1, _i(s))
                pygame.draw.line(surf, c, (sx - sz, sy), (sx + sz, sy), w)
                pygame.draw.line(surf, c, (sx, sy - sz), (sx, sy + sz), w)
                dsz = _i(sz * 0.6)
                pygame.draw.line(surf, c,
                                 (sx - dsz, sy - dsz), (sx + dsz, sy + dsz), 1)
                pygame.draw.line(surf, c,
                                 (sx - dsz, sy + dsz), (sx + dsz, sy - dsz), 1)
