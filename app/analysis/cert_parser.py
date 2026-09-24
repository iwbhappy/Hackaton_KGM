"""Extract certificate attributes from DER, even when trust verification fails."""
from datetime import datetime, timezone
from math import floor
from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, ed448, rsa, dsa
from cryptography.x509.oid import AuthorityInformationAccessOID, NameOID


def name_value(name: x509.Name, oid) -> str | None:
    """Return the first matching distinguished-name attribute."""
    values = name.get_attributes_for_oid(oid)
    return values[0].value if values else None


def is_self_signed(cert: x509.Certificate) -> bool:
    """Require both matching issuer/subject and a verified self-signature."""
    if cert.subject != cert.issuer:
        return False
    try:
        cert.verify_directly_issued_by(cert)
        return True
    except (ValueError, TypeError, InvalidSignature, UnsupportedAlgorithm):
        return False


def parse_certificate(der: bytes) -> dict:
    """Parse the leaf certificate into database-compatible attributes."""
    cert = x509.load_der_x509_certificate(der)
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        dns, ips = san.get_values_for_type(x509.DNSName), san.get_values_for_type(x509.IPAddress)
    except x509.ExtensionNotFound:
        dns, ips = [], []
    try:
        aia = cert.extensions.get_extension_for_class(x509.AuthorityInformationAccess).value
        has_aia = any(item.access_method == AuthorityInformationAccessOID.CA_ISSUERS for item in aia)
    except x509.ExtensionNotFound:
        has_aia = False
    key = cert.public_key()
    types = [(rsa.RSAPublicKey, "RSA"), (ec.EllipticCurvePublicKey, "EC"),
             (ed25519.Ed25519PublicKey, "Ed25519"), (ed448.Ed448PublicKey, "Ed448"),
             (dsa.DSAPublicKey, "DSA")]
    key_type = next((label for cls, label in types if isinstance(key, cls)), "Unknown")
    return {
        "subject_cn": name_value(cert.subject, NameOID.COMMON_NAME),
        "san_dns": dns, "san_ip": [str(ip) for ip in ips],
        "issuer_cn": name_value(cert.issuer, NameOID.COMMON_NAME),
        "issuer_o": name_value(cert.issuer, NameOID.ORGANIZATION_NAME),
        "serial": format(cert.serial_number, "X"),
        "thumbprint_sha1": cert.fingerprint(hashes.SHA1()).hex().upper(),
        "fingerprint_sha256": cert.fingerprint(hashes.SHA256()).hex().upper(),
        "not_before": cert.not_valid_before_utc, "not_after": cert.not_valid_after_utc,
        "days_left": floor((cert.not_valid_after_utc - datetime.now(timezone.utc)).total_seconds() / 86400),
        "key_type": key_type, "key_size": getattr(key, "key_size", None),
        "signature_algorithm": cert.signature_algorithm_oid._name,
        "has_aia": has_aia, "self_signed": is_self_signed(cert),
    }
