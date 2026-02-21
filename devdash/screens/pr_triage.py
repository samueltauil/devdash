"""PR Triage screen — Tinder-style swipe to review PRs."""

from __future__ import annotations

import asyncio
import logging

from devdash.screens.base import BaseScreen
from devdash.ui.widgets import Card, StatusBadge, BigButton
from devdash.ui.touch import Gesture
from devdash.ui import theme as T

log = logging.getLogger(__name__)


class PRTriageScreen(BaseScreen):
    name = "pr_triage"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.prs: list[dict] = []
        self.current_pr_idx = 0
        self.ai_summary: str = ""
        self.ai_risk: str = ""
        self.ai_concern: str = ""
        self._loading = False

    async def render(self):
        y = T.CONTENT_Y + 8

        # Header
        total = len(self.prs)
        idx = self.current_pr_idx + 1 if total > 0 else 0
        self.renderer.draw_text("PR Triage", 12, y, "heading", "text")
        self.renderer.draw_text(f"{idx} of {total}", self.config.display.width - 80, y, "body", "text_dim")
        y += 36

        if not self.prs:
            self.renderer.draw_text("No pending PRs — you're all caught up! ✨",
                                    40, y + 60, "body", "success")
            return

        pr = self.prs[self.current_pr_idx]

        # PR Card
        card = Card(self.renderer, T.CARD_MARGIN, y, T.CARD_WIDTH, 160)
        title = f"#{pr.get('number', '?')} {pr.get('title', 'Untitled')}"
        ci = "✅" if pr.get("ci_status") == "success" else "❌"
        lines = [
            f"by @{pr.get('author', '?')} · {pr.get('files_changed', '?')} files · CI {ci}",
        ]

        if self.ai_summary:
            lines.append(f"SUMMARY: {self.ai_summary}")
        if self.ai_risk:
            lines.append(f"RISK: {self.ai_risk}")
        if self.ai_concern:
            lines.append(f"CONCERN: {self.ai_concern}")

        if self._loading:
            lines.append("🤖 Copilot analyzing...")

        accent = "warning" if self.ai_risk == "MEDIUM" else "error" if self.ai_risk == "HIGH" else "success"
        card.draw(title, lines, accent_color=accent)

        # Action buttons at bottom
        btn_y = self.config.display.height - T.NAV_BAR_HEIGHT - T.BUTTON_HEIGHT - 8
        self.button_rects["reject"] = BigButton.draw(
            self.renderer, "Reject", 12, btn_y, 140, color="error", icon="◀"
        )
        self.button_rects["skip"] = BigButton.draw(
            self.renderer, "Skip", 170, btn_y, 140, color="primary", icon="▲"
        )
        self.button_rects["approve"] = BigButton.draw(
            self.renderer, "Approve", 328, btn_y, 140, color="success", icon="▶"
        )

    def on_enter(self):
        super().on_enter()
        if self.prs and not self.ai_summary:
            asyncio.create_task(self._analyze_current_pr())

    async def refresh_data(self):
        try:
            self.prs = await self.db.get_pending_prs(self.config.github.repos)
            if self.current_pr_idx >= len(self.prs):
                self.current_pr_idx = 0
        except Exception as e:
            log.error("PR refresh error: %s", e)

    def on_swipe_right(self, gesture: Gesture) -> bool:
        """Swipe right = approve."""
        if self.prs:
            asyncio.create_task(self._approve_current())
            return True
        return False

    def on_swipe_left(self, gesture: Gesture) -> bool:
        """Swipe left = request changes."""
        if self.prs:
            asyncio.create_task(self._reject_current())
            return True
        return False

    def on_swipe_up(self, gesture: Gesture):
        """Swipe up = skip."""
        self._next_pr()

    def on_button_tap(self, button_name: str):
        if button_name == "approve":
            asyncio.create_task(self._approve_current())
        elif button_name == "reject":
            asyncio.create_task(self._reject_current())
        elif button_name == "skip":
            self._next_pr()

    def _next_pr(self):
        if self.prs:
            self.current_pr_idx = (self.current_pr_idx + 1) % len(self.prs)
            self.ai_summary = ""
            self.ai_risk = ""
            self.ai_concern = ""
            asyncio.create_task(self._analyze_current_pr())

    async def _analyze_current_pr(self):
        """Use Copilot SDK to analyze the current PR."""
        if not self.prs:
            return
        self._loading = True
        pr = self.prs[self.current_pr_idx]

        try:
            result = await self.copilot.analyze_pr(
                repo=pr["repo"],
                pr_number=pr["number"],
                on_delta=lambda text: self._on_stream(text),
            )
            self.ai_summary = result.get("summary", "")
            self.ai_risk = result.get("risk", "")
            self.ai_concern = result.get("concern", "")
        except Exception as e:
            log.error("PR analysis error: %s", e)
            self.ai_summary = "Analysis unavailable"
        finally:
            self._loading = False

    async def _approve_current(self):
        if not self.prs:
            return
        pr = self.prs[self.current_pr_idx]
        try:
            await self.copilot.submit_pr_review(
                pr["repo"], pr["number"], "APPROVE"
            )
            log.info("Approved PR #%s", pr["number"])
        except Exception as e:
            log.error("Approve error: %s", e)
        self._next_pr()

    async def _reject_current(self):
        if not self.prs:
            return
        pr = self.prs[self.current_pr_idx]
        try:
            await self.copilot.submit_pr_review(
                pr["repo"], pr["number"], "REQUEST_CHANGES"
            )
            log.info("Requested changes on PR #%s", pr["number"])
        except Exception as e:
            log.error("Reject error: %s", e)
        self._next_pr()

    def _on_stream(self, text: str):
        """Handle streaming text from Copilot."""
        # Could update UI incrementally here
        pass

    def get_status(self) -> str:
        if len(self.prs) > 5:
            return "warning"
        return "success"
