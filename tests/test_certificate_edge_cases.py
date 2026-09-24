from cryptography import x509
from cryptography.hazmat.primitives import serialization

from app.analysis.cert_parser import is_self_signed
from lab.generate_certs import make_certificate


def test_legacy_self_signature_is_checked_cryptographically():
    cert, _ = make_certificate("legacy.local", 90, weak=True)
    assert is_self_signed(cert)
    der = cert.public_bytes(serialization.Encoding.DER)
    tampered = x509.load_der_x509_certificate(der[:-1] + bytes([der[-1] ^ 1]))
    assert not is_self_signed(tampered)
