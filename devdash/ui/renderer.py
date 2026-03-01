"""PyGame renderer — handles display initialization, fonts, and drawing primitives."""

from __future__ import annotations

import logging
from pathlib import Path

import pygame

from devdash.config import AppConfig

log = logging.getLogger(__name__)

FONT_DIR = Path(__file__).parent.parent / "assets" / "fonts"


class Renderer:
    def __init__(self, config: AppConfig):
        self.config = config
        self.width = config.display.width
        self.height = config.display.height

        import os
        # Set up for SPI LCD framebuffer before pygame init
        if config.display.fullscreen and os.path.exists("/dev/fb0"):
            os.environ.setdefault("SDL_FBDEV", "/dev/fb0")
            # Try fbcon first, fall back to directfb, then dummy
            if "SDL_VIDEODRIVER" not in os.environ:
                os.environ["SDL_VIDEODRIVER"] = "fbcon"

        pygame.init()
        flags = pygame.FULLSCREEN if config.display.fullscreen else 0

        try:
            self.screen = pygame.display.set_mode((self.width, self.height), flags)
        except pygame.error:
            # fbcon may fail over SSH — try kmsdrm, then dummy
            import os
            for driver in ("kmsdrm", "directfb", "dummy"):
                os.environ["SDL_VIDEODRIVER"] = driver
                try:
                    pygame.quit()
                    pygame.init()
                    self.screen = pygame.display.set_mode((self.width, self.height), flags)
                    log.info("Using SDL video driver: %s", driver)
                    break
                except pygame.error:
                    continue
            else:
                log.warning("All video drivers failed — using windowed dummy")
                os.environ["SDL_VIDEODRIVER"] = "dummy"
                pygame.quit()
                pygame.init()
                self.screen = pygame.display.set_mode((self.width, self.height))

        pygame.display.set_caption("DevDash")
        pygame.mouse.set_visible(False)

        # Load fonts
        self.fonts: dict[str, pygame.font.Font] = {}
        self._load_fonts()

        # Parse theme colors
        self.colors = {}
        theme = config.theme
        for attr in theme.__dataclass_fields__:
            self.colors[attr] = theme.color(attr)

    def _load_fonts(self):
        font_path = FONT_DIR / "DejaVuSans.ttf"
        if font_path.exists():
            self.fonts["body"] = pygame.font.Font(str(font_path), 16)
            self.fonts["heading"] = pygame.font.Font(str(font_path), 24)
            self.fonts["large"] = pygame.font.Font(str(font_path), 32)
            self.fonts["small"] = pygame.font.Font(str(font_path), 14)
            self.fonts["icon"] = pygame.font.Font(str(font_path), 28)
        else:
            log.warning("Custom font not found — using default")
            self.fonts["body"] = pygame.font.SysFont(None, 20)
            self.fonts["heading"] = pygame.font.SysFont(None, 28)
            self.fonts["large"] = pygame.font.SysFont(None, 36)
            self.fonts["small"] = pygame.font.SysFont(None, 16)
            self.fonts["icon"] = pygame.font.SysFont(None, 32)

    def clear(self, color: str = "background"):
        self.screen.fill(self.colors.get(color, self.colors["background"]))

    def draw_text(self, text: str, x: int, y: int, font: str = "body",
                  color: str = "text", max_width: int | None = None) -> pygame.Rect:
        """Draw text at position, optionally truncating to max_width."""
        f = self.fonts.get(font, self.fonts["body"])
        c = self.colors.get(color, self.colors["text"])

        if max_width and f.size(text)[0] > max_width:
            while f.size(text + "…")[0] > max_width and len(text) > 1:
                text = text[:-1]
            text += "…"

        surface = f.render(text, True, c)
        rect = self.screen.blit(surface, (x, y))
        return rect

    def draw_rect(self, x: int, y: int, w: int, h: int, color: str = "surface",
                  border_radius: int = 8):
        c = self.colors.get(color, self.colors["surface"])
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, c, rect, border_radius=border_radius)
        return rect

    def draw_status_bar(self, time_str: str, cpu_temp: str, status_color: str = "success"):
        """Draw the 32px top status bar."""
        self.draw_rect(0, 0, self.width, 32, "surface", border_radius=0)
        self.draw_text(time_str, 8, 6, "small", "text_dim")
        self.draw_text(cpu_temp, self.width - 80, 6, "small", "text_dim")
        # Status dot
        dot_color = self.colors.get(status_color, self.colors["success"])
        pygame.draw.circle(self.screen, dot_color, (self.width - 16, 16), 6)

    def draw_nav_bar(self, current_idx: int, total: int):
        """Draw bottom navigation bar with screen indicator dots."""
        y = self.height - 40
        self.draw_rect(0, y, self.width, 40, "surface", border_radius=0)

        # Dots
        dot_spacing = 16
        start_x = (self.width - (total - 1) * dot_spacing) // 2
        for i in range(total):
            x = start_x + i * dot_spacing
            color = self.colors["accent"] if i == current_idx else self.colors["text_dim"]
            pygame.draw.circle(self.screen, color, (x, y + 12), 4)

    def draw_button(self, text: str, x: int, y: int, w: int, h: int,
                    color: str = "primary", text_color: str = "text") -> pygame.Rect:
        """Draw a tappable button and return its rect for hit testing."""
        rect = self.draw_rect(x, y, w, h, color, border_radius=12)
        f = self.fonts["body"]
        tw, th = f.size(text)
        tx = x + (w - tw) // 2
        ty = y + (h - th) // 2
        self.draw_text(text, tx, ty, "body", text_color)
        return rect

    def flip(self):
        pygame.display.flip()

    def quit(self):
        pygame.quit()
