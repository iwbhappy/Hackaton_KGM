from datetime import datetime, timedelta, timezone
import pytest

from app.analysis.analyzer import analyze
from app.analysis.checks import CHECKS, run_checks
from app.config import DEFAULTS

NOW = datetime.now(timezone.utc)
GOOD = {"reachable": True, "days_left": 365, "status": "OK", "not_before": NOW - timedelta(days=1),
        "not_after": NOW + timedelta(days=365), "chain_status": "valid", "hostname_match": "match",
        "key_type": "RSA", "key_size": 2048, "signature_algorithm": "sha256WithRSAEncryption", "tls_version": "TLSv1.3"}
OWNER = {"host": "valid.lab.local", "owner": "ИТ", "criticality": "normal"}


@pytest.mark.parametrize("changes,code", [({"days_left": -1}, "EXPIRED"), ({"days_left": 10}, "EXPIRING"),
    ({"self_signed": True}, "SELF_SIGNED"), ({"chain_status": "incomplete_or_untrusted"}, "CHAIN_UNTRUSTED"),
    ({"hostname_match": "mismatch"}, "HOSTNAME_MISMATCH"), ({"key_size": 1024}, "WEAK_KEY"),
    ({"key_type": "EC", "key_size": 224}, "WEAK_KEY"), ({"signature_algorithm": "sha1WithRSAEncryption"}, "WEAK_SIGNATURE"),
    ({"tls_version": "TLSv1.1"}, "OLD_TLS"), ({"not_before": NOW + timedelta(days=1)}, "NOT_YET_VALID"),
    ({"reachable": False}, "UNREACHABLE")])
def test_checks_trigger(changes, code):
    issues = run_checks(dict(GOOD, **changes), OWNER, DEFAULTS)
    assert code in {issue["code"] for issue in issues}


def test_checks_clear_and_owner():
    assert all(check(GOOD, OWNER, DEFAULTS) is None for check in CHECKS)
    assert run_checks(GOOD, {}, DEFAULTS)[0]["code"] == "NO_OWNER"
    issues = run_checks(dict(GOOD, self_signed=True, chain_status="error"), OWNER, DEFAULTS)
    assert [i["code"] for i in issues] == ["SELF_SIGNED"]
    assert not run_checks(dict(GOOD, chain_status="valid_but_expired"), OWNER, DEFAULTS)


def test_analyze_uses_expiration_only_for_status():
    result = analyze(dict(GOOD, hostname_match="mismatch", self_signed=True), OWNER, now=NOW)
    assert result["status"] == "OK"
    assert result["risk_score"] == 45
    assert sum(i["points"] for i in result["issues"]) == 45
