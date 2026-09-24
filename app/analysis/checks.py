"""Issue registry: add one check function and register it in CHECKS."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from app.analysis.status import as_utc


@dataclass
class Issue:
    code: str
    severity: str
    title: str
    detail: str
    recommendation: str
    points: int = 0


def check_expired(result, endpoint, config) -> Issue | None:
    """Report expired certificates."""
    if result.get("days_left") is not None and result["days_left"] < 0:
        return Issue("EXPIRED", "critical", "Сертификат истёк", f"Истёк {-result['days_left']} дн. назад",
                     "Немедленно перевыпустить и установить новый сертификат; проверить доступность сервиса")


def check_expiring(result, endpoint, config) -> Issue | None:
    """Report approaching expiry using the configured thresholds."""
    days = result.get("days_left")
    if days is not None and 0 <= days <= config["threshold_info"]:
        severity = {"INFO": "info", "WARNING": "medium", "CRITICAL": "critical"}.get(result.get("status"), "info")
        return Issue("EXPIRING", severity, f"Сертификат скоро истекает ({days} дн.)", f"Осталось {days} дн.",
                     "Запланировать перевыпуск; уведомить владельца")


def check_self_signed(result, endpoint, config) -> Issue | None:
    """Report verified self-signed leaves."""
    if result.get("self_signed"):
        return Issue("SELF_SIGNED", "high", "Самоподписанный сертификат", "Подпись проверена собственным ключом",
                     "Заменить на сертификат, выпущенный корпоративным или публичным CA")


def check_chain(result, endpoint, config) -> Issue | None:
    """Report trust failures separately from expiry and self-signatures."""
    if not result.get("self_signed") and result.get("chain_status") in {"untrusted_root", "incomplete_or_untrusted", "error"}:
        return Issue("CHAIN_UNTRUSTED", "high", "Ошибка цепочки доверия", result.get("chain_message") or "",
                     "Установить на сервере полную цепочку (включая промежуточные сертификаты) или добавить корневой CA в доверенные")


def check_hostname(result, endpoint, config) -> Issue | None:
    """Report a service name absent from the certificate."""
    if result.get("hostname_match") == "mismatch":
        return Issue("HOSTNAME_MISMATCH", "high", "Имя сервиса не совпадает с CN/SAN", endpoint.get("host", ""),
                     "Перевыпустить сертификат с корректным SAN, включающим имя сервиса")


def check_key(result, endpoint, config) -> Issue | None:
    """Report undersized RSA or EC keys."""
    key_type, size = result.get("key_type"), result.get("key_size")
    if size is not None and ((key_type == "RSA" and size < 2048) or (key_type == "EC" and size < 256)):
        return Issue("WEAK_KEY", "medium", f"Слабый ключ ({key_type} {size})", f"{key_type} {size} бит",
                     "Перевыпустить с ключом RSA ≥ 2048 или ECDSA P-256")


def check_signature(result, endpoint, config) -> Issue | None:
    """Report SHA-1 and MD5 certificate signatures."""
    algorithm = result.get("signature_algorithm") or ""
    if any(weak in algorithm.lower().replace("-", "") for weak in ("sha1", "md5")):
        return Issue("WEAK_SIGNATURE", "medium", "Устаревший алгоритм подписи", algorithm,
                     "Перевыпустить с подписью SHA-256 или выше")


def check_tls(result, endpoint, config) -> Issue | None:
    """Report a negotiated TLS version older than 1.2."""
    if result.get("tls_version") in {"TLSv1", "TLSv1.0", "TLSv1.1"}:
        return Issue("OLD_TLS", "medium", "Устаревшая версия TLS", result["tls_version"],
                     "Отключить TLS 1.0/1.1 на сервере, включить TLS 1.2/1.3")


def check_not_yet_valid(result, endpoint, config) -> Issue | None:
    """Report future validity start dates."""
    if result.get("not_before") and as_utc(result["not_before"]) > config.get("now", datetime.now(timezone.utc)):
        return Issue("NOT_YET_VALID", "medium", "Сертификат ещё не действителен", str(result["not_before"]),
                     "Проверить время на сервере и дату выпуска")


def check_owner(result, endpoint, config) -> Issue | None:
    """Report services without an assigned owner."""
    if not (endpoint.get("owner") or "").strip():
        return Issue("NO_OWNER", "low", "Не назначен владелец", "Нет ответственного за перевыпуск",
                     "Назначить ответственного за сервис")


def check_unreachable(result, endpoint, config) -> Issue | None:
    """Report failed TLS observations."""
    if not result.get("reachable"):
        return Issue("UNREACHABLE", "info", "Сервис недоступен", result.get("error") or "Сертификат не получен",
                     "Проверить доступность сервиса и корректность адреса")


CHECKS = [check_expired, check_expiring, check_self_signed, check_chain, check_hostname,
          check_key, check_signature, check_tls, check_not_yet_valid, check_owner, check_unreachable]


def run_checks(result: dict, endpoint: dict, config: dict) -> list[dict]:
    """Execute all registered checks; failed observations have no certificate findings."""
    checks = CHECKS if result.get("reachable") else [check_owner, check_unreachable]
    return [asdict(issue) for check in checks if (issue := check(result, endpoint, config))]
