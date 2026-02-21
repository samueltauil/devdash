"""Touch gesture detection — tap, swipe, long press."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum, auto

import pygame

from devdash.config import AppConfig

log = logging.getLogger(__name__)

SWIPE_THRESHOLD = 50  # pixels
LONG_PRESS_MS = 600
TAP_MAX_MS = 300


class GestureType(Enum):
    TAP = auto()
    SWIPE_LEFT = auto()
    SWIPE_RIGHT = auto()
    SWIPE_UP = auto()
    SWIPE_DOWN = auto()
    LONG_PRESS = auto()


@dataclass
class Gesture:
    type: GestureType
    x: int
    y: int
    start_x: int
    start_y: int


class TouchHandler:
    def __init__(self, config: AppConfig):
        self.config = config
        self._touch_start: tuple[int, int] | None = None
        self._touch_start_time: float = 0

    def process_events(self) -> list[Gesture]:
        """Process PyGame events and return detected gestures."""
        gestures = []

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise SystemExit

            elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                if event.type == pygame.FINGERDOWN:
                    x = int(event.x * self.config.display.width)
                    y = int(event.y * self.config.display.height)
                else:
                    x, y = event.pos
                self._touch_start = (x, y)
                self._touch_start_time = time.monotonic()

            elif event.type in (pygame.MOUSEBUTTONUP, pygame.FINGERUP):
                if self._touch_start is None:
                    continue

                if event.type == pygame.FINGERUP:
                    x = int(event.x * self.config.display.width)
                    y = int(event.y * self.config.display.height)
                else:
                    x, y = event.pos

                sx, sy = self._touch_start
                dx = x - sx
                dy = y - sy
                duration = time.monotonic() - self._touch_start_time

                gesture = self._classify(sx, sy, x, y, dx, dy, duration)
                if gesture:
                    gestures.append(gesture)

                self._touch_start = None

            # Keyboard fallback for desktop testing
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    gestures.append(Gesture(GestureType.SWIPE_LEFT, 240, 160, 340, 160))
                elif event.key == pygame.K_RIGHT:
                    gestures.append(Gesture(GestureType.SWIPE_RIGHT, 240, 160, 140, 160))
                elif event.key == pygame.K_UP:
                    gestures.append(Gesture(GestureType.SWIPE_UP, 240, 160, 240, 260))
                elif event.key == pygame.K_DOWN:
                    gestures.append(Gesture(GestureType.SWIPE_DOWN, 240, 160, 240, 60))
                elif event.key == pygame.K_RETURN:
                    gestures.append(Gesture(GestureType.TAP, 240, 160, 240, 160))
                elif event.key == pygame.K_q:
                    raise SystemExit

        # Check for long press while still holding
        if self._touch_start is not None:
            elapsed = time.monotonic() - self._touch_start_time
            if elapsed > LONG_PRESS_MS / 1000:
                sx, sy = self._touch_start
                gestures.append(Gesture(GestureType.LONG_PRESS, sx, sy, sx, sy))
                self._touch_start = None

        return gestures

    def _classify(self, sx: int, sy: int, x: int, y: int,
                  dx: int, dy: int, duration: float) -> Gesture | None:
        abs_dx, abs_dy = abs(dx), abs(dy)

        # Swipe detection
        if abs_dx > SWIPE_THRESHOLD or abs_dy > SWIPE_THRESHOLD:
            if abs_dx > abs_dy:
                gt = GestureType.SWIPE_RIGHT if dx > 0 else GestureType.SWIPE_LEFT
            else:
                gt = GestureType.SWIPE_DOWN if dy > 0 else GestureType.SWIPE_UP
            return Gesture(gt, x, y, sx, sy)

        # Long press
        if duration > LONG_PRESS_MS / 1000:
            return Gesture(GestureType.LONG_PRESS, x, y, sx, sy)

        # Tap
        return Gesture(GestureType.TAP, x, y, sx, sy)
