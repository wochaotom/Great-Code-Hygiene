ACTIVATION_MAP = {
    "general": set(),
    "api": {"rest_api", "web_or_api_security"},
    "docs": {"developer_documentation"},
    "security": {"security_core"},
}


def active_activation_values(domains):
    active = {"always"}
    for domain in domains:
        active.update(ACTIVATION_MAP.get(domain.lower(), set()))
    return active


def validate_domains(domains):
    errors = []
    allowed = sorted(ACTIVATION_MAP)
    for domain in domains:
        normalized = domain.lower()
        if normalized in ACTIVATION_MAP:
            continue
        errors.append(f"unknown domain: {domain}. Allowed domains: {', '.join(allowed)}")
    return errors
