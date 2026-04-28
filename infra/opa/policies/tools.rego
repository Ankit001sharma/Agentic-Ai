package sentinel.tools

import rego.v1

# Returns set of tool names allowed for this user in this request context
default allow_tool := {}

# Every package must be queryable: we expose allow_tool as a set via a rule
# that yields each tool name on success (OPA 1.0+ set generation pattern).
allow_tool contains "web_search" if { true }
allow_tool contains "rag_query" if { true }
allow_tool contains "calculator" if { true }
allow_tool contains "code_exec_sandbox" if { input.user.role in {"engineer", "admin", "sre"} }
allow_tool contains "sql_query_ro" if { input.user.role in {"analyst", "admin"} }
allow_tool contains "http_get" if { input.user.tier != "free" }
allow_tool contains "file_read" if { object.get(input, "workspace_dir", null) != null }
