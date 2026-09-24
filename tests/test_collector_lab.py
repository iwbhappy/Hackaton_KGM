import pytest

from app.collectors.tls_collector import TLSCollector, result_attributes
from app.parser import Target


@pytest.mark.lab
@pytest.mark.parametrize("name,chain", [
    ("valid", "valid"), ("info", "valid"), ("warn", "valid"),
    ("soon", "valid"), ("vpn", "valid"), ("expired", "valid_but_expired"),
    ("selfsigned", "self_signed"), ("untrusted", "untrusted_root"),
    ("nochain", "incomplete_or_untrusted"), ("mismatch", "valid"),
    ("weak", "error"), ("wildcard", "valid"),
])
def test_collector_lab(name, chain, lab_server, lab_material):
    host = name + ".lab.local"
    target = Target(host, lab_server.server_address[1], host)
    collector = TLSCollector(trust_dir=lab_material[1], connect_host="127.0.0.1")
    result = result_attributes(collector.collect(target), host)
    assert result["reachable"] is True
    assert result["chain_status"] == chain
    assert result["hostname_match"] == ("mismatch" if name == "mismatch" else "match")
    assert result["self_signed"] is (name == "selfsigned")
    assert len(result["thumbprint_sha1"]) == 40
    assert result["not_after"].tzinfo is not None
    if name == "nochain":
        assert "промежуточный" in result["chain_message"]


@pytest.mark.lab
def test_unreachable(lab_server, lab_material):
    target = Target("127.0.0.2", lab_server.server_address[1])
    result = TLSCollector(timeout=0.2, trust_dir=lab_material[1]).collect(target)
    assert not result.reachable
    assert result.der is None
    assert result.error
