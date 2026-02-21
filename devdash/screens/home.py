"""Home screen — glanceable dashboard overview."""

from __future__ import annotations

import logging

from devdash.screens.base import BaseScreen
from devdash.ui.widgets import CountCard
from devdash.ui import theme as T

log = logging.getLogger(__name__)


class HomeScreen(BaseScreen):
    name = "home"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pr_count = 0
        self.ci_failing = 0
        self.notifications = 0
        self.streak = 0

    async def render(self):
        y = T.CONTENT_Y + 20

        # Title
        self.renderer.draw_text("DevDash", 12, y, "heading", "accent")
        y += 40

        # Count cards row
        card_w = 140
        gap = 16
        start_x = (self.config.display.width - 3 * card_w - 2 * gap) // 2

        self.button_rects["prs"] = CountCard.draw(
            self.renderer, self.pr_count, "PRs pending",
            start_x, y, card_w, 80, accent_color="warning"
        )
        self.button_rects["ci"] = CountCard.draw(
            self.renderer, self.ci_failing, "CI failing",
            start_x + card_w + gap, y, card_w, 80, accent_color="error"
        )
        self.button_rects["notif"] = CountCard.draw(
            self.renderer, self.notifications, "unread",
            start_x + 2 * (card_w + gap), y, card_w, 80, accent_color="info"
        )

        y += 100

        # Streak
        if self.streak > 0:
            self.renderer.draw_text(
                f"🔥 {self.streak}-day commit streak!",
                self.config.display.width // 2 - 100, y, "body", "accent"
            )

    async def refresh_data(self):
        try:
            prs = await self.db.get_pending_prs(self.config.github.repos)
            self.pr_count = len(prs)

            runs = await self.db.get_failed_runs()
            self.ci_failing = len(runs)
        except Exception as e:
            log.error("Home refresh error: %s", e)

    def on_button_tap(self, button_name: str):
        # Navigate to relevant screen when tapping a card
        screen_map = {"prs": "pr_triage", "ci": "ci_diagnosis", "notif": "standup"}
        target = screen_map.get(button_name)
        if target:
            # Screen manager handles this via navigation
            from devdash.ui.screen_manager import ScreenManager
            # This is handled by the screen manager checking button_rects
            log.info("Tap on %s → navigate to %s", button_name, target)

    def get_status(self) -> str:
        if self.ci_failing > 0:
            return "error"
        if self.pr_count > 3:
            return "warning"
        return "success"
