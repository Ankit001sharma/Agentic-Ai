package sentinel.intent

import rego.v1

default deny_outright := false
default require_human_review := false
default require_local_model := false
default rate_limit_class := "normal"

deny_outright if {
    input.intent in data.deny_intents
}

require_human_review if {
    input.intent in data.review_intents
}

require_local_model if {
    input.sensitivity == "high"
    input.intent in data.local_model_intents
}

rate_limit_class := "strict" if {
    input.user.tier == "free"
    input.intent in data.strict_rate_intents
}
