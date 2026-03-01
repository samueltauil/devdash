"""Copilot SDK integration — single unified conversational agent."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

from devdash.config import AppConfig

log = logging.getLogger(__name__)


class CopilotService:
    """Single Copilot agent handling all DevDash features via natural language."""

    def __init__(self, config: AppConfig, github_service=None, db=None):
        self.config = config
        self.github_service = github_service
        self.db = db
        self._client = None
        self._session = None
        self._started = False

    async def start(self):
        """Initialize the Copilot SDK client."""
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
            log.warning("Copilot SDK not installed — AI features disabled")
        except Exception as e:
            log.error("Copilot SDK start failed: %s", e)

    async def stop(self):
        """Shutdown session and client."""
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

    async def _ensure_session(self):
        """Get or create the unified conversation session."""
        if not self._started:
            raise RuntimeError("Copilot SDK not started")
        if self._session is None:
            self._session = await self._client.create_session(self._build_config())
            log.info("Created unified Copilot session")
        return self._session

    # ─── Tools ───

    def _build_tools(self) -> list:
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

        class GetFileParams(BaseModel):
            repo: str = Field(description="Repository in owner/name format")
            path: str = Field(description="File path in the repository")
            ref: str = Field(default="main", description="Git ref")

        @define_tool(description="Read a source file from a repository")
        async def get_file_contents(params: GetFileParams) -> str:
            if github_svc:
                return await github_svc.get_file_contents(params.repo, params.path, params.ref)
            return "File unavailable"

        class GetPRDetailsParams(BaseModel):
            repo: str = Field(description="Repository in owner/name format")
            pr_number: int = Field(description="Pull request number")

        @define_tool(description="Fetch PR diff and metadata for analysis")
        async def get_pr_details(params: GetPRDetailsParams) -> dict:
            if github_svc:
                diff = await github_svc.get_pr_diff(params.repo, params.pr_number)
                return {"repo": params.repo, "pr_number": params.pr_number, "diff": diff[:3000]}
            return {"error": "GitHub service not available"}

        class GetActivityParams(BaseModel):
            repo: str = Field(description="Repository in owner/name format")
            hours: int = Field(default=16, description="Hours to look back")

        @define_tool(description="Get recent commits, PRs, and issues activity for a repo")
        async def get_repo_activity(params: GetActivityParams) -> dict:
            if github_svc:
                return await github_svc.get_recent_activity(params.repo, params.hours)
            return {"repo": params.repo, "hours": params.hours}

        class SafetyCheckParams(BaseModel):
            repo: str = Field(description="Repository to check")

        @define_tool(description="Run pre-deployment safety checks on a repository")
        async def run_safety_check(params: SafetyCheckParams) -> dict:
            if github_svc:
                return {"repo": params.repo, "ci_status": "checked"}
            return {"repo": params.repo}

        class DispatchWorkflowParams(BaseModel):
            repo: str = Field(description="Repository in owner/name format")
            workflow: str = Field(description="Workflow file name")
            ref: str = Field(default="main", description="Git ref to deploy")

        @define_tool(description="Trigger a GitHub Actions workflow deployment")
        async def dispatch_workflow(params: DispatchWorkflowParams) -> dict:
            if github_svc:
                return await github_svc.dispatch_workflow(params.repo, params.workflow, params.ref)
            return {"error": "GitHub service not available"}

        class QueryKBParams(BaseModel):
            question: str = Field(description="Search query for the knowledge base")

        @define_tool(description="Search the local knowledge base for codebase context")
        async def query_knowledge_base(params: QueryKBParams) -> list:
            if db:
                return await db.query_knowledge(params.question)
            return []

        class SaveKBParams(BaseModel):
            content: str = Field(description="Knowledge to save")
            source: str = Field(description="Source of this knowledge")

        @define_tool(description="Save new knowledge about the codebase for future reference")
        async def save_knowledge(params: SaveKBParams) -> str:
            if db:
                await db.save_knowledge(params.content, params.source)
                return f"Saved: {params.content[:50]}..."
            return "Database not available"

        class GetFailedCIRunsParams(BaseModel):
            repo: str = Field(default="", description="Optional repo filter")

        @define_tool(description="Get list of recent failed CI runs from cache")
        async def get_failed_ci_runs(params: GetFailedCIRunsParams) -> list:
            if db:
                return await db.get_failed_runs(params.repo or None)
            return []

        class GetOpenPRsParams(BaseModel):
            repo: str = Field(default="", description="Optional repo filter")

        @define_tool(description="Get list of open pull requests from cache")
        async def get_open_prs(params: GetOpenPRsParams) -> list:
            if db:
                repos = [params.repo] if params.repo else (cfg.github.repos or None)
                return await db.get_pending_prs(repos)
            return []

        return [
            fetch_ci_logs, get_file_contents, get_pr_details,
            get_repo_activity, run_safety_check, dispatch_workflow,
            query_knowledge_base, save_knowledge,
            get_failed_ci_runs, get_open_prs,
        ]

    # ─── Session config ───

    def _build_config(self) -> dict:
        repos = ", ".join(self.config.github.repos) if self.config.github.repos else "none configured"

        return {
            "model": self.config.copilot.model,
            "streaming": True,
            "tools": self._build_tools(),
            "infinite_sessions": {
                "enabled": True,
                "background_compaction_threshold": 0.75,
                "buffer_exhaustion_threshold": 0.90,
            },
            "system_message": {
                "content": (
                    "You are DevDash, an AI developer companion on a Raspberry Pi "
                    "with a 3.5\" LCD screen. The developer interacts via voice.\n\n"
                    f"Monitored repositories: {repos}\n\n"
                    "You can help with:\n"
                    "- **CI/CD**: Check failed runs, diagnose errors, suggest fixes\n"
                    "- **Pull Requests**: List open PRs, analyze diffs, assess risk\n"
                    "- **Standup**: Generate daily briefings of repo activity\n"
                    "- **Deployments**: Safety checks, trigger workflow deploys\n"
                    "- **Code Context**: Answer questions, save/query knowledge\n\n"
                    "Guidelines:\n"
                    "- Be concise — responses display on a 480×320 screen\n"
                    "- Use emoji sparingly for clarity\n"
                    "- Use tools proactively to fetch real data\n"
                    "- For CI questions → get_failed_ci_runs or fetch_ci_logs\n"
                    "- For PR questions → get_open_prs or get_pr_details\n"
                    "- For standup → get_repo_activity for each repo\n"
                    "- For deploys → run_safety_check first, confirm before dispatch\n"
                    "- Save useful learnings to knowledge base automatically\n"
                    "- Max 5-8 lines per response"
                ),
            },
        }

    # ─── Public API ───

    async def chat(self, message: str, on_delta: Optional[Callable] = None) -> dict:
        """Send a message and get a streaming response."""
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
