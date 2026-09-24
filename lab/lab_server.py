"""Threaded HTTPS laboratory with one certificate context per SNI name."""
import argparse
import socketserver
import ssl
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def contexts(folder: Path) -> dict[str, ssl.SSLContext]:
    """Load fixture contexts, including the deliberately weak certificate."""
    result = {}
    for path in folder.glob("*.fullchain.pem"):
        name = path.name.removesuffix(".fullchain.pem")
        if name.endswith("ca"):
            continue
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        if name == "weak":
            try:
                ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
            except ssl.SSLError:
                warnings.warn("Слабые сертификаты не поддерживаются этой сборкой OpenSSL")
                continue
        try:
            ctx.load_cert_chain(str(path), str(folder / f"{name}.key"))
        except ssl.SSLError:
            if name != "weak":
                raise
            warnings.warn("Сертификат weak пропущен: OpenSSL запрещает слабую подпись")
            continue
        result[f"{name}.lab.local"] = ctx
    return result


class LabHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        """Perform TLS in a worker so an idle client cannot block other handshakes."""
        try:
            self.request.settimeout(5)
            with self.server.default_context.wrap_socket(self.request, server_side=True) as tls:
                if tls.recv(4096).startswith(b"GET "):
                    name = getattr(tls, "lab_name", "valid.lab.local")
                    body = f"<!doctype html><h1>Lab service: {name}</h1>".encode()
                    tls.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
                                + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode() + body)
        except (ssl.SSLError, OSError):
            pass  # Verification clients intentionally disconnect on invalid certificates.


class LabServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: tuple, folder: Path):
        self.contexts = contexts(folder)
        self.default_context = self.contexts["valid.lab.local"]
        self.default_context.sni_callback = self.select_sni
        super().__init__(address, LabHandler)

    def select_sni(self, tls, name, _initial) -> int | None:
        """Select a known laboratory service, rejecting unknown SNI names."""
        if name and name not in self.contexts:
            return ssl.ALERT_DESCRIPTION_UNRECOGNIZED_NAME
        tls.context = self.contexts.get(name, self.default_context)
        tls.lab_name = name or "valid.lab.local"
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Локальный TLS-стенд")
    parser.add_argument("--port", type=int, default=443)
    parser.add_argument("--bind", default="127.0.0.1", help="127.0.0.1 сохраняет dead.lab.local недоступным")
    parser.add_argument("--certs", type=Path, default=ROOT / "lab/certs")
    args = parser.parse_args()
    try:
        server = LabServer((args.bind, args.port), args.certs)
    except PermissionError:
        if args.port != 443:
            raise
        print("Нет прав на порт 443; используется 8443. Укажите :8443 в целях.")
        server = LabServer((args.bind, 8443), args.certs)
    with server:
        print(f"Стенд: {server.server_address}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
