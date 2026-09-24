"""Explainable bounded risk score with non-overlapping issue groups."""
from app.config import DEFAULTS


def calculate_risk(result: dict, endpoint: dict, config: dict | None = None) -> dict:
    """Score one service and return every contribution and criticality multiplier."""
    config = config or DEFAULTS
    if result.get("status") == "ERROR" or not result.get("reachable"):
        return {"risk_score": None, "risk_level": None, "reasons": []}
    weights, reasons = config["risk_weights"], []
    days = result.get("days_left")
    base = weights["expired"] if days is not None and days < 0 else next(
        (weights[str(bound)] for bound in [7, 14, 30, 60] if days is not None and days <= bound), 0)
    if base:
        text = "Сертификат истёк" if days < 0 else f"Сертификат истекает через {days} дней"
        reasons.append({"code": "EXPIRED" if days < 0 else "EXPIRING", "text": f"{text} (+{base})", "points": base})
    codes = {issue["code"] for issue in result.get("issues", [])}
    chain = [("SELF_SIGNED", weights["self_signed"], "Самоподписанный сертификат"),
             ("CHAIN_UNTRUSTED", weights["chain"], "Ошибка цепочки доверия")]
    contributions = sorted([item for item in chain if item[0] in codes], key=lambda i: i[1], reverse=True)[:1]
    if "HOSTNAME_MISMATCH" in codes:
        contributions.append(("HOSTNAME_MISMATCH", weights["hostname"], "Имя не совпадает с CN/SAN"))
    crypto = next((code for code in ["WEAK_KEY", "WEAK_SIGNATURE", "OLD_TLS"] if code in codes), None)
    if crypto:
        contributions.append((crypto, weights["crypto"], "Слабая криптография (один раз за группу)"))
    if "NO_OWNER" in codes:
        contributions.append(("NO_OWNER", weights["no_owner"], "Не назначен владелец"))
    for code, points, text in contributions:
        reasons.append({"code": code, "text": f"{text} (+{points})", "points": points})
    multiplier = config["risk_multipliers"].get(endpoint.get("criticality") or "normal", 1)
    score = min(100, round(sum(reason["points"] for reason in reasons) * multiplier))
    if multiplier != 1:
        label = {"low": "низкой критичности", "high": "высокой критичности", "critical": "критичный"}[endpoint["criticality"]]
        reasons.append({"code": "CRITICALITY", "text": f"Сервис {label} (×{multiplier})", "points": 0})
    level = "Low" if score < 20 else "Medium" if score < 50 else "High" if score < 80 else "Critical"
    return {"risk_score": score, "risk_level": level, "reasons": reasons}
