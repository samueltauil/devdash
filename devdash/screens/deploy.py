"""Deploy screen — physical button + Copilot AI safety analysis."""

from __future__ import annotations

import asyncio
import logging

from devdash.screens.base import BaseScreen
from devdash.ui.widgets import BigButton, ConfidenceMeter
from devdash.ui import theme as T

log = logging.getLogger(__name__)


class DeployScreen(BaseScreen):
    name = "deploy"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.confidence: int = 0
        self.risk_level: str = ""
        self.analysis_text: str = ""
        self.deploy_status: str = "idle"  # idle, analyzing, ready, deploying, success, failed
        self._streaming_text = ""

    async def render(self):
        y = T.CONTENT_Y + 8

        # Header
        self.renderer.draw_text("🔘 Smart Deploy", 12, y, "heading", "text")
        y += 40

        repo = self.config.deploy.repo or "No repo configured"
        self.renderer.draw_text(f"Target: {repo}", 16, y, "body", "text_dim")
        y += 28

        if self.deploy_status == "idle":
            self.renderer.draw_text("Press the physical button", 60, y + 30, "body", "text_dim")
            self.renderer.draw_text("to start deploy analysis", 70, y + 55, "body", "text_dim")
            # Also allow tap
            self.button_rects["analyze"] = BigButton.draw(
                self.renderer, "Start Analysis", 140, y + 90, 200, color="primary", icon="🔍"
            )

        elif self.deploy_status == "analyzing":
            self.renderer.draw_text("🔍 Copilot analyzing deploy safety...", 40, y + 20, "body", "info")
            if self._streaming_text:
                for line in self._streaming_text.split("\n")[-4:]:
                    y += 22
                    self.renderer.draw_text(line[:55], 16, y, "small", "text_dim")

        elif self.deploy_status == "ready":
            # Confidence meter
            ConfidenceMeter.draw(self.renderer, self.confidence,
                                 self.config.display.width // 2 - 100, y, 200)
            y += 36

            risk_color = "success" if self.risk_level == "LOW" else "warning" if self.risk_level == "MEDIUM" else "error"
            self.renderer.draw_text(
                f"CONFIDENCE: {self.confidence}%  |  RISK: {self.risk_level}",
                40, y, "body", risk_color
            )
            y += 28

            # Analysis summary
            for line in self.analysis_text.split("\n")[:3]:
                self.renderer.draw_text(line[:55], 16, y, "small", "text_dim")
                y += 20

            # Confirm button (only if above threshold)
            btn_y = self.config.display.height - T.NAV_BAR_HEIGHT - T.BUTTON_HEIGHT - 8
            if self.confidence >= self.config.deploy.min_confidence:
                self.button_rects["confirm"] = BigButton.draw(
                    self.renderer, "Confirm Deploy", 80, btn_y, 200, color="success", icon="🚀"
                )
                self.renderer.draw_text("or press button", 310, btn_y + 14, "small", "text_dim")
            else:
                self.renderer.draw_text(
                    f"⚠ Below {self.config.deploy.min_confidence}% threshold — deploy blocked",
                    30, btn_y + 10, "body", "error"
                )

        elif self.deploy_status == "deploying":
            self.renderer.draw_text("🚀 Deploying...", 150, y + 50, "heading", "info")
            self.renderer.draw_text("LED strip shows deploy progress", 100, y + 90, "small", "text_dim")

        elif self.deploy_status == "success":
            self.renderer.draw_text("✅ Deploy Successful!", 100, y + 50, "heading", "success")

        elif self.deploy_status == "failed":
            self.renderer.draw_text("❌ Deploy Failed", 120, y + 50, "heading", "error")
            self.button_rects["diagnose"] = BigButton.draw(
                self.renderer, "Diagnose", 160, y + 100, 160, color="error", icon="🧠"
            )

    def on_enter(self):
        super().on_enter()
        # Listen for physical button press
        self.button.on_press(self._on_button_press)

    def on_leave(self):
        super().on_leave()
        self.button.on_press(None)

    def _on_button_press(self):
        if self.deploy_status == "idle":
            asyncio.create_task(self._run_analysis())
        elif self.deploy_status == "ready" and self.confidence >= self.config.deploy.min_confidence:
            asyncio.create_task(self._execute_deploy())

    def on_button_tap(self, button_name: str):
        if button_name == "analyze":
            asyncio.create_task(self._run_analysis())
        elif button_name == "confirm":
            asyncio.create_task(self._execute_deploy())

    async def _run_analysis(self):
        self.deploy_status = "analyzing"
        self._streaming_text = ""

        try:
            result = await self.copilot.analyze_deploy(
                repo=self.config.deploy.repo,
                environment=self.config.deploy.environment,
                on_delta=lambda text: self._on_stream(text),
            )
            self.confidence = result.get("confidence", 0)
            self.risk_level = result.get("risk", "UNKNOWN")
            self.analysis_text = result.get("analysis", "")
            self.deploy_status = "ready"

            # LED feedback
            if self.confidence >= 80:
                self.leds.set_pattern("breathe_green")
            elif self.confidence >= 50:
                self.leds.set_pattern("breathe_yellow")
            else:
                self.leds.set_pattern("breathe_red")
        except Exception as e:
            log.error("Deploy analysis error: %s", e)
            self.deploy_status = "idle"

    async def _execute_deploy(self):
        self.deploy_status = "deploying"
        self.leds.set_pattern("breathe_blue")

        try:
            result = await self.copilot.trigger_deploy(
                repo=self.config.deploy.repo,
                workflow=self.config.deploy.workflow,
                ref=self.config.deploy.ref,
            )
            await self.db.save_deploy(
                self.config.deploy.repo, self.config.deploy.ref,
                self.confidence, self.risk_level,
                result.get("run_id"), "success"
            )
            self.deploy_status = "success"
            self.leds.set_pattern("celebration")
            self.buzzer.play_success()
        except Exception as e:
            log.error("Deploy error: %s", e)
            self.deploy_status = "failed"
            self.leds.set_pattern("flash_red")
            self.buzzer.play_error()

    def _on_stream(self, text: str):
        self._streaming_text += text
