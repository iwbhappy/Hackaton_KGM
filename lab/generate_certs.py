"""Generate deliberately varied certificates for the offline laboratory."""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import AuthorityInformationAccessOID, NameOID

ROOT = Path(__file__).resolve().parent.parent
SERVICES = {"valid": 365, "info": 45, "warn": 25, "soon": 10, "vpn": 5,
            "expired": -5, "selfsigned": 365, "untrusted": 365,
            "nochain": 365, "mismatch": 365, "weak": 200, "wildcard": 300}
PEM = serialization.Encoding.PEM


def der(tag: int, value: bytes) -> bytes:
    """Encode one DER element (used only to create the intentionally weak fixture)."""
    size = len(value)
    length = bytes([size]) if size < 128 else size.to_bytes((size.bit_length() + 7) // 8, "big")
    if size >= 128:
        length = bytes([0x80 | len(length)]) + length
    return bytes([tag]) + length + value


def sign_legacy(cert: x509.Certificate, issuer_key) -> x509.Certificate:
    """Sign the laboratory fixture with SHA-1, unsupported by modern builders."""
    sha256_oid = bytes.fromhex("06092a864886f70d01010b")
    sha1_oid = bytes.fromhex("06092a864886f70d010105")
    tbs = cert.tbs_certificate_bytes.replace(sha256_oid, sha1_oid, 1)
    signature = issuer_key.sign(tbs, padding.PKCS1v15(), hashes.SHA1())
    encoded = der(0x30, tbs + der(0x30, sha1_oid + b"\x05\x00") + der(3, b"\x00" + signature))
    return x509.load_der_x509_certificate(encoded)


def make_certificate(name: str, days: int, issuer=None, ca=False, weak=False,
                     san: str | None = None) -> tuple:
    """Create a key and a certificate with strict-compatible CA extensions."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=1024 if weak else 2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name),
                         x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Certificate Radar Lab")])
    issuer_cert, issuer_key = issuer if issuer else (None, key)
    now = datetime.now(timezone.utc)
    builder = (x509.CertificateBuilder().subject_name(subject)
               .issuer_name(issuer_cert.subject if issuer_cert else subject)
               .public_key(key.public_key()).serial_number(x509.random_serial_number())
               .not_valid_before(now - timedelta(days=400 if days < 0 else 1))
               .not_valid_after(now + timedelta(days=days, hours=12))
               .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
               .add_extension(x509.KeyUsage(True, False, not ca, False, False, ca, ca, None, None), True)
               .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
               .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()), False))
    if not ca:
        builder = builder.add_extension(x509.SubjectAlternativeName([x509.DNSName(san or name)]), False)
        builder = builder.add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), False)
        if issuer:
            builder = builder.add_extension(x509.AuthorityInformationAccess([
                x509.AccessDescription(AuthorityInformationAccessOID.CA_ISSUERS,
                                       x509.UniformResourceIdentifier("http://ca.lab.local/intermediate.crt"))]), False)
    cert = builder.sign(issuer_key, hashes.SHA256())
    return (sign_legacy(cert, issuer_key) if weak else cert), key


def write_pair(folder: Path, name: str, pair: tuple, chain: list) -> None:
    """Write PEM and password-protected PFX fixtures for one service."""
    cert, key = pair
    (folder / f"{name}.key").write_bytes(key.private_bytes(
        PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    (folder / f"{name}.crt").write_bytes(cert.public_bytes(PEM))
    (folder / f"{name}.fullchain.pem").write_bytes(b"".join(c.public_bytes(PEM) for c in [cert, *chain]))
    (folder / f"{name}.pfx").write_bytes(pkcs12.serialize_key_and_certificates(
        name.encode(), key, cert, chain or None, serialization.BestAvailableEncryption(b"lab")))


def generate(output: Path = ROOT / "lab/certs", trust: Path = ROOT / "data/trusted_ca") -> None:
    """Generate all fixtures and install only the laboratory root as trusted."""
    output.mkdir(parents=True, exist_ok=True)
    trust.mkdir(parents=True, exist_ok=True)
    root = make_certificate("Lab Root CA", 3650, ca=True)
    intermediate = make_certificate("Lab Intermediate CA", 1825, issuer=root, ca=True)
    rogue = make_certificate("Rogue CA", 3650, ca=True)
    for name, pair in [("lab-root-ca", root), ("lab-intermediate-ca", intermediate), ("rogue-ca", rogue)]:
        write_pair(output, name, pair, [])
    (trust / "lab-root-ca.pem").write_bytes(root[0].public_bytes(PEM))
    for name, days in SERVICES.items():
        issuer = None if name == "selfsigned" else rogue if name == "untrusted" else intermediate
        san = "www.other.local" if name == "mismatch" else "*.lab.local" if name == "wildcard" else None
        pair = make_certificate(f"{name}.lab.local", days, issuer, weak=name == "weak", san=san)
        chain = [] if name in {"selfsigned", "nochain"} else [issuer[0]]
        write_pair(output, name, pair, chain)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Генерация сертификатов локального стенда")
    parser.add_argument("--output", type=Path, default=ROOT / "lab/certs")
    parser.add_argument("--trust", type=Path, default=ROOT / "data/trusted_ca")
    args = parser.parse_args()
    generate(args.output, args.trust)
    print(f"Сертификаты созданы: {args.output}. Корневой CA: {args.trust}")
