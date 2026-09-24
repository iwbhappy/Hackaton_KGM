"""Normalize text/CSV targets without any network access."""
import csv
import io
import ipaddress
import re
from dataclasses import asdict, dataclass, field
from urllib.parse import urlsplit

MAX_UPLOAD = 1024 * 1024
CRITICALITIES = {"low", "normal", "high", "critical"}


@dataclass
class Target:
    host: str
    port: int = 443
    sni: str | None = None
    owner: str | None = None
    criticality: str | None = None
    service_name: str | None = None


@dataclass
class ParseResult:
    targets: list[Target] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return the JSON API representation."""
        return asdict(self)


def normalize_host(host: str) -> tuple[str, str | None]:
    """Normalize IP literals or IDNA DNS names and select the appropriate SNI."""
    host = host.rstrip(".").lower()
    try:
        return str(ipaddress.ip_address(host)), None
    except ValueError:
        pass
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        raise ValueError("Некорректное DNS-имя") from None
    if len(host) > 253 or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                                 for label in host.split(".")):
        raise ValueError("Некорректное DNS-имя или IP-адрес")
    if re.fullmatch(r"[0-9.]+", host):
        raise ValueError("Некорректный IP-адрес")
    return host, host


def parse_target(value: str, max_cidr_hosts: int = 1024) -> list[Target]:
    """Parse one target or expand one bounded network."""
    value = value.strip()
    if "/" in value and "://" not in value:
        try:
            network = ipaddress.ip_network(value, strict=False)
        except ValueError:
            raise ValueError("Некорректный CIDR-диапазон") from None
        if network.num_addresses > max_cidr_hosts:
            raise ValueError(f"Диапазон превышает лимит {max_cidr_hosts} адресов")
        return [Target(str(ip)) for ip in network.hosts()]
    try:
        # A bare IPv6 address has no port; explicit ports require brackets.
        if value.count(":") > 1 and not value.startswith("[") and "://" not in value:
            return [Target(str(ipaddress.ip_address(value)))]
        url = urlsplit(value if "://" in value else "//" + value)
        if url.scheme and url.scheme.lower() != "https":
            raise ValueError("Поддерживаются только HTTPS URL")
        if url.username is not None or url.password is not None:
            raise ValueError("Учётные данные в адресе запрещены")
        if not url.hostname or any(c.isspace() for c in value):
            raise ValueError("Адрес пустой или содержит пробелы")
        if not url.scheme and (url.path or url.query or url.fragment):
            raise ValueError("Путь допустим только в HTTPS URL")
        port = url.port if url.port is not None else 443
        if not 1 <= port <= 65535 or url.netloc.endswith(":"):
            raise ValueError("Порт должен быть от 1 до 65535")
        host, sni = normalize_host(url.hostname)
        return [Target(host, port, sni)]
    except ValueError as error:
        if "Port" in str(error) or "port" in str(error):
            raise ValueError("Порт должен быть числом от 1 до 65535") from None
        if str(error).startswith(("Invalid", "'")):
            raise ValueError("Некорректный адрес") from None
        raise


def input_rows(text: str, is_csv: bool):
    """Yield (physical line number, target string, metadata) from text or CSV."""
    if not is_csv:
        for number, line in enumerate(text.splitlines(), 1):
            if line.strip() and not line.lstrip().startswith("#"):
                yield number, line, {}
        return
    first = text.splitlines()[0] if text else ""
    reader = csv.DictReader(io.StringIO(text), delimiter=";" if ";" in first else ",", strict=True)
    if not reader.fieldnames or "target" not in reader.fieldnames:
        raise ValueError("CSV должен содержать заголовок target")
    for row in reader:
        if None in row:
            yield reader.line_num, "", {"_error": "Количество столбцов не совпадает с заголовком"}
        else:
            yield reader.line_num, row.get("target") or "", {
                key: (row.get(key) or "").strip() or None
                for key in ("service_name", "owner", "criticality")}


def parse_targets(text: str, filename: str = "", max_cidr_hosts: int = 1024,
                  max_targets: int = 2048) -> ParseResult:
    """Return valid unique targets and localized errors with line numbers."""
    result = ParseResult()
    if len(text.encode("utf-8")) > MAX_UPLOAD:
        return ParseResult(errors=[{"line": 0, "error": "Размер файла превышает 1 МБ"}])
    text = text.lstrip("\ufeff")
    header = text.splitlines()[0] if text else ""
    is_csv = filename.lower().endswith(".csv") or header.split(";")[0].split(",")[0] == "target"
    unique: dict[tuple, Target] = {}
    try:
        for line, value, metadata in input_rows(text, is_csv):
            try:
                if metadata.get("_error"):
                    raise ValueError(metadata["_error"])
                if metadata.get("criticality") and metadata["criticality"] not in CRITICALITIES:
                    raise ValueError("Критичность: low, normal, high или critical")
                if not value.strip():
                    raise ValueError("Не указана цель")
                targets = parse_target(value, max_cidr_hosts)
                added = {(t.host, t.port) for t in targets} - unique.keys()
                if len(unique) + len(added) > max_targets:
                    raise ValueError(f"Превышен лимит {max_targets} целей за сканирование")
                for target in targets:
                    key = (target.host, target.port)
                    target = unique.get(key, target)
                    for attr, value in metadata.items():
                        if value:
                            setattr(target, attr, value)
                    unique[key] = target
            except ValueError as error:
                result.errors.append({"line": line, "error": str(error)})
    except (ValueError, csv.Error) as error:
        message = "Некорректный CSV" if isinstance(error, csv.Error) else str(error)
        result.errors.append({"line": 1, "error": message})
    result.targets = list(unique.values())
    return result
