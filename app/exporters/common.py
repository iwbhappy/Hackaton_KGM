"""Shared localized report columns and spreadsheet-safe text."""
from app.analysis.status import as_utc

STATUS_LABELS = {"OK": "OK", "INFO": "Информация", "WARNING": "Предупреждение",
                 "CRITICAL": "Критический", "EXPIRED": "Истёк", "ERROR": "Недоступно"}
STATUS_COLORS = {"OK": "E6F5EC", "INFO": "E9F1FF", "WARNING": "FFF3D8",
                 "CRITICAL": "FFF0E3", "EXPIRED": "FBE9E9", "ERROR": "EDF0F4"}
CHAIN_LABELS = {"valid": "Доверена", "valid_but_expired": "Цепочка построена, сертификат истёк",
                "self_signed": "Самоподписанный", "untrusted_root": "Недоверенный корневой CA",
                "incomplete_or_untrusted": "Неполная цепочка или недоверенный CA", "error": "Ошибка",
                "not_yet_valid": "Ещё не действителен", "not_checked": "Не проверена"}
COLUMNS = [("service_name", "Сервис"), ("host", "Хост"), ("port", "Порт"), ("owner", "Владелец"),
           ("criticality", "Критичность"), ("issuer", "Издатель"), ("subject_cn", "CN"),
           ("not_after", "Истекает (UTC)"), ("days_left", "Осталось дней"), ("status", "Статус"),
           ("chain_status", "Цепочка"), ("hostname_match", "Имя"), ("risk_score", "Риск"),
           ("risk_level", "Уровень риска"), ("san", "SAN"), ("thumbprint_sha1", "Thumbprint SHA-1"),
           ("issues", "Проблемы"), ("resolved_ip", "IP"), ("not_before", "Действует с (UTC)"),
           ("tls_version", "TLS"), ("key_type", "Тип ключа"), ("key_size", "Бит"),
           ("signature_algorithm", "Подпись"), ("fingerprint_sha256", "SHA-256"), ("reasons", "Причины риска")]


def display_value(row: dict, key: str):
    """Get a localized scalar for a report column."""
    if key == "issuer":
        return row.get("issuer_o") or row.get("issuer_cn") or "—"
    if key == "san":
        return "; ".join(row.get("san_dns", []) + row.get("san_ip", []))
    if key == "issues":
        return "; ".join(issue["title"] for issue in row["issues"])
    if key == "reasons":
        return "; ".join(reason["text"] for reason in row["reasons"])
    if key in {"not_after", "not_before"}:
        return as_utc(row[key]).strftime("%d.%m.%Y %H:%M UTC") if row.get(key) else "—"
    if key == "status":
        return STATUS_LABELS.get(row[key], row[key])
    if key == "chain_status":
        return CHAIN_LABELS.get(row[key], row[key])
    if key == "hostname_match":
        return {"match": "Совпадает", "mismatch": "Не совпадает", "not_checked": "Не проверено"}[row[key]]
    if key == "criticality":
        return {"low": "Низкая", "normal": "Обычная", "high": "Высокая", "critical": "Критичная"}[row[key]]
    return row.get(key) if row.get(key) is not None else "—"


def csv_safe(value):
    """Prevent formulas when a text field is opened by spreadsheet software."""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value
