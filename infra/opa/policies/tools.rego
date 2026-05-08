package sentinel.tools

import rego.v1

# Stage 7 (backend/app/pipeline/stage07_opa_policy.py) calls
#   /v1/data/sentinel/tools/allow_tool
# via OPAClient.check_tool() which expects an incremental SET of tool IDs
# (rego.v1 `contains` heads). Set membership ⇒ allowed. Do NOT convert this
# to a boolean `allow` rule — it would silently fail-open through the
# `else: bool(result)` branch in check_tool().
#
# Repo-level GitHub access (read/write/maintain) is enforced separately by
# `pipeline.github` (backend/infra/opa/policies/github.rego). This file
# enforces only the role/tier gate that Stage 7's input supports.

# ─────────────────────────────────────────────────────────────────────────────
# Legacy supervisor tools (kept for backward compat with old graph.py tools)
# ─────────────────────────────────────────────────────────────────────────────

allow_tool contains "web_search"        if { true }
allow_tool contains "rag_query"         if { true }
allow_tool contains "calculator"        if { true }
allow_tool contains "code_exec_sandbox" if { input.user.role in {"engineer", "admin", "sre"} }
allow_tool contains "sql_query_ro"      if { input.user.role in {"analyst", "admin"} }
allow_tool contains "http_get"          if { input.user.tier != "free" }
allow_tool contains "file_read"         if { object.get(input, "workspace_dir", null) != null }

# ─────────────────────────────────────────────────────────────────────────────
# Pipeline core tools (any authenticated user — high-impact gate handles review)
# ─────────────────────────────────────────────────────────────────────────────

allow_tool contains "search_web"         if { true }
allow_tool contains "search_docs"        if { true }
allow_tool contains "send_email"         if { true }
allow_tool contains "send_slack_message" if { true }

# ─────────────────────────────────────────────────────────────────────────────
# Legacy GitHub aliases (kept until callers migrate to the github_* IDs)
# ─────────────────────────────────────────────────────────────────────────────

# TEMP 2026-05-07: GitHub role gates relaxed for testing — restore the
# `input.user.role in {...}` guards below before shipping.
allow_tool contains "create_github_issue" if { true }

allow_tool contains "close_github_issue" if { true }

# ─────────────────────────────────────────────────────────────────────────────
# GitHub read-only (any authenticated user; repo-level ACLs in pipeline.github)
# ─────────────────────────────────────────────────────────────────────────────

github_read_tools := {
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

allow_tool contains tool if {
    some tool in github_read_tools
}

# ─────────────────────────────────────────────────────────────────────────────
# GitHub write (engineer / admin / sre)
# ─────────────────────────────────────────────────────────────────────────────

github_write_tools := {
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
    "github_trigger_workflow",
}

# TEMP 2026-05-07: write tools open to everyone for testing.
allow_tool contains tool if {
    some tool in github_write_tools
}

# ─────────────────────────────────────────────────────────────────────────────
# GitHub maintainer (admin / sre)
# ─────────────────────────────────────────────────────────────────────────────

github_maintainer_tools := {
    "github_merge_pr",
    "github_create_release",
}

# TEMP 2026-05-07: maintainer tools open to everyone for testing.
allow_tool contains tool if {
    some tool in github_maintainer_tools
}

# ─────────────────────────────────────────────────────────────────────────────
# GitHub security alerts (security_admin only)
# ─────────────────────────────────────────────────────────────────────────────

# TEMP 2026-05-07: security alert dismissal open for testing — restore
# `input.user.role == "security_admin"` before shipping.
allow_tool contains "github_dismiss_alert" if { true }

# ─────────────────────────────────────────────────────────────────────────────
# miniOrange documentation tools (any authenticated user)
# ─────────────────────────────────────────────────────────────────────────────

allow_tool contains "query_miniorange_docs"   if { true }
allow_tool contains "list_miniorange_plugins" if { true }
allow_tool contains "get_miniorange_plugin"   if { true }

# ─────────────────────────────────────────────────────────────────────────────
# Per-tool deny reasons (queryable at /v1/data/sentinel/tools/reasons)
# Stage 7 currently synthesises a generic message, but these are available for
# richer deny messages once policies.py.check_tool() also fetches `reasons`.
# ─────────────────────────────────────────────────────────────────────────────

reasons contains msg if {
    input.tool_id in github_write_tools
    not input.user.role in {"engineer", "admin", "sre"}
    msg := sprintf("Tool '%s' requires engineer, admin, or sre role (got '%v')", [input.tool_id, input.user.role])
}

reasons contains msg if {
    input.tool_id in github_maintainer_tools
    not input.user.role in {"admin", "sre"}
    msg := sprintf("Tool '%s' requires admin or sre role (got '%v')", [input.tool_id, input.user.role])
}

reasons contains msg if {
    input.tool_id == "github_dismiss_alert"
    input.user.role != "security_admin"
    msg := "github_dismiss_alert requires the security_admin role"
}

reasons contains msg if {
    input.tool_id == "code_exec_sandbox"
    not input.user.role in {"engineer", "admin", "sre"}
    msg := sprintf("code_exec_sandbox requires engineer/admin/sre role (got '%v')", [input.user.role])
}

reasons contains msg if {
    input.tool_id == "sql_query_ro"
    not input.user.role in {"analyst", "admin"}
    msg := sprintf("sql_query_ro requires analyst or admin role (got '%v')", [input.user.role])
}

reasons contains msg if {
    input.tool_id == "http_get"
    input.user.tier == "free"
    msg := "http_get is not available on the free tier"
}
