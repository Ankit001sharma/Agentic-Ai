package sentinel.models

import rego.v1

# Allowed models per tier
allowed_models contains model if {
	some model in data.tiers[input.user.tier].allowed_models
}

# Models considered safe for sensitive content (local / on-prem)
sensitive_safe_models := data.sensitive_safe_models
