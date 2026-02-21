"""Base screen class — all screens inherit from this."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from devdash.ui.touch import Gesture

log = logging.getLogger(__name__)


class BaseScreen(ABC):
    """Abstract base for all DevDash screens."""

    name: str = "base"

    def __init__(self, config, renderer, github, copilot, system,
                 leds, button, buzzer, db, **kwargs):
        self.config = config
        self.renderer = renderer
        self.github = github
        self.copilot = copilot
        self.system = system
        self.leds = leds
        self.button = button
        self.buzzer = buzzer
        self.db = db
        self._status = "success"
        self.button_rects: dict[str, object] = {}

    @abstractmethod
    async def render(self):
        """Draw the screen content (between status bar and nav bar)."""
        ...

    async def refresh_data(self):
        """Called periodically to fetch new data."""
        pass

    def on_enter(self):
        """Called when this screen becomes active."""
        log.debug("Entering %s", self.name)

    def on_leave(self):
        """Called when navigating away from this screen."""
        log.debug("Leaving %s", self.name)

    def on_tap(self, gesture: Gesture):
        """Handle tap gesture. Override in subclasses."""
        # Check registered button rects
        for name, rect in self.button_rects.items():
            if rect.collidepoint(gesture.x, gesture.y):
                self.on_button_tap(name)
                return

    def on_button_tap(self, button_name: str):
        """Handle tap on a named button. Override in subclasses."""
        pass

    def on_swipe_left(self, gesture: Gesture) -> bool:
        """Handle swipe left. Return True if consumed (prevents screen nav)."""
        return False

    def on_swipe_right(self, gesture: Gesture) -> bool:
        """Handle swipe right. Return True if consumed (prevents screen nav)."""
        return False

    def on_swipe_up(self, gesture: Gesture):
        """Handle swipe up."""
        pass

    def on_long_press(self, gesture: Gesture):
        """Handle long press."""
        pass

    def get_status(self) -> str:
        """Return current status: 'success', 'warning', or 'error'."""
        return self._status

    def hit_test(self, x: int, y: int, rect) -> bool:
        """Check if a point is inside a rect."""
        return rect.collidepoint(x, y) if rect else False
