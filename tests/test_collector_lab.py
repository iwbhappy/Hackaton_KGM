import socket
import ssl
import warnings
from threading import Thread

import pytest

from app.analysis.analyzer import analyze
from app.collectors.tls_collector import TLSCollector, result_attributes
from app.parser import Target
from lab.lab_server import LabServer


@pytest.mark.lab
@pytest.mark.parametrize("name,chain", [
    ("valid", "valid"), ("info", "valid"), ("warn", "valid"),
    ("soon", "valid"), ("vpn", "valid"), ("expired", "valid_but_expired"),
    ("selfsigned", "self_signed"), ("untrusted", "untrusted_root"),
    ("nochain", "incomplete_or_untrusted"), ("mismatch", "valid"),
    ("weak", "valid"), ("wildcard", "valid"),
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
    if name == "weak":
        assert "пониженным уровнем" in result["chain_message"]
        assert "по умолчанию отклонено:" in result["chain_message"]
        analyzed = analyze(result, {"owner": "", "criticality": "normal"})
        assert {issue["code"] for issue in analyzed["issues"]} == {"WEAK_KEY", "WEAK_SIGNATURE", "NO_OWNER"}
        assert analyzed["risk_score"] == 25


@pytest.mark.lab
def test_trusted_tls_v1(lab_material):
    with LabServer(("127.0.0.1", 0), lab_material[0]) as server:
        ctx = server.default_context
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                ctx.minimum_version = ctx.maximum_version = ssl.TLSVersion.TLSv1
            ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
        except (ssl.SSLError, ValueError) as error:
            pytest.skip(f"OpenSSL не разрешает TLS 1.0: {error}")
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            # Probe support independently so a verification regression cannot cause a skip.
            probe = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            probe.check_hostname = False
            probe.verify_mode = ssl.CERT_NONE
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    probe.minimum_version = probe.maximum_version = ssl.TLSVersion.TLSv1
                probe.set_ciphers("DEFAULT:@SECLEVEL=0")
                with socket.create_connection(server.server_address, timeout=2) as raw:
                    with probe.wrap_socket(raw, server_hostname="valid.lab.local"):
                        pass
            except (ssl.SSLError, ValueError) as error:
                pytest.skip(f"OpenSSL не поддерживает рукопожатие TLS 1.0: {error}")
            target = Target("valid.lab.local", server.server_address[1], "valid.lab.local")
            collector = TLSCollector(trust_dir=lab_material[1], connect_host="127.0.0.1")
            result = result_attributes(collector.collect(target), target.host)
            assert result["tls_version"] == "TLSv1"
            assert result["chain_status"] == "valid"
            assert "пониженным уровнем" in result["chain_message"]
            analyzed = analyze(result, {"owner": "ИТ", "criticality": "normal"})
            assert {issue["code"] for issue in analyzed["issues"]} == {"OLD_TLS"}
        finally:
            server.shutdown()
            thread.join(timeout=5)


@pytest.mark.lab
def test_unreachable(lab_server, lab_material):
    target = Target("127.0.0.2", lab_server.server_address[1])
    result = TLSCollector(timeout=0.2, trust_dir=lab_material[1]).collect(target)
    assert not result.reachable
    assert result.der is None
    assert result.error
