"""Validate and store public root certificates under safe generated filenames."""
import re
from pathlib import Path

from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.oid import NameOID

from app.config import settings


def load_ca(data: bytes) -> x509.Certificate:
    """Accept one PEM/DER CA certificate, excluding private keys and leaf certificates."""
    if b"PRIVATE KEY" in data:
        raise ValueError("Загружайте только публичный сертификат CA, без закрытого ключа")
    try:
        if b"-----BEGIN" in data:
            certificates = x509.load_pem_x509_certificates(data)
            if len(certificates) != 1:
                raise ValueError("Ожидается один корневой сертификат")
            cert = certificates[0]
        else:
            cert = x509.load_der_x509_certificate(data)
        if not cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
            raise ValueError("Это не сертификат CA")
        if cert.subject != cert.issuer:
            raise ValueError("Загрузите корневой CA, а не промежуточный сертификат")
        cert.verify_directly_issued_by(cert)
        return cert
    except (ValueError, TypeError, x509.ExtensionNotFound, InvalidSignature, UnsupportedAlgorithm):
        raise ValueError("Нужен корректный самоподписанный корневой сертификат CA в PEM или DER") from None


def ca_info(path: Path) -> dict:
    """Show public certificate metadata without disclosing filesystem paths."""
    try:
        cert = load_ca(path.read_bytes())
        attributes = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        return {"name": path.name, "cn": attributes[0].value if attributes else cert.subject.rfc4514_string(),
                "not_after": cert.not_valid_after_utc.isoformat(), "fingerprint": cert.fingerprint(hashes.SHA256()).hex().upper()}
    except (OSError, ValueError):
        return {"name": path.name, "cn": "Не удалось прочитать CA", "not_after": None, "error": "Некорректный сертификат"}


def save_ca(data: bytes) -> dict:
    """Convert DER to PEM and persist a certificate by its SHA-256 fingerprint."""
    cert = load_ca(data)
    path = settings.trusted_ca_dir / (cert.fingerprint(hashes.SHA256()).hex() + ".pem")
    if path.is_symlink():
        raise ValueError("Небезопасное имя файла")
    settings.trusted_ca_dir.mkdir(parents=True, exist_ok=True)
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return ca_info(path)


def delete_ca(name: str) -> None:
    """Remove only a direct non-symlink certificate from the configured trust folder."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}\.(pem|crt|cer)", name, re.IGNORECASE):
        raise ValueError("Некорректное имя сертификата")
    path = settings.trusted_ca_dir / name
    if path.is_symlink() or path.resolve().parent != settings.trusted_ca_dir.resolve():
        raise ValueError("Некорректный путь сертификата")
    path.unlink()
