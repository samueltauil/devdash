"""Transition animations for screen changes."""

from __future__ import annotations

import pygame

from devdash.ui import theme as T


def slide_transition(screen: pygame.Surface, old_surface: pygame.Surface,
                     new_surface: pygame.Surface, direction: int, progress: float):
    """Slide transition between screens. direction: -1 = left, 1 = right."""
    w = screen.get_width()
    offset = int(w * (1.0 - progress) * direction)

    screen.fill((0, 0, 0))
    screen.blit(old_surface, (offset - w * direction, T.STATUS_BAR_HEIGHT))
    screen.blit(new_surface, (offset, T.STATUS_BAR_HEIGHT))


def celebration_burst(screen: pygame.Surface, cx: int, cy: int, progress: float):
    """Rainbow burst animation for PR merged / deploy success."""
    import math
    import random

    colors = [
        (255, 0, 0), (255, 127, 0), (255, 255, 0),
        (0, 255, 0), (0, 0, 255), (148, 0, 211),
    ]

    particles = 12
    for i in range(particles):
        angle = (2 * math.pi * i / particles) + progress * math.pi
        radius = int(80 * progress)
        x = cx + int(radius * math.cos(angle))
        y = cy + int(radius * math.sin(angle))
        size = max(2, int(8 * (1 - progress)))
        color = colors[i % len(colors)]
        alpha = int(255 * (1 - progress))
        pygame.draw.circle(screen, color, (x, y), size)
