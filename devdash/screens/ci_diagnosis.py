"""CI Diagnosis screen — auto-populated Copilot failure analysis."""

from __future__ import annotations

import asyncio
import logging

from devdash.screens.base import BaseScreen
from devdash.ui.widgets import Card, BigButton
from devdash.ui import theme as T

log = logging.getLogger(__name__)


class CIDiagnosisScreen(BaseScreen):
    name = "ci_diagnosis"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.failures: list[dict] = []
        self.current_idx = 0
        self.diagnosis: str = ""
        self.fix_suggestion: str = ""
        self.caused_by: str = ""
        self._loading = False
        self._streaming_text = ""

    async def render(self):
        y = T.CONTENT_Y + 8

        if not self.failures:
            self.renderer.draw_text("CI Status", 12, y, "heading", "text")
            y += 50
            self.renderer.draw_text("All pipelines passing! ✅", 80, y, "body", "success")
            return

        failure = self.failures[self.current_idx]

        # Header
        self.renderer.draw_text("🚨 CI Failed", 12, y, "heading", "error")
        ago = failure.get("updated_at", "")
        self.renderer.draw_text(ago, self.config.display.width - 120, y + 4, "small", "text_dim")
        y += 36

        # Error card
        card = Card(self.renderer, T.CARD_MARGIN, y, T.CARD_WIDTH, 140)
        lines = []

        if self._loading:
            lines.append("🤖 Copilot diagnosing...")
            if self._streaming_text:
                # Show streaming diagnosis
                for line in self._streaming_text.split("\n")[:4]:
                    lines.append(line[:60])
        else:
            if self.diagnosis:
                lines.append(self.diagnosis[:80])
            if self.fix_suggestion:
                lines.append(f"Fix: {self.fix_suggestion[:60]}")
            if self.caused_by:
                lines.append(f"Caused by: {self.caused_by}")

        card.draw(f"Run #{failure.get('run_id', '?')}", lines, accent_color="error")

        # Action buttons
        btn_y = self.config.display.height - T.NAV_BAR_HEIGHT - T.BUTTON_HEIGHT - 8
        if self.diagnosis and not self._loading:
            self.button_rects["fix"] = BigButton.draw(
                self.renderer, "Create Fix PR", 12, btn_y, 220, color="success", icon="🔧"
            )
            self.button_rects["dismiss"] = BigButton.draw(
                self.renderer, "Dismiss", 248, btn_y, 140, color="surface"
            )

    def on_enter(self):
        super().on_enter()
        if self.failures and not self.diagnosis:
            asyncio.create_task(self._diagnose_current())

    async def refresh_data(self):
        try:
            self.failures = await self.db.get_failed_runs()
            if self.failures and not self.diagnosis:
                asyncio.create_task(self._diagnose_current())
        except Exception as e:
            log.error("CI refresh error: %s", e)

    async def _diagnose_current(self):
        if not self.failures:
            return
        self._loading = True
        self._streaming_text = ""
        failure = self.failures[self.current_idx]

        try:
            result = await self.copilot.diagnose_ci_failure(
                repo=failure["repo"],
                run_id=failure["run_id"],
                on_delta=lambda text: self._on_stream(text),
            )
            self.diagnosis = result.get("diagnosis", "")
            self.fix_suggestion = result.get("fix", "")
            self.caused_by = result.get("caused_by", "")
        except Exception as e:
            log.error("CI diagnosis error: %s", e)
            self.diagnosis = "Diagnosis unavailable"
        finally:
            self._loading = False

    def _on_stream(self, text: str):
        self._streaming_text += text

    def on_button_tap(self, button_name: str):
        if button_name == "fix":
            asyncio.create_task(self._create_fix_pr())
        elif button_name == "dismiss":
            self._next_failure()

    async def _create_fix_pr(self):
        if not self.failures:
            return
        failure = self.failures[self.current_idx]
        try:
            await self.copilot.create_ci_fix_pr(
                repo=failure["repo"],
                run_id=failure["run_id"],
            )
            log.info("Fix PR created for run %s", failure["run_id"])
            self._next_failure()
        except Exception as e:
            log.error("Fix PR error: %s", e)

    def _next_failure(self):
        self.diagnosis = ""
        self.fix_suggestion = ""
        self.caused_by = ""
        self._streaming_text = ""
        if self.failures:
            self.current_idx = (self.current_idx + 1) % len(self.failures)
            asyncio.create_task(self._diagnose_current())

    def get_status(self) -> str:
        return "error" if self.failures else "success"
