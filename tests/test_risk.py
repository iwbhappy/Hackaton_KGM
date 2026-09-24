from app.analysis.risk import calculate_risk


def risk(days=5, codes=(), criticality="normal", reachable=True):
    return calculate_risk({"status": "CRITICAL" if reachable else "ERROR", "reachable": reachable,
                           "days_left": days, "issues": [{"code": code} for code in codes]},
                          {"criticality": criticality})


def test_vpn_is_91_critical():
    result = risk(criticality="critical")
    assert (result["risk_score"], result["risk_level"]) == (91, "Critical")
    assert "×1.3" in result["reasons"][-1]["text"]


def test_expired_cap_grouping_owner_and_error():
    assert risk(days=-1)["risk_score"] == 80
    assert risk(days=-1, codes=["HOSTNAME_MISMATCH"])["risk_score"] == 100
    assert risk(days=100, codes=["SELF_SIGNED", "CHAIN_UNTRUSTED"])["risk_score"] == 25
    assert risk(days=100, codes=["WEAK_KEY", "WEAK_SIGNATURE", "OLD_TLS"])["risk_score"] == 15
    assert risk(days=100, codes=["NO_OWNER"])["risk_score"] == 10
    assert risk(reachable=False)["risk_score"] is None
