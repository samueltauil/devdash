"""Copilot AI service — Copilot SDK with GitHub Models API fallback."""

from __future__ import annotations

import json
import logging
from typing import Callable, Optional

import httpx

from devdash.config import AppConfig

log = logging.getLogger(__name__)

_MODELS_URL = "https://models.inference.ai.azure.com/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"


class CopilotService:
    """AI agent: tries Copilot SDK first, falls back to GitHub Models API."""

    def __init__(self, config: AppConfig, github_service=None, db=None):
        self.config = config
        self.github_service = github_service
        self.db = db
        self._client = None
        self._session = None
        self._started = False
        self._use_models_api = False
        self._history: list[dict] = []

    async def start(self):
        """Initialize the Copilot SDK client, fall back to Models API."""
        try:
            from copilot import CopilotClient

            self._client = CopilotClient({
                "cli_path": self.config.copilot.cli_path,
                "log_level": "warn",
            })
            await self._client.start()
            self._started = True
            log.info("Copilot SDK client started")
        except ImportError:
            log.info("Copilot SDK not available — using GitHub Models API")
            self._use_models_api = True
            self._started = True
        except Exception as e:
            log.warning("Copilot SDK failed (%s) — using GitHub Models API", e)
            self._use_models_api = True
            self._started = True

    async def stop(self):
        if self._session:
            try:
                await self._session.destroy()
            except Exception:
                pass
        if self._client:
            try:
                await self._client.stop()
            except Exception:
                pass
        self._started = False

    # ─── System prompt ───

    def _system_prompt(self) -> str:
        repos = ", ".join(self.config.github.repos) if self.config.github.repos else "none configured"
        return (
            "You are DevDash, an AI developer companion on a Raspberry Pi "
            "with a 3.5\" LCD screen. The developer interacts via voice.\n\n"
            f"Monitored repositories: {repos}\n\n"
            "You help with CI/CD, pull requests, standup briefings, "
            "deployments, and code context questions.\n\n"
            "Guidelines:\n"
            "- Be concise — responses display on a 480×320 screen\n"
            "- Max 3-5 lines per response\n"
            "- Use emoji sparingly for clarity\n"
            "- If asked to list repos, list the monitored repos above"
        )

    # ─── GitHub Models API fallback ───

    async def _chat_models_api(self, message: str,
                                on_delta: Optional[Callable] = None) -> dict:
        """Chat via GitHub Models API (OpenAI-compatible)."""
        token = self.config.github.token
        if not token:
            return {"answer": "No GitHub token configured."}

        if not self._history:
            self._history.append({"role": "system", "content": self._system_prompt()})

        self._history.append({"role": "user", "content": message})

        # Keep conversation compact (last 20 messages + system)
        if len(self._history) > 21:
            self._history = [self._history[0]] + self._history[-20:]

        model = getattr(self.config.copilot, "model", _DEFAULT_MODEL)
        # Map model names to GitHub Models catalog
        model_map = {"gpt-4.1": "gpt-4o", "gpt-4": "gpt-4o"}
        api_model = model_map.get(model, _DEFAULT_MODEL)

        payload = {
            "model": api_model,
            "messages": self._history,
            "max_tokens": 200,
            "temperature": 0.7,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    _MODELS_URL,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

            answer = data["choices"][0]["message"]["content"]
            self._history.append({"role": "assistant", "content": answer})

            if on_delta:
                on_delta(answer)

            return {"answer": answer}
        except httpx.HTTPStatusError as e:
            log.error("Models API HTTP error: %s %s", e.response.status_code,
                      e.response.text[:200])
            return {"answer": f"API error: {e.response.status_code}"}
        except Exception as e:
            log.error("Models API error: %s", e)
            return {"answer": f"Error: {e}"}

    # ─── Copilot SDK path ───

    async def _ensure_session(self):
        if not self._started:
            raise RuntimeError("AI service not started")
        if self._session is None:
            self._session = await self._client.create_session(self._build_sdk_config())
            log.info("Created Copilot SDK session")
        return self._session

    def _build_sdk_config(self) -> dict:
        from pydantic import BaseModel, Field
        from copilot import define_tool

        github_svc = self.github_service
        db = self.db
        cfg = self.config

        class FetchCILogsParams(BaseModel):
            repo: str = Field(description="Repository in owner/name format")
            run_id: int = Field(description="GitHub Actions workflow run ID")

        @define_tool(description="Fetch CI log output for a failed workflow run")
        async def fetch_ci_logs(params: FetchCILogsParams) -> dict:
            if github_svc:
                logs = await github_svc.get_workflow_run_logs(params.repo, params.run_id)
                return {"run_id": params.run_id, "logs": logs[-3000:]}
            return {"error": "GitHub service not available"}

        class GetActivityParams(BaseModel):
            repo: str = Field(description="Repository in owner/name format")
            hours: int = Field(default=16, description="Hours to look back")

        @define_tool(description="Get recent commits, PRs, and issues activity")
        async def get_repo_activity(params: GetActivityParams) -> dict:
            if github_svc:
                return await github_svc.get_recent_activity(params.repo, params.hours)
            return {"repo": params.repo, "hours": params.hours}

        class GetOpenPRsParams(BaseModel):
            repo: str = Field(default="", description="Optional repo filter")

        @define_tool(description="Get list of open pull requests from cache")
        async def get_open_prs(params: GetOpenPRsParams) -> list:
            if db:
                repos = [params.repo] if params.repo else (cfg.github.repos or None)
                return await db.get_pending_prs(repos)
            return []

        return {
            "model": self.config.copilot.model,
            "streaming": True,
            "tools": [fetch_ci_logs, get_repo_activity, get_open_prs],
            "system_message": {"content": self._system_prompt()},
        }

    async def _chat_sdk(self, message: str,
                         on_delta: Optional[Callable] = None) -> dict:
        from copilot.generated.session_events import SessionEventType

        session = await self._ensure_session()
        result_text = ""

        def on_event(event):
            nonlocal result_text
            if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
                delta = event.data.delta_content
                result_text += delta
                if on_delta:
                    on_delta(delta)
            elif event.type == SessionEventType.ASSISTANT_MESSAGE:
                result_text = event.data.content

        session.on(on_event)
        await session.send_and_wait({"prompt": message})
        return {"answer": result_text}

    # ─── Public API ───

    async def chat(self, message: str, on_delta: Optional[Callable] = None) -> dict:
        """Send a message and get a response."""
        if not self._started:
            return {"answer": "AI service not started."}

        if self._use_models_api:
            return await self._chat_models_api(message, on_delta)
        return await self._chat_sdk(message, on_delta)
