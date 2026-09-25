"""Two read-only TLS handshakes: observation followed by trust verification."""
import argparse
import json
import socket
import ssl
import warnings
from dataclasses import asdict
from pathlib import Path

from app.analysis.cert_parser import parse_certificate
from app.analysis.hostname import match_hostname
from app.collectors.base import BaseCollector, RawObservation
from app.config import settings
from app.parser import Target, parse_targets

CHAIN_CODES = {18: "self_signed", 19: "untrusted_root", 20: "incomplete_or_untrusted",
               21: "incomplete_or_untrusted", 10: "valid_but_expired", 9: "not_yet_valid"}


def network_error(error: Exception) -> str:
    """Translate connection errors without exposing connection credentials."""
    if isinstance(error, socket.gaierror):
        return "DNS-имя не разрешается"
    if isinstance(error, (TimeoutError, socket.timeout)):
        return "Таймаут подключения"
    if isinstance(error, ConnectionRefusedError):
        return "Порт закрыт"
    if isinstance(error, ssl.SSLError):
        return "Сервис не поддерживает TLS или TLS-рукопожатие отклонено"
    return "Не удалось подключиться к сервису"


def observation_context() -> ssl.SSLContext:
    """Allow inspection of expired, untrusted and legacy certificates."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            ctx.minimum_version = ssl.TLSVersion.TLSv1
        ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
    except (ssl.SSLError, ValueError):
        pass
    return ctx


class TLSCollector(BaseCollector):
    def __init__(self, timeout: float = 4, trust_dir: Path | None = None,
                 connect_host: str | None = None):
        self.timeout = timeout
        self.trust_dir = trust_dir if trust_dir is not None else settings.trusted_ca_dir
        self.connect_host = connect_host

    def collect(self, target: Target) -> RawObservation:
        """Retrieve the leaf regardless of trust, then verify it separately."""
        observation = RawObservation()
        try:
            with socket.create_connection((self.connect_host or target.host, target.port), self.timeout) as raw:
                with observation_context().wrap_socket(raw, server_hostname=target.sni) as tls:
                    observation.der = tls.getpeercert(binary_form=True)
                    observation.tls_version = tls.version()
                    observation.resolved_ip = tls.getpeername()[0]
                    observation.reachable = bool(observation.der)
        except OSError as error:
            observation.error = network_error(error)
            return observation
        self.verify(target, observation)
        return observation

    def verification_context(self, legacy: bool) -> ssl.SSLContext:
        """Require a trusted chain, optionally allowing legacy TLS and cryptography."""
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_REQUIRED
        for path in sorted(self.trust_dir.glob("*")):
            if path.suffix.lower() in {".pem", ".crt", ".cer"}:
                ctx.load_verify_locations(cafile=str(path))
        if legacy:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    ctx.minimum_version = ssl.TLSVersion.TLSv1
                ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
            except (ssl.SSLError, ValueError):
                pass
        return ctx

    def verify(self, target: Target, observation: RawObservation) -> None:
        """Verify trust on the same IP, retrying only TLS/security-policy failures."""
        original_rejection = None
        for legacy in (False, True):
            try:
                ctx = self.verification_context(legacy)
                with socket.create_connection((observation.resolved_ip, target.port), self.timeout) as raw:
                    with ctx.wrap_socket(raw, server_hostname=target.sni) as tls:
                        if tls.getpeercert(binary_form=True) != observation.der:
                            observation.chain_status = "error"
                            observation.chain_message = "Сертификат изменился между двумя подключениями"
                        else:
                            observation.chain_status = "valid"
                            observation.chain_message = "Цепочка доверена"
            except ssl.SSLCertVerificationError as error:
                if not legacy and error.verify_code in {66, 67, 68}:
                    original_rejection = error.verify_message
                    continue
                observation.chain_status = CHAIN_CODES.get(error.verify_code, "error")
                observation.chain_message = error.verify_message
            except ssl.SSLError as error:
                if not legacy:
                    continue
                observation.chain_status = "error"
                observation.chain_message = "Проверка доверия не выполнена: " + network_error(error)
            except OSError as error:
                observation.chain_status = "error"
                observation.chain_message = "Проверка доверия не выполнена: " + network_error(error)
            if legacy:
                observation.chain_message += (
                    "; проверено с пониженным уровнем безопасности OpenSSL "
                    "(устаревший TLS или слабая криптография)"
                )
                if original_rejection:
                    observation.chain_message += "; по умолчанию отклонено: " + original_rejection
            break


def result_attributes(observation: RawObservation, host: str) -> dict:
    """Combine the raw observation with parsed certificate attributes."""
    data = asdict(observation)
    data.pop("der")
    data["hostname_match"] = "not_checked"
    if observation.der:
        data.update(parse_certificate(observation.der))
        matched = match_hostname(host, data["san_dns"], data["san_ip"], data["subject_cn"])
        data["hostname_match"] = "match" if matched else "mismatch"
        if data["chain_status"] == "incomplete_or_untrusted" and data["has_aia"] and not data["self_signed"]:
            data["chain_message"] += "; вероятно, сервер не отдаёт промежуточный сертификат"
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Получить TLS-сертификат и проверить доверие")
    parser.add_argument("target")
    parser.add_argument("--connect-host", help="IP для локальной диагностики без изменения hosts")
    parser.add_argument("--trust", type=Path, default=settings.trusted_ca_dir)
    args = parser.parse_args()
    parsed = parse_targets(args.target)
    if parsed.errors or len(parsed.targets) != 1:
        parser.error("Укажите одну корректную цель")
    target = parsed.targets[0]
    collector = TLSCollector(trust_dir=args.trust, connect_host=args.connect_host)
    print(json.dumps(result_attributes(collector.collect(target), target.host), ensure_ascii=False, default=str, indent=2))
