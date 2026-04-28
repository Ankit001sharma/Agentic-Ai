package sentinel

import rego.v1

# Default deny is risky for a demo gateway; default to allow,
# but downstream Decision Gate is what enforces risk-based blocks.
default allow := true

# Reasons explaining the decision
default reasons := []

# Block if input verdict is already BLOCK
allow := false if {
	input.verdict == "BLOCK"
}

reasons := r if {
	input.verdict == "BLOCK"
	r := ["input_verdict_block"]
}

# Block if requested model is not in the user's allowed list
allow := false if {
	some allowed in data.tiers[input.user.tier].allowed_models
	not allowed_model_match(input.model)
}

allowed_model_match(model) if {
	some m in data.tiers[input.user.tier].allowed_models
	m == model
}

# Block if region restricted
allow := false if {
	input.user.region in data.restricted_regions
}
