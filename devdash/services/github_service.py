"""GitHub API service — fetch PRs, CI runs, notifications with caching."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from github import Github, GithubException

from devdash.config import AppConfig
from devdash.database import Database

log = logging.getLogger(__name__)


class GitHubService:
    def __init__(self, config: AppConfig, db: Database):
        self.config = config
        self.db = db
        self._gh: Github | None = None

    @property
    def gh(self) -> Github:
        if self._gh is None:
            self._gh = Github(self.config.github.token)
        return self._gh

    async def poll_all(self):
        """Refresh all data from GitHub API and cache in SQLite."""
        for repo_name in self.config.github.repos:
            try:
                await self._poll_prs(repo_name)
                await self._poll_ci(repo_name)
            except GithubException as e:
                log.error("GitHub API error for %s: %s", repo_name, e)
            except Exception as e:
                log.error("Poll error for %s: %s", repo_name, e)

    async def _poll_prs(self, repo_name: str):
        repo = self.gh.get_repo(repo_name)
        prs = repo.get_pulls(state="open", sort="updated", direction="desc")
        if prs.totalCount == 0:
            return
        for pr in prs[:20]:  # Cap at 20
            await self.db.upsert_pr(
                repo=repo_name,
                number=pr.number,
                title=pr.title,
                author=pr.user.login,
                state=pr.state,
                ci_status=self._get_pr_ci_status(pr),
            )

    async def _poll_ci(self, repo_name: str):
        repo = self.gh.get_repo(repo_name)
        runs = repo.get_workflow_runs(status="completed")
        if runs.totalCount == 0:
            return
        for run in runs[:10]:
            if run.conclusion == "failure":
                await self.db.upsert_ci_run(
                    repo=repo_name,
                    run_id=run.id,
                    status=run.status,
                    conclusion=run.conclusion,
                    head_sha=run.head_sha,
                )

    def _get_pr_ci_status(self, pr) -> str:
        try:
            commits = list(pr.get_commits())
            if not commits:
                return "unknown"
            commit = commits[-1]
            statuses = commit.get_combined_status()
            return statuses.state  # success, failure, pending
        except Exception:
            return "unknown"

    # --- Direct API calls for Copilot agents ---

    async def get_workflow_run_logs(self, repo_name: str, run_id: int) -> str:
        """Fetch logs for a specific workflow run (used by CI diagnosis agent)."""
        repo = self.gh.get_repo(repo_name)
        run = repo.get_workflow_run(run_id)
        # Get failed job logs
        logs = []
        for job in run.jobs():
            if job.conclusion == "failure":
                # PyGithub doesn't support log download directly —
                # use the API URL pattern
                logs.append(f"Job: {job.name} — Status: {job.conclusion}")
                for step in job.steps:
                    if step.conclusion == "failure":
                        logs.append(f"  Step: {step.name} — FAILED")
        return "\n".join(logs) if logs else "No failed job logs found"

    async def get_pr_diff(self, repo_name: str, pr_number: int) -> str:
        """Fetch PR diff content."""
        repo = self.gh.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        files = pr.get_files()
        diff_parts = []
        for f in files[:20]:  # Limit files
            diff_parts.append(f"--- {f.filename} (+{f.additions}/-{f.deletions})")
            if f.patch:
                diff_parts.append(f.patch[:500])  # First 500 chars of patch
        return "\n".join(diff_parts)

    async def get_file_contents(self, repo_name: str, path: str, ref: str = "main") -> str:
        """Read a file from a repo."""
        repo = self.gh.get_repo(repo_name)
        content = repo.get_contents(path, ref=ref)
        return content.decoded_content.decode("utf-8")

    async def create_pr(self, repo_name: str, title: str, branch: str,
                        body: str, base: str = "main") -> dict:
        """Create a pull request."""
        repo = self.gh.get_repo(repo_name)
        pr = repo.create_pull(title=title, body=body, head=branch, base=base)
        return {"number": pr.number, "url": pr.html_url}

    async def submit_review(self, repo_name: str, pr_number: int,
                            event: str, body: str):
        """Submit a PR review (APPROVE or REQUEST_CHANGES)."""
        repo = self.gh.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        pr.create_review(body=body, event=event)

    async def get_recent_activity(self, repo_name: str, hours: int = 16) -> dict:
        """Get recent commits, PRs, and issues for standup generation."""
        repo = self.gh.get_repo(repo_name)
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        commits = [
            {"sha": c.sha[:7], "message": c.commit.message.split("\n")[0], "author": c.author.login if c.author else "unknown"}
            for c in repo.get_commits(since=since)[:20]
        ]

        merged_prs = [
            {"number": pr.number, "title": pr.title, "author": pr.user.login}
            for pr in repo.get_pulls(state="closed", sort="updated", direction="desc")[:10]
            if pr.merged and pr.merged_at and pr.merged_at > since
        ]

        return {"commits": commits, "merged_prs": merged_prs, "repo": repo_name}

    async def dispatch_workflow(self, repo_name: str, workflow: str, ref: str) -> dict:
        """Trigger a GitHub Actions workflow dispatch."""
        repo = self.gh.get_repo(repo_name)
        wf = repo.get_workflow(workflow)
        success = wf.create_dispatch(ref=ref)
        return {"triggered": success}

    async def get_ci_status(self, repo_name: str, sha: str) -> str:
        """Get combined CI status for a commit."""
        repo = self.gh.get_repo(repo_name)
        commit = repo.get_commit(sha)
        return commit.get_combined_status().state
