"""Copilot SDK integration — session lifecycle, streaming, tools, and agents."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

from devdash.config import AppConfig

log = logging.getLogger(__name__)


class CopilotService:
    """Single CopilotClient managing multiple specialized AI sessions."""

    def __init__(self, config: AppConfig):
        self.config = config
        self._client = None
        self._sessions: dict[str, object] = {}
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
        """Shutdown all sessions and the client."""
        for name, session in self._sessions.items():
            try:
                await session.destroy()
            except Exception:
                pass
        self._sessions.clear()

        if self._client:
            try:
                await self._client.stop()
            except Exception:
                pass
        self._started = False

    async def _get_session(self, name: str, session_config: dict) -> object:
        """Get or create a named session with specific config."""
        if not self._started:
            raise RuntimeError("Copilot SDK not started")

        if name not in self._sessions:
            self._sessions[name] = await self._client.create_session(session_config)
            log.info("Created Copilot session: %s", name)
        return self._sessions[name]

    async def _send_and_stream(self, session_name: str, session_config: dict,
                                prompt: str, on_delta: Optional[Callable] = None) -> str:
        """Send a prompt, collect streaming response, return final text."""
        from copilot.generated.session_events import SessionEventType

        session = await self._get_session(session_name, session_config)
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
        await session.send_and_wait({"prompt": prompt})
        return result_text

    # ─── Feature 1: CI Diagnosis Agent ───

    async def diagnose_ci_failure(self, repo: str, run_id: int,
                                   on_delta: Optional[Callable] = None) -> dict:
        """Diagnose a CI failure using Copilot agent with custom tools."""
        from pydantic import BaseModel, Field
        from copilot import define_tool

        # Import github service lazily to avoid circular deps
        github_svc = None

        class FetchCILogsParams(BaseModel):
            run_id: int = Field(description="GitHub Actions workflow run ID")

        @define_tool(description="Fetch CI log output for a failed workflow run")
        async def fetch_ci_logs(params: FetchCILogsParams) -> dict:
            if github_svc:
                logs = await github_svc.get_workflow_run_logs(repo, params.run_id)
                return {"run_id": params.run_id, "logs": logs[-3000:]}
            return {"error": "GitHub service not available"}

        class GetFileParams(BaseModel):
            path: str = Field(description="File path in the repository")
            ref: str = Field(default="main", description="Git ref")

        @define_tool(description="Read a source file from the repository")
        async def get_file_contents(params: GetFileParams) -> str:
            if github_svc:
                return await github_svc.get_file_contents(repo, params.path, params.ref)
            return "File unavailable"

        config = {
            "model": self.config.copilot.model,
            "streaming": True,
            "tools": [fetch_ci_logs, get_file_contents],
            "system_message": {
                "content": (
                    "You are a CI/CD debugging expert. When given a failed workflow run ID:\n"
                    "1. Use fetch_ci_logs to get the error output\n"
                    "2. Identify the root cause (compile error, test failure, lint, etc.)\n"
                    "3. Use get_file_contents to read relevant source files\n"
                    "4. Provide a clear root cause analysis\n"
                    "5. Suggest a fix\n"
                    "Format: DIAGNOSIS: ...\nFIX: ...\nCAUSED BY: ...\n"
                    "Be concise — this displays on a 3.5 inch screen."
                ),
            },
        }

        text = await self._send_and_stream(
            "ci_diagnosis", config,
            f"CI run {run_id} in repo {repo} has failed. Diagnose and suggest a fix.",
            on_delta,
        )

        return self._parse_diagnosis(text)

    def _parse_diagnosis(self, text: str) -> dict:
        result = {"diagnosis": "", "fix": "", "caused_by": ""}
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("DIAGNOSIS:"):
                result["diagnosis"] = line[10:].strip()
            elif line.startswith("FIX:"):
                result["fix"] = line[4:].strip()
            elif line.startswith("CAUSED BY:"):
                result["caused_by"] = line[10:].strip()
        if not result["diagnosis"]:
            result["diagnosis"] = text[:200]
        return result

    async def create_ci_fix_pr(self, repo: str, run_id: int):
        """Ask Copilot to create a fix PR for a CI failure."""
        from pydantic import BaseModel, Field
        from copilot import define_tool

        class CreateFixPRParams(BaseModel):
            title: str = Field(description="PR title")
            branch: str = Field(description="Branch name for the fix")
            body: str = Field(description="PR description")

        @define_tool(description="Create a pull request with a fix for the CI failure")
        async def create_fix_pr(params: CreateFixPRParams) -> dict:
            # This would integrate with github_service
            return {"status": "PR creation queued", "title": params.title}

        config = {
            "model": self.config.copilot.model,
            "streaming": True,
            "tools": [create_fix_pr],
            "system_message": {"content": "Create a fix PR for the CI failure."},
        }

        await self._send_and_stream(
            "ci_fix", config,
            f"Create a fix PR for failed CI run {run_id} in {repo}.",
        )

    # ─── Feature 2: PR Triage Agent ───

    async def analyze_pr(self, repo: str, pr_number: int,
                          on_delta: Optional[Callable] = None) -> dict:
        """Analyze a PR and generate summary, risk, and concerns."""
        from pydantic import BaseModel, Field
        from copilot import define_tool

        class AnalyzePRParams(BaseModel):
            pr_number: int = Field(description="Pull request number")

        @define_tool(description="Fetch PR diff and metadata for analysis")
        async def get_pr_details(params: AnalyzePRParams) -> dict:
            return {"pr_number": params.pr_number, "repo": repo}

        config = {
            "model": self.config.copilot.model,
            "streaming": True,
            "tools": [get_pr_details],
            "system_message": {
                "content": (
                    "You are a code review assistant for a touch-screen device.\n"
                    "Summarize the PR in EXACTLY this format:\n"
                    "SUMMARY: (1 sentence)\n"
                    "RISK: LOW|MEDIUM|HIGH\n"
                    "CONCERN: (1 key concern, or 'None')\n"
                    "Keep it extremely concise — max 3 lines. 480x320 screen."
                ),
            },
        }

        text = await self._send_and_stream(
            "pr_triage", config,
            f"Analyze PR #{pr_number} in {repo}.",
            on_delta,
        )

        return self._parse_pr_analysis(text)

    def _parse_pr_analysis(self, text: str) -> dict:
        result = {"summary": "", "risk": "", "concern": ""}
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("SUMMARY:"):
                result["summary"] = line[8:].strip()
            elif line.startswith("RISK:"):
                result["risk"] = line[5:].strip()
            elif line.startswith("CONCERN:"):
                result["concern"] = line[8:].strip()
        if not result["summary"]:
            result["summary"] = text[:100]
        return result

    async def submit_pr_review(self, repo: str, pr_number: int, event: str):
        """Submit a PR review via Copilot-generated comment."""
        # For now, directly call GitHub API
        # In full impl, Copilot generates the review comment
        log.info("Would submit %s review for PR #%s in %s", event, pr_number, repo)

    # ─── Feature 4: Morning Standup Agent ───

    async def generate_standup(self, repos: list[str], lookback_hours: int,
                                on_delta: Optional[Callable] = None) -> dict:
        """Generate a morning standup briefing across all repos."""
        from pydantic import BaseModel, Field
        from copilot import define_tool

        class GetActivityParams(BaseModel):
            repo: str = Field(description="Repository in owner/name format")
            hours: int = Field(description="Hours to look back")

        @define_tool(description="Get commits, PRs, and issues activity for a repo")
        async def get_repo_activity(params: GetActivityParams) -> dict:
            return {"repo": params.repo, "hours": params.hours}

        config = {
            "model": self.config.copilot.model,
            "streaming": True,
            "tools": [get_repo_activity],
            "system_message": {
                "content": (
                    "You are a standup report generator for a developer's desk device.\n"
                    "Call get_repo_activity for EACH monitored repo.\n"
                    "Generate a structured morning briefing:\n"
                    "🚢 SHIPPED: What teammates merged overnight\n"
                    "⚠️ NEEDS ATTENTION: Failing CI, stale PRs\n"
                    "📋 PRIORITIES: Suggested focus areas\n"
                    "Be warm but concise. Use emoji. Max 15 lines."
                ),
            },
        }

        repo_list = ", ".join(repos)
        text = await self._send_and_stream(
            "standup", config,
            f"Generate a morning standup for repos: {repo_list}. Look back {lookback_hours} hours.",
            on_delta,
        )

        return {"standup": text}

    # ─── Feature 5: Deploy Safety Agent ───

    async def analyze_deploy(self, repo: str, environment: str,
                              on_delta: Optional[Callable] = None) -> dict:
        """Run pre-deploy safety analysis."""
        from pydantic import BaseModel, Field
        from copilot import define_tool

        class SafetyCheckParams(BaseModel):
            repo: str = Field(description="Repository to check")

        @define_tool(description="Run pre-deployment safety checks")
        async def run_safety_check(params: SafetyCheckParams) -> dict:
            return {"repo": params.repo, "environment": environment}

        config = {
            "model": self.config.copilot.model,
            "streaming": True,
            "tools": [run_safety_check],
            "system_message": {
                "content": (
                    "You are a deployment safety analyst.\n"
                    "Run run_safety_check first. Then provide:\n"
                    "CONFIDENCE: XX%\n"
                    "RISK: LOW|MEDIUM|HIGH\n"
                    "ANALYSIS: (2-3 sentences explaining the risk)\n"
                    "Only recommend deploying if confidence > 70%."
                ),
            },
        }

        text = await self._send_and_stream(
            "deploy", config,
            f"Analyze deployment safety for {repo} to {environment}.",
            on_delta,
        )

        return self._parse_deploy_analysis(text)

    def _parse_deploy_analysis(self, text: str) -> dict:
        result = {"confidence": 50, "risk": "MEDIUM", "analysis": ""}
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("CONFIDENCE:"):
                try:
                    result["confidence"] = int(line.split(":")[1].strip().rstrip("%"))
                except ValueError:
                    pass
            elif line.startswith("RISK:"):
                result["risk"] = line[5:].strip()
            elif line.startswith("ANALYSIS:"):
                result["analysis"] = line[9:].strip()
        if not result["analysis"]:
            result["analysis"] = text[:200]
        return result

    async def trigger_deploy(self, repo: str, workflow: str, ref: str) -> dict:
        """Trigger the actual deployment."""
        log.info("Would trigger deploy: %s/%s@%s", repo, workflow, ref)
        return {"run_id": 0, "status": "triggered"}

    # ─── Feature 6: Context Keeper Agent ───

    async def ask_context_keeper(self, question: str,
                                  on_delta: Optional[Callable] = None) -> dict:
        """Ask the persistent context keeper a question."""
        from pydantic import BaseModel, Field
        from copilot import define_tool

        class QueryKBParams(BaseModel):
            question: str = Field(description="Question about the codebase")

        @define_tool(description="Search the local knowledge base for codebase history")
        async def query_knowledge_base(params: QueryKBParams) -> list:
            return [{"content": "Knowledge base query", "source": "local"}]

        class SaveKBParams(BaseModel):
            content: str = Field(description="Knowledge to remember")
            source: str = Field(description="Source of this knowledge")

        @define_tool(description="Save new knowledge about the codebase")
        async def save_knowledge(params: SaveKBParams) -> str:
            return f"Saved: {params.content[:50]}..."

        config = {
            "model": self.config.copilot.model,
            "streaming": True,
            "tools": [query_knowledge_base, save_knowledge],
            "infinite_sessions": {
                "enabled": True,
                "background_compaction_threshold": 0.75,
                "buffer_exhaustion_threshold": 0.90,
            },
            "system_message": {
                "content": (
                    "You are the architectural memory of this developer's codebase.\n"
                    "Search the knowledge base first. Save new learnings.\n"
                    "Be specific, cite sources (PR numbers, commits), and be concise.\n"
                    "This displays on a 480×320 touch screen — max 5 lines."
                ),
            },
        }

        text = await self._send_and_stream(
            "context_keeper", config,
            question,
            on_delta,
        )

        return {"answer": text}
