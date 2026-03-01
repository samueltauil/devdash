"""Reusable UI widgets — chat bubble and mic button."""

from __future__ import annotations

import pygame

from devdash.ui.renderer import Renderer
from devdash.ui import theme as T


class ChatBubble:
    """A rounded chat message bubble."""

    @staticmethod
    def draw(renderer: Renderer, lines: list[str], x: int, y: int,
             w: int, color: str = "surface") -> pygame.Rect:
        h = len(lines) * 20 + 2 * T.BUBBLE_PADDING
        renderer.draw_rect(x, y, w, h, color, T.BUBBLE_BORDER_RADIUS)
        ty = y + T.BUBBLE_PADDING
        for line in lines:
            renderer.draw_text(line, x + T.BUBBLE_PADDING, ty, "body", "text")
            ty += 20
        return pygame.Rect(x, y, w, h)


class MicButton:
    """Large tap-friendly mic button."""

    @staticmethod
    def draw(renderer: Renderer, label: str, x: int, y: int,
             w: int = 280, h: int = T.BUTTON_HEIGHT,
             color: str = "primary") -> pygame.Rect:
        return renderer.draw_button(label, x, y, w, h, color)
