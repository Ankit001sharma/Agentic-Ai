package sentinel.compliance

import rego.v1

default allow := true
default reasons := []

allow := false if {
    input.data_class == "PII"
    not input.user.region in data.allowed_pii_regions
}
reasons := r if {
    input.data_class == "PII"
    not input.user.region in data.allowed_pii_regions
    r := ["pii_region_mismatch"]
}

allow := false if {
    input.data_class == "PHI"
    not object.get(input.user, "hipaa_authorized", false)
}
reasons := r if {
    input.data_class == "PHI"
    not object.get(input.user, "hipaa_authorized", false)
    r := ["phi_requires_hipaa"]
}
