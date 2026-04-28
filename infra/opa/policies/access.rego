package sentinel.access

import rego.v1

default allow := true

default reasons := []

# Deny non-admin explicit privilege escalation intent
allow := false if {
    input.intent == "privilege_escalation"
    input.user.role != "admin"
}
reasons := r if {
    input.intent == "privilege_escalation"
    input.user.role != "admin"
    r := ["intent_privileged_non_admin"]
}

# Resource-based RBAC: role must be in data.resource_role_map[resource]
allow := false if {
    some res
    res = input.resource
    res in data.resource_role_map
    not user_in_allowed_roles(res, input.user.role)
}
reasons := r if {
    some res
    res = input.resource
    res in data.resource_role_map
    not user_in_allowed_roles(res, input.user.role)
    r := [sprintf("resource_denied:%s", [res])]
}

user_in_allowed_roles(res, role) if {
    role in data.resource_role_map[res]
}

# Write actions from low-priv roles
allow := false if {
    input.action == "write"
    input.user.role in {"viewer", "guest"}
}
reasons := r if {
    input.action == "write"
    input.user.role in {"viewer", "guest"}
    r := ["write_denied_for_role"]
}
