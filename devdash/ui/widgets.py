"""Reusable UI widgets — cards, buttons, progress indicators, status badges."""

from __future__ import annotations

import pygame

from devdash.ui.renderer import Renderer
from devdash.ui import theme as T


class Card:
    """A rounded-corner card with title and content lines."""

    def __init__(self, renderer: Renderer, x: int, y: int, w: int, h: int):
        self.r = renderer
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.rect = pygame.Rect(x, y, w, h)

    def draw(self, title: str = "", lines: list[str] | None = None,
             color: str = "surface", accent_color: str | None = None):
        self.r.draw_rect(self.x, self.y, self.w, self.h, color, T.CARD_BORDER_RADIUS)

        # Accent stripe on left
        if accent_color:
            c = self.r.colors.get(accent_color, self.r.colors["accent"])
            stripe = pygame.Rect(self.x, self.y + 4, 4, self.h - 8)
            pygame.draw.rect(self.r.screen, c, stripe, border_radius=2)

        cy = self.y + T.CARD_PADDING
        if title:
            self.r.draw_text(title, self.x + T.CARD_PADDING + 8, cy, "heading", "text",
                             max_width=self.w - 2 * T.CARD_PADDING)
            cy += 30

        for line in (lines or []):
            if cy + 20 > self.y + self.h - T.CARD_PADDING:
                self.r.draw_text("…", self.x + T.CARD_PADDING + 8, cy, "small", "text_dim")
                break
            self.r.draw_text(line, self.x + T.CARD_PADDING + 8, cy, "body", "text",
                             max_width=self.w - 2 * T.CARD_PADDING - 16)
            cy += 22
        return self.rect


class StatusBadge:
    """Colored pill badge (e.g., PASSING, FAILING, HIGH RISK)."""

    BADGE_COLORS = {
        "passing": "success",
        "failing": "error",
        "pending": "warning",
        "low": "success",
        "medium": "warning",
        "high": "error",
    }

    @staticmethod
    def draw(renderer: Renderer, text: str, x: int, y: int, badge_type: str = "passing"):
        color = StatusBadge.BADGE_COLORS.get(badge_type.lower(), "info")
        c = renderer.colors.get(color, renderer.colors["info"])

        f = renderer.fonts["small"]
        tw, th = f.size(text.upper())
        pw, ph = tw + 16, th + 6

        pill = pygame.Rect(x, y, pw, ph)
        pygame.draw.rect(renderer.screen, c, pill, border_radius=ph // 2)
        renderer.draw_text(text.upper(), x + 8, y + 3, "small", "text")
        return pill


class ConfidenceMeter:
    """Horizontal bar showing a confidence/risk score (0-100%)."""

    @staticmethod
    def draw(renderer: Renderer, score: int, x: int, y: int, w: int = 200, h: int = 24):
        # Background
        bg = pygame.Rect(x, y, w, h)
        pygame.draw.rect(renderer.screen, renderer.colors["surface"], bg, border_radius=h // 2)

        # Filled portion
        if score > 70:
            color = "success"
        elif score > 40:
            color = "warning"
        else:
            color = "error"
        fill_w = max(h, int(w * score / 100))
        fill = pygame.Rect(x, y, fill_w, h)
        pygame.draw.rect(renderer.screen, renderer.colors[color], fill, border_radius=h // 2)

        # Label
        label = f"{score}%"
        renderer.draw_text(label, x + w // 2 - 15, y + 3, "small", "text")


class BigButton:
    """Large tap-friendly button (≥48px height)."""

    @staticmethod
    def draw(renderer: Renderer, text: str, x: int, y: int,
             w: int = 140, h: int = T.BUTTON_HEIGHT,
             color: str = "primary", icon: str = "") -> pygame.Rect:
        label = f"{icon} {text}".strip() if icon else text
        return renderer.draw_button(label, x, y, w, h, color)


class CountCard:
    """Small card showing a number + label (e.g., "3 PRs pending")."""

    @staticmethod
    def draw(renderer: Renderer, count: int | str, label: str,
             x: int, y: int, w: int = 140, h: int = 80,
             color: str = "surface", accent_color: str = "info"):
        renderer.draw_rect(x, y, w, h, color, T.CARD_BORDER_RADIUS)

        # Big number
        renderer.draw_text(str(count), x + w // 2 - 12, y + 10, "large", accent_color)
        # Label
        renderer.draw_text(label, x + w // 2 - len(label) * 3, y + 50, "small", "text_dim")

        return pygame.Rect(x, y, w, h)
