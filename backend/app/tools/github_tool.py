"""GitHub tool executor via GitHub REST API."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.tools.base import ToolExecutor, ToolResult

log = get_logger("tools.github")

GITHUB_API = "https://api.github.com"

# All tool_ids this executor handles
GITHUB_TOOL_IDS = {
    "github_create_issue",
    "github_update_issue",
    "github_close_issue",
    "github_comment_on_issue",
    "github_create_pr",
    "github_merge_pr",
    "github_get_pr_diff",
    "github_comment_on_pr",
    "github_list_open_prs",
    "github_get_file_contents",
    "github_update_file",
    "github_search_code",
    "github_create_branch",
    "github_trigger_workflow",
    "github_get_workflow_run",
    "github_get_workflow_logs",
    "github_rerun_failed_jobs",
    "github_cancel_workflow_run",
    "github_create_release",
    "github_list_dependabot_alerts",
    "github_dismiss_alert",
    "github_lookup_user",
    "github_get_codeowners",
    # legacy IDs kept for back-compat
    "create_github_issue",
    "close_github_issue",
}


# region agent log
def _debug_log(run_id: str, hypothesis_id: str, location: str, message: str, data: dict) -> None:
    try:
        payload = {
            "sessionId": "caa63e",
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with open("debug-caa63e.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
# endregion


class GitHubToolExecutor(ToolExecutor):
    """Executes GitHub REST API operations on behalf of authenticated users."""

    async def execute(
        self,
        args: dict[str, Any],
        *,
        idempotency_key: str,
        simulate: bool = False,
    ) -> ToolResult:
        s = get_settings()
        # _action is injected by the pipeline runner to tell us which tool_id fired
        action = args.get("_action", "github_create_issue")
        # region agent log
        _debug_log(
            idempotency_key,
            "H5",
            "github_tool.py:GitHubToolExecutor.execute",
            "github execute entry",
            {
                "action": action,
                "args_keys": sorted(list(args.keys())),
                "simulate": bool(simulate or args.get("simulate")),
                "has_repo": bool(args.get("repo")),
            },
        )
        # endregion

        if simulate or args.get("simulate"):
            log.info("github_simulate", action=action, repo=args.get("repo"))
            return ToolResult.ok(
                action,
                {"simulated": True, "repo": args.get("repo"), "action": action},
                simulated=True,
                idempotency_key=idempotency_key,
            )

        if not s.github_token:
            return ToolResult.fail(
                action,
                code="TOOL_CONFIG_ERROR",
                message="GITHUB_TOKEN is not configured",
                retryable=False,
                user_facing=True,
                idempotency_key=idempotency_key,
            )

        headers = {
            "Authorization": f"Bearer {s.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        repo = args.get("repo", "")
        timeout = s.tool_github_timeout

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                return await self._dispatch(action, args, repo, headers, client, timeout, idempotency_key)
        except (httpx.TimeoutException, asyncio.TimeoutError):
            return ToolResult.fail(
                action,
                code="TOOL_TIMEOUT",
                message="GitHub API timed out",
                retryable=True,
                user_facing=True,
                idempotency_key=idempotency_key,
            )

    # ── dispatch ──────────────────────────────────────────────────────────────

    async def _dispatch(
        self,
        action: str,
        args: dict[str, Any],
        repo: str,
        headers: dict[str, str],
        client: httpx.AsyncClient,
        timeout: float,
        idempotency_key: str,
    ) -> ToolResult:
        # Issues
        if action in ("create_github_issue", "github_create_issue"):
            return await self._create_issue(args, repo, headers, client, timeout, idempotency_key)
        if action == "github_update_issue":
            return await self._update_issue(args, repo, headers, client, timeout, idempotency_key)
        if action in ("close_github_issue", "github_close_issue"):
            return await self._close_issue(args, repo, headers, client, timeout, idempotency_key)
        if action == "github_comment_on_issue":
            return await self._comment_on_issue(args, repo, headers, client, timeout, idempotency_key)
        # PRs
        if action == "github_create_pr":
            return await self._create_pr(args, repo, headers, client, timeout, idempotency_key)
        if action == "github_merge_pr":
            return await self._merge_pr(args, repo, headers, client, timeout, idempotency_key)
        if action == "github_get_pr_diff":
            return await self._get_pr_diff(args, repo, headers, client, timeout, idempotency_key)
        if action == "github_comment_on_pr":
            return await self._comment_on_pr(args, repo, headers, client, timeout, idempotency_key)
        if action == "github_list_open_prs":
            return await self._list_open_prs(args, repo, headers, client, timeout, idempotency_key)
        # Files / code
        if action == "github_get_file_contents":
            return await self._get_file_contents(args, repo, headers, client, timeout, idempotency_key)
        if action == "github_update_file":
            return await self._update_file(args, repo, headers, client, timeout, idempotency_key)
        if action == "github_search_code":
            return await self._search_code(args, headers, client, timeout, idempotency_key)
        if action == "github_create_branch":
            return await self._create_branch(args, repo, headers, client, timeout, idempotency_key)
        # Workflows
        if action == "github_trigger_workflow":
            return await self._trigger_workflow(args, repo, headers, client, timeout, idempotency_key)
        if action == "github_get_workflow_run":
            return await self._get_workflow_run(args, repo, headers, client, timeout, idempotency_key)
        if action == "github_get_workflow_logs":
            return await self._get_workflow_logs(args, repo, headers, client, timeout, idempotency_key)
        if action == "github_rerun_failed_jobs":
            return await self._rerun_failed_jobs(args, repo, headers, client, timeout, idempotency_key)
        if action == "github_cancel_workflow_run":
            return await self._cancel_workflow_run(args, repo, headers, client, timeout, idempotency_key)
        # Releases
        if action == "github_create_release":
            return await self._create_release(args, repo, headers, client, timeout, idempotency_key)
        # Security
        if action == "github_list_dependabot_alerts":
            return await self._list_dependabot_alerts(args, repo, headers, client, timeout, idempotency_key)
        if action == "github_dismiss_alert":
            return await self._dismiss_alert(args, repo, headers, client, timeout, idempotency_key)
        # Users / metadata
        if action == "github_lookup_user":
            return await self._lookup_user(args, headers, client, timeout, idempotency_key)
        if action == "github_get_codeowners":
            return await self._get_codeowners(args, repo, headers, client, timeout, idempotency_key)

        return ToolResult.fail(
            action,
            code="TOOL_UNKNOWN_ACTION",
            message=f"Unknown GitHub action: {action}",
            retryable=False,
            user_facing=True,
            idempotency_key=idempotency_key,
        )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _ok(self, action: str, data: dict, idempotency_key: str) -> ToolResult:
        log.info("github_ok", action=action)
        return ToolResult.ok(action, data, idempotency_key=idempotency_key)

    def _http_fail(self, action: str, resp: httpx.Response, idempotency_key: str) -> ToolResult:
        return ToolResult.fail(
            action,
            code=f"GITHUB_HTTP_{resp.status_code}",
            message=resp.text[:500],
            retryable=resp.status_code >= 500,
            user_facing=True,
            idempotency_key=idempotency_key,
        )

    # ── issue actions ─────────────────────────────────────────────────────────

    async def _create_issue(self, args, repo, headers, client, timeout, ik) -> ToolResult:
        payload: dict[str, Any] = {"title": args["title"], "body": args.get("body", "")}
        if args.get("labels"):
            payload["labels"] = args["labels"]
        if args.get("assignees"):
            payload["assignees"] = args["assignees"]
        if args.get("milestone"):
            payload["milestone"] = args["milestone"]
        resp = await asyncio.wait_for(
            client.post(f"{GITHUB_API}/repos/{repo}/issues", json=payload, headers=headers),
            timeout=timeout,
        )
        if resp.status_code == 201:
            d = resp.json()
            return self._ok("github_create_issue", {"number": d["number"], "html_url": d["html_url"]}, ik)
        return self._http_fail("github_create_issue", resp, ik)

    async def _update_issue(self, args, repo, headers, client, timeout, ik) -> ToolResult:
        num = args["issue_number"]
        payload = {k: args[k] for k in ("title", "body", "state", "labels", "assignees") if k in args}
        resp = await asyncio.wait_for(
            client.patch(f"{GITHUB_API}/repos/{repo}/issues/{num}", json=payload, headers=headers),
            timeout=timeout,
        )
        if resp.status_code == 200:
            d = resp.json()
            return self._ok("github_update_issue", {"number": d["number"], "html_url": d["html_url"]}, ik)
        return self._http_fail("github_update_issue", resp, ik)

    async def _close_issue(self, args, repo, headers, client, timeout, ik) -> ToolResult:
        num = args["issue_number"]
        payload: dict[str, Any] = {"state": "closed"}
        if args.get("state_reason"):
            payload["state_reason"] = args["state_reason"]
        resp = await asyncio.wait_for(
            client.patch(f"{GITHUB_API}/repos/{repo}/issues/{num}", json=payload, headers=headers),
            timeout=timeout,
        )
        if resp.status_code == 200 and args.get("comment"):
            await client.post(
                f"{GITHUB_API}/repos/{repo}/issues/{num}/comments",
                json={"body": args["comment"]},
                headers=headers,
            )
        if resp.status_code == 200:
            d = resp.json()
            return self._ok("github_close_issue", {"number": d["number"], "state": d["state"]}, ik)
        return self._http_fail("github_close_issue", resp, ik)

    async def _comment_on_issue(self, args, repo, headers, client, timeout, ik) -> ToolResult:
        num = args["issue_number"]
        resp = await asyncio.wait_for(
            client.post(
                f"{GITHUB_API}/repos/{repo}/issues/{num}/comments",
                json={"body": args["body"]},
                headers=headers,
            ),
            timeout=timeout,
        )
        if resp.status_code == 201:
            d = resp.json()
            return self._ok("github_comment_on_issue", {"comment_id": d["id"], "html_url": d["html_url"]}, ik)
        return self._http_fail("github_comment_on_issue", resp, ik)

    # ── PR actions ────────────────────────────────────────────────────────────

    async def _create_pr(self, args, repo, headers, client, timeout, ik) -> ToolResult:
        # region agent log
        _debug_log(
            ik,
            "H5",
            "github_tool.py:_create_pr",
            "github create_pr required fields snapshot",
            {
                "repo_present": bool(repo),
                "has_title": bool(isinstance(args.get("title"), str) and args.get("title", "").strip()),
                "has_base": bool(isinstance(args.get("base"), str) and args.get("base", "").strip()),
                "has_head": bool(isinstance(args.get("head"), str) and args.get("head", "").strip()),
                "body_len": len(args.get("body", "")) if isinstance(args.get("body"), str) else 0,
            },
        )
        # endregion
        payload: dict[str, Any] = {
            "title": args["title"],
            "body": args.get("body", ""),
            "base": args["base"],
            "head": args["head"],
            "draft": args.get("draft", True),
        }
        if args.get("reviewers"):
            payload["reviewers"] = args["reviewers"]
        if args.get("labels"):
            payload["labels"] = args["labels"]
        resp = await asyncio.wait_for(
            client.post(f"{GITHUB_API}/repos/{repo}/pulls", json=payload, headers=headers),
            timeout=timeout,
        )
        if resp.status_code == 201:
            d = resp.json()
            return self._ok("github_create_pr", {"pr_number": d["number"], "html_url": d["html_url"], "draft": d.get("draft")}, ik)
        return self._http_fail("github_create_pr", resp, ik)

    async def _merge_pr(self, args, repo, headers, client, timeout, ik) -> ToolResult:
        num = args["pr_number"]
        payload: dict[str, Any] = {"merge_method": args.get("merge_method", "squash")}
        if args.get("commit_title"):
            payload["commit_title"] = args["commit_title"]
        if args.get("commit_message"):
            payload["commit_message"] = args["commit_message"]
        resp = await asyncio.wait_for(
            client.put(f"{GITHUB_API}/repos/{repo}/pulls/{num}/merge", json=payload, headers=headers),
            timeout=timeout,
        )
        if resp.status_code == 200:
            d = resp.json()
            return self._ok("github_merge_pr", {"sha": d.get("sha"), "merged": d.get("merged"), "message": d.get("message")}, ik)
        return self._http_fail("github_merge_pr", resp, ik)

    async def _get_pr_diff(self, args, repo, headers, client, timeout, ik) -> ToolResult:
        num = args["pr_number"]
        diff_headers = {**headers, "Accept": "application/vnd.github.v3.diff"}
        resp = await asyncio.wait_for(
            client.get(f"{GITHUB_API}/repos/{repo}/pulls/{num}", headers=diff_headers),
            timeout=timeout,
        )
        if resp.status_code == 200:
            return self._ok("github_get_pr_diff", {"diff": resp.text[:50000]}, ik)
        return self._http_fail("github_get_pr_diff", resp, ik)

    async def _comment_on_pr(self, args, repo, headers, client, timeout, ik) -> ToolResult:
        num = args["pr_number"]
        resp = await asyncio.wait_for(
            client.post(
                f"{GITHUB_API}/repos/{repo}/issues/{num}/comments",
                json={"body": args["body"]},
                headers=headers,
            ),
            timeout=timeout,
        )
        if resp.status_code == 201:
            d = resp.json()
            return self._ok("github_comment_on_pr", {"comment_id": d["id"], "html_url": d["html_url"]}, ik)
        return self._http_fail("github_comment_on_pr", resp, ik)

    async def _list_open_prs(self, args, repo, headers, client, timeout, ik) -> ToolResult:
        params: dict[str, str] = {"state": "open", "per_page": "30"}
        if args.get("author"):
            params["head"] = args["author"]
        if args.get("label"):
            params["labels"] = args["label"]
        resp = await asyncio.wait_for(
            client.get(f"{GITHUB_API}/repos/{repo}/pulls", params=params, headers=headers),
            timeout=timeout,
        )
        if resp.status_code == 200:
            prs = [{"number": p["number"], "title": p["title"], "html_url": p["html_url"], "draft": p.get("draft")} for p in resp.json()]
            return self._ok("github_list_open_prs", {"prs": prs, "count": len(prs)}, ik)
        return self._http_fail("github_list_open_prs", resp, ik)

    # ── file / code actions ───────────────────────────────────────────────────

    async def _get_file_contents(self, args, repo, headers, client, timeout, ik) -> ToolResult:
        path = args["path"]
        ref = args.get("ref", "HEAD")
        resp = await asyncio.wait_for(
            client.get(f"{GITHUB_API}/repos/{repo}/contents/{path}", params={"ref": ref}, headers=headers),
            timeout=timeout,
        )
        if resp.status_code == 200:
            d = resp.json()
            import base64
            content = base64.b64decode(d.get("content", "")).decode("utf-8", errors="replace") if d.get("encoding") == "base64" else d.get("content", "")
            return self._ok("github_get_file_contents", {"path": d["path"], "sha": d["sha"], "content": content[:50000]}, ik)
        return self._http_fail("github_get_file_contents", resp, ik)

    async def _update_file(self, args, repo, headers, client, timeout, ik) -> ToolResult:
        import base64
        path = args["path"]
        payload: dict[str, Any] = {
            "message": args["commit_message"],
            "content": base64.b64encode(args["content"].encode()).decode(),
            "branch": args["branch"],
        }
        if args.get("sha"):
            payload["sha"] = args["sha"]
        resp = await asyncio.wait_for(
            client.put(f"{GITHUB_API}/repos/{repo}/contents/{path}", json=payload, headers=headers),
            timeout=timeout,
        )
        if resp.status_code in (200, 201):
            d = resp.json()
            return self._ok("github_update_file", {"path": path, "sha": d["content"]["sha"], "html_url": d["content"].get("html_url")}, ik)
        return self._http_fail("github_update_file", resp, ik)

    async def _search_code(self, args, headers, client, timeout, ik) -> ToolResult:
        q = args["query"]
        if args.get("repo"):
            q += f" repo:{args['repo']}"
        if args.get("language"):
            q += f" language:{args['language']}"
        resp = await asyncio.wait_for(
            client.get(f"{GITHUB_API}/search/code", params={"q": q, "per_page": "10"}, headers=headers),
            timeout=timeout,
        )
        if resp.status_code == 200:
            items = [{"path": i["path"], "repo": i["repository"]["full_name"], "html_url": i["html_url"]} for i in resp.json().get("items", [])]
            return self._ok("github_search_code", {"items": items, "total_count": resp.json().get("total_count", 0)}, ik)
        return self._http_fail("github_search_code", resp, ik)

    async def _create_branch(self, args, repo, headers, client, timeout, ik) -> ToolResult:
        from_ref = args.get("from_ref", "HEAD")
        # Resolve from_ref to a SHA
        ref_resp = await asyncio.wait_for(
            client.get(f"{GITHUB_API}/repos/{repo}/git/ref/heads/{from_ref}", headers=headers),
            timeout=timeout,
        )
        if ref_resp.status_code != 200:
            # Try as a commit SHA directly
            sha = from_ref
        else:
            sha = ref_resp.json()["object"]["sha"]
        resp = await asyncio.wait_for(
            client.post(
                f"{GITHUB_API}/repos/{repo}/git/refs",
                json={"ref": f"refs/heads/{args['branch']}", "sha": sha},
                headers=headers,
            ),
            timeout=timeout,
        )
        if resp.status_code == 201:
            d = resp.json()
            return self._ok("github_create_branch", {"branch": args["branch"], "sha": d["object"]["sha"]}, ik)
        return self._http_fail("github_create_branch", resp, ik)

    # ── workflow actions ──────────────────────────────────────────────────────

    async def _trigger_workflow(self, args, repo, headers, client, timeout, ik) -> ToolResult:
        workflow = args["workflow"]
        payload: dict[str, Any] = {"ref": args["ref"]}
        if args.get("inputs"):
            payload["inputs"] = args["inputs"]
        resp = await asyncio.wait_for(
            client.post(
                f"{GITHUB_API}/repos/{repo}/actions/workflows/{workflow}/dispatches",
                json=payload,
                headers=headers,
            ),
            timeout=timeout,
        )
        if resp.status_code == 204:
            return self._ok("github_trigger_workflow", {"workflow": workflow, "ref": args["ref"], "dispatched": True}, ik)
        return self._http_fail("github_trigger_workflow", resp, ik)

    async def _get_workflow_run(self, args, repo, headers, client, timeout, ik) -> ToolResult:
        run_id = args["run_id"]
        resp = await asyncio.wait_for(
            client.get(f"{GITHUB_API}/repos/{repo}/actions/runs/{run_id}", headers=headers),
            timeout=timeout,
        )
        if resp.status_code == 200:
            d = resp.json()
            return self._ok("github_get_workflow_run", {
                "run_id": d["id"], "status": d["status"], "conclusion": d.get("conclusion"),
                "name": d["name"], "html_url": d["html_url"],
            }, ik)
        return self._http_fail("github_get_workflow_run", resp, ik)

    async def _get_workflow_logs(self, args, repo, headers, client, timeout, ik) -> ToolResult:
        run_id = args["run_id"]
        resp = await asyncio.wait_for(
            client.get(
                f"{GITHUB_API}/repos/{repo}/actions/runs/{run_id}/logs",
                headers=headers,
                follow_redirects=True,
            ),
            timeout=timeout,
        )
        if resp.status_code == 200:
            return self._ok("github_get_workflow_logs", {"run_id": run_id, "logs": resp.text[:50000]}, ik)
        return self._http_fail("github_get_workflow_logs", resp, ik)

    async def _rerun_failed_jobs(self, args, repo, headers, client, timeout, ik) -> ToolResult:
        run_id = args["run_id"]
        resp = await asyncio.wait_for(
            client.post(f"{GITHUB_API}/repos/{repo}/actions/runs/{run_id}/rerun-failed-jobs", headers=headers, content=b""),
            timeout=timeout,
        )
        if resp.status_code in (200, 201):
            return self._ok("github_rerun_failed_jobs", {"run_id": run_id, "rerun_requested": True}, ik)
        return self._http_fail("github_rerun_failed_jobs", resp, ik)

    async def _cancel_workflow_run(self, args, repo, headers, client, timeout, ik) -> ToolResult:
        run_id = args["run_id"]
        resp = await asyncio.wait_for(
            client.post(f"{GITHUB_API}/repos/{repo}/actions/runs/{run_id}/cancel", headers=headers, content=b""),
            timeout=timeout,
        )
        if resp.status_code in (200, 202):
            return self._ok("github_cancel_workflow_run", {"run_id": run_id, "cancelled": True}, ik)
        return self._http_fail("github_cancel_workflow_run", resp, ik)

    # ── releases ──────────────────────────────────────────────────────────────

    async def _create_release(self, args, repo, headers, client, timeout, ik) -> ToolResult:
        payload: dict[str, Any] = {
            "tag_name": args["tag_name"],
            "name": args["name"],
            "body": args.get("body", ""),
            "prerelease": args.get("prerelease", False),
            "draft": args.get("draft", False),
        }
        if args.get("target_commitish"):
            payload["target_commitish"] = args["target_commitish"]
        resp = await asyncio.wait_for(
            client.post(f"{GITHUB_API}/repos/{repo}/releases", json=payload, headers=headers),
            timeout=timeout,
        )
        if resp.status_code == 201:
            d = resp.json()
            return self._ok("github_create_release", {"id": d["id"], "tag_name": d["tag_name"], "html_url": d["html_url"]}, ik)
        return self._http_fail("github_create_release", resp, ik)

    # ── security ──────────────────────────────────────────────────────────────

    async def _list_dependabot_alerts(self, args, repo, headers, client, timeout, ik) -> ToolResult:
        params: dict[str, str] = {"state": args.get("state", "open"), "per_page": "30"}
        if args.get("severity"):
            params["severity"] = args["severity"]
        resp = await asyncio.wait_for(
            client.get(f"{GITHUB_API}/repos/{repo}/dependabot/alerts", params=params, headers=headers),
            timeout=timeout,
        )
        if resp.status_code == 200:
            alerts = [
                {
                    "number": a["number"],
                    "state": a["state"],
                    "severity": a["security_advisory"]["severity"],
                    "package": a["dependency"]["package"]["name"],
                    "html_url": a["html_url"],
                }
                for a in resp.json()
            ]
            return self._ok("github_list_dependabot_alerts", {"alerts": alerts, "count": len(alerts)}, ik)
        return self._http_fail("github_list_dependabot_alerts", resp, ik)

    async def _dismiss_alert(self, args, repo, headers, client, timeout, ik) -> ToolResult:
        alert_type = args["alert_type"]
        alert_id = args["alert_id"]
        payload: dict[str, Any] = {"dismissed_reason": args["dismissed_reason"]}
        if args.get("comment"):
            payload["dismissed_comment"] = args["comment"]

        url_map = {
            "dependabot": f"{GITHUB_API}/repos/{repo}/dependabot/alerts/{alert_id}",
            "code_scanning": f"{GITHUB_API}/repos/{repo}/code-scanning/alerts/{alert_id}",
            "secret_scanning": f"{GITHUB_API}/repos/{repo}/secret-scanning/alerts/{alert_id}",
        }
        url = url_map.get(alert_type)
        if not url:
            return ToolResult.fail("github_dismiss_alert", code="TOOL_UNKNOWN_ACTION",
                                   message=f"Unknown alert_type: {alert_type}", retryable=False,
                                   user_facing=True, idempotency_key=ik)
        resp = await asyncio.wait_for(
            client.patch(url, json=payload, headers=headers),
            timeout=timeout,
        )
        if resp.status_code == 200:
            return self._ok("github_dismiss_alert", {"alert_id": alert_id, "state": "dismissed"}, ik)
        return self._http_fail("github_dismiss_alert", resp, ik)

    # ── users / metadata ──────────────────────────────────────────────────────

    async def _lookup_user(self, args, headers, client, timeout, ik) -> ToolResult:
        username = _extract_username(args)
        if not username:
            return ToolResult.fail(
                "github_lookup_user",
                code="TOOL_INVALID_ARGS",
                message="username must not be empty",
                retryable=False,
                user_facing=True,
                idempotency_key=ik,
            )
        resp = await asyncio.wait_for(
            client.get(f"{GITHUB_API}/users/{username}", headers=headers),
            timeout=timeout,
        )
        if resp.status_code == 200:
            d = resp.json()
            return self._ok("github_lookup_user", {
                "login": d["login"], "name": d.get("name"), "company": d.get("company"),
                "html_url": d["html_url"], "public_repos": d.get("public_repos"),
            }, ik)
        return self._http_fail("github_lookup_user", resp, ik)


def _extract_username(args: dict[str, Any]) -> str:
    """Accept common username aliases used by function-call models."""
    for key in ("username", "user", "login", "handle"):
        value = args.get(key)
        if isinstance(value, str):
            cleaned = value.strip().lstrip("@")
            if cleaned:
                return cleaned
    return ""

    async def _get_codeowners(self, args, repo, headers, client, timeout, ik) -> ToolResult:
        ref = args.get("ref", "HEAD")
        for codeowners_path in ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"):
            resp = await asyncio.wait_for(
                client.get(f"{GITHUB_API}/repos/{repo}/contents/{codeowners_path}",
                           params={"ref": ref}, headers=headers),
                timeout=timeout,
            )
            if resp.status_code == 200:
                import base64
                d = resp.json()
                content = base64.b64decode(d.get("content", "")).decode("utf-8", errors="replace") if d.get("encoding") == "base64" else d.get("content", "")
                return self._ok("github_get_codeowners", {"path": codeowners_path, "content": content[:10000]}, ik)
        return ToolResult.fail("github_get_codeowners", code="GITHUB_NOT_FOUND",
                               message="CODEOWNERS file not found in repo", retryable=False,
                               user_facing=True, idempotency_key=ik)
