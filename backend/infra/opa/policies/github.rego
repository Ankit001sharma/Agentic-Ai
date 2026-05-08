package pipeline.github

import future.keywords.if
import future.keywords.in

# Default deny
default allow := false
default reason := "no matching rule"

# ── Read-only: any authenticated user with repo read access ──────────────────

allow if {
    input.tool_id in {
        "github_get_file_contents",
        "github_search_code",
        "github_get_pr_diff",
        "github_list_open_prs",
        "github_list_dependabot_alerts",
        "github_get_workflow_run",
        "github_get_workflow_logs",
        "github_lookup_user",
        "github_get_codeowners",
    }
    user_has_repo_access(input.user, input.arguments.repo, "read")
}

# ── Write: contributor / engineer role required ──────────────────────────────

allow if {
    input.tool_id in {
        "github_create_issue",
        "github_update_issue",
        "github_close_issue",
        "github_comment_on_issue",
        "github_create_pr",
        "github_comment_on_pr",
        "github_create_branch",
        "github_update_file",
        "github_rerun_failed_jobs",
        "github_cancel_workflow_run",
    }
    user_has_repo_access(input.user, input.arguments.repo, "write")
}

# ── Maintainer: merge / approve / release ───────────────────────────────────

allow if {
    input.tool_id in {
        "github_merge_pr",
        "github_create_release",
    }
    user_has_repo_access(input.user, input.arguments.repo, "maintain")
}

# ── Workflow trigger: write for non-prod, deployer for production ─────────────

allow if {
    input.tool_id == "github_trigger_workflow"
    input.arguments.env != "production"
    user_has_repo_access(input.user, input.arguments.repo, "write")
}

allow if {
    input.tool_id == "github_trigger_workflow"
    input.arguments.env == "production"
    "deployer" in input.user.roles
}

# ── Security alerts: security_admin only ────────────────────────────────────

allow if {
    input.tool_id == "github_dismiss_alert"
    "security_admin" in input.user.roles
}

# ── Deny reason messages ─────────────────────────────────────────────────────

reason := msg if {
    not allow
    input.tool_id == "github_merge_pr"
    msg := "Merging requires maintainer role on the repository"
}

reason := msg if {
    not allow
    input.tool_id == "github_dismiss_alert"
    msg := "Dismissing security alerts requires security_admin role"
}

reason := msg if {
    not allow
    input.tool_id == "github_trigger_workflow"
    input.arguments.env == "production"
    msg := "Production deploys require the 'deployer' role"
}

reason := msg if {
    not allow
    input.tool_id == "github_create_release"
    msg := "Creating releases requires maintainer role on the repository"
}

# ── Helpers ───────────────────────────────────────────────────────────────────
# Backed by data loaded into OPA from your IAM / GitHub org membership sync.

user_has_repo_access(user, repo, level) if {
    access := data.github_access[user.id][repo]
    level_rank(level) <= level_rank(access)
}

level_rank("read")     := 1
level_rank("triage")   := 2
level_rank("write")    := 3
level_rank("maintain") := 4
level_rank("admin")    := 5
