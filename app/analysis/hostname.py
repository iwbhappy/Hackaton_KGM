"""Conservative DNS wildcard and IP matching for certificate names."""
import ipaddress


def canonical(name: str) -> str:
    """Normalize case, terminal dot and IDNA labels."""
    return name.rstrip(".").lower().encode("idna").decode("ascii")


def dns_match(host: str, pattern: str) -> bool:
    """Match an exact DNS name or a wildcard occupying one complete left label."""
    try:
        host, pattern = canonical(host), canonical(pattern)
    except UnicodeError:
        return False
    if "*" not in pattern:
        return host == pattern
    labels, wanted = host.split("."), pattern.split(".")
    return (wanted[0] == "*" and pattern.count("*") == 1 and len(labels) == len(wanted)
            and len(labels) > 1 and bool(labels[0]) and labels[1:] == wanted[1:])


def match_hostname(target_host: str, san_dns: list[str], san_ip: list[str],
                   subject_cn: str | None) -> bool:
    """Match against SAN, allowing CN fallback only when no SAN names exist."""
    try:
        host_ip = ipaddress.ip_address(target_host.rstrip("."))
    except ValueError:
        if san_dns:
            return any(dns_match(target_host, name) for name in san_dns)
        return not san_ip and bool(subject_cn) and dns_match(target_host, subject_cn)
    candidates = san_ip if (san_ip or san_dns) else [subject_cn] if subject_cn else []
    for candidate in candidates:
        try:
            if host_ip == ipaddress.ip_address(candidate):
                return True
        except ValueError:
            continue
    return False
