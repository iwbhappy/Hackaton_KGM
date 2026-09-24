import socket
import ssl
from datetime import datetime, timezone

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import pkcs12


def test_lab_certificates_and_sha1(lab_material):
    folder, trust = lab_material
    weak = x509.load_pem_x509_certificate((folder / "weak.crt").read_bytes())
    issuer = x509.load_pem_x509_certificate((folder / "lab-intermediate-ca.crt").read_bytes())
    issuer.public_key().verify(weak.signature, weak.tbs_certificate_bytes,
                               padding.PKCS1v15(), weak.signature_hash_algorithm)
    assert weak.signature_hash_algorithm.name == "sha1"
    assert weak.public_key().key_size == 1024
    soon = x509.load_pem_x509_certificate((folder / "soon.crt").read_bytes())
    assert (soon.not_valid_after_utc - datetime.now(timezone.utc)).days == 10
    assert (folder / "nochain.fullchain.pem").read_bytes().count(b"BEGIN CERTIFICATE") == 1
    assert (folder / "valid.fullchain.pem").read_bytes().count(b"BEGIN CERTIFICATE") == 2
    assert len(list(trust.glob("*.pem"))) == 1
    assert pkcs12.load_key_and_certificates((folder / "weak.pfx").read_bytes(), b"lab")[1] == weak


def test_sni_and_default_certificate(lab_server):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    for name in ["soon.lab.local", "nochain.lab.local", None]:
        with socket.create_connection(lab_server.server_address, timeout=3) as sock:
            with ctx.wrap_socket(sock, server_hostname=name) as tls:
                cert = x509.load_der_x509_certificate(tls.getpeercert(binary_form=True))
                cn = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
                assert cn == (name or "valid.lab.local")
                tls.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
                assert b"Lab service:" in tls.recv(4096)
