"""Screen manager — handles navigation between screens with swipe transitions."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime

import pygame

from devdash.config import AppConfig
from devdash.ui.renderer import Renderer
from devdash.ui.touch import TouchHandler, GestureType
from devdash.ui import theme as T
from devdash.screens.base import BaseScreen
from devdash.screens.home import HomeScreen
from devdash.screens.pr_triage import PRTriageScreen
from devdash.screens.ci_diagnosis import CIDiagnosisScreen
from devdash.screens.standup import StandupScreen
from devdash.screens.deploy import DeployScreen
from devdash.screens.context_chat import ContextChatScreen

log = logging.getLogger(__name__)


class ScreenManager:
    def __init__(self, config, renderer, touch, github_service,
                 copilot_service, system_service, leds, button, buzzer, db):
        self.config = config
        self.renderer = renderer
        self.touch = touch
        self.clock = pygame.time.Clock()

        # Build screen list
        ctx = {
            "config": config,
            "renderer": renderer,
            "github": github_service,
            "copilot": copilot_service,
            "system": system_service,
            "leds": leds,
            "button": button,
            "buzzer": buzzer,
            "db": db,
        }

        self.screens: list[BaseScreen] = [
            HomeScreen(**ctx),
            PRTriageScreen(**ctx),
            CIDiagnosisScreen(**ctx),
            StandupScreen(**ctx),
            DeployScreen(**ctx),
            ContextChatScreen(**ctx),
        ]
        self.current_idx = 0
        self._last_poll = 0

    @property
    def current_screen(self) -> BaseScreen:
        return self.screens[self.current_idx]

    def navigate(self, direction: int):
        """Switch screen: -1 = prev, 1 = next."""
        new_idx = self.current_idx + direction
        if 0 <= new_idx < len(self.screens):
            self.screens[self.current_idx].on_leave()
            self.current_idx = new_idx
            self.screens[self.current_idx].on_enter()
            log.info("Screen → %s", self.current_screen.name)

    def navigate_to(self, screen_name: str):
        """Jump to a named screen."""
        for i, s in enumerate(self.screens):
            if s.name == screen_name:
                if i != self.current_idx:
                    self.screens[self.current_idx].on_leave()
                    self.current_idx = i
                    self.screens[self.current_idx].on_enter()
                return

    async def run(self, shutdown_event: asyncio.Event):
        """Main event loop."""
        self.screens[0].on_enter()

        while not shutdown_event.is_set():
            # Process touch input
            gestures = self.touch.process_events()
            for gesture in gestures:
                if gesture.type == GestureType.SWIPE_LEFT:
                    # Check if screen wants to handle it
                    if not self.current_screen.on_swipe_left(gesture):
                        self.navigate(1)
                elif gesture.type == GestureType.SWIPE_RIGHT:
                    if not self.current_screen.on_swipe_right(gesture):
                        self.navigate(-1)
                elif gesture.type == GestureType.TAP:
                    self.current_screen.on_tap(gesture)
                elif gesture.type == GestureType.SWIPE_UP:
                    self.current_screen.on_swipe_up(gesture)
                elif gesture.type == GestureType.LONG_PRESS:
                    self.current_screen.on_long_press(gesture)

            # Periodic data refresh
            now = time.monotonic()
            if now - self._last_poll > self.config.github.poll_interval:
                self._last_poll = now
                asyncio.create_task(self._poll_data())

            # Render
            self.renderer.clear()

            # Status bar
            time_str = datetime.now().strftime("%H:%M  %a %b %d")
            cpu_temp = await self._get_cpu_temp()
            status_color = self._get_overall_status()
            self.renderer.draw_status_bar(time_str, cpu_temp, status_color)

            # Screen content
            await self.current_screen.render()

            # Navigation bar
            self.renderer.draw_nav_bar(self.current_idx, len(self.screens))

            self.renderer.flip()
            self.clock.tick(self.config.display.fps)

            # Yield to asyncio
            await asyncio.sleep(0)

    async def _poll_data(self):
        """Background data refresh."""
        try:
            for screen in self.screens:
                await screen.refresh_data()
        except Exception as e:
            log.error("Poll error: %s", e)

    async def _get_cpu_temp(self) -> str:
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                temp = int(f.read().strip()) / 1000
                return f"{temp:.0f}°C"
        except (FileNotFoundError, ValueError):
            return ""

    def _get_overall_status(self) -> str:
        """Determine overall status color based on all screen states."""
        # Check if any screen reports an error state
        for screen in self.screens:
            status = screen.get_status()
            if status == "error":
                return "error"
            if status == "warning":
                return "warning"
        return "success"
