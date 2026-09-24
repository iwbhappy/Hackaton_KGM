"""Install dependencies once; subsequent starts require no network."""
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    """Use an optional local wheelhouse and skip pip when requirements are unchanged."""
    if sys.version_info < (3, 11):
        print("Требуется Python 3.11 или новее")
        return 1
    requirements = ROOT / "requirements.txt"
    marker = ROOT / ".venv/.requirements.sha256"
    fingerprint = hashlib.sha256(requirements.read_bytes()).hexdigest()
    if marker.exists() and marker.read_text(encoding="ascii") == fingerprint:
        return 0
    command = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--quiet", "-r", str(requirements)]
    wheels = ROOT / "wheelhouse"
    if wheels.is_dir():
        command.extend(["--no-index", "--find-links", str(wheels)])
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode == 0:
        marker.write_text(fingerprint, encoding="ascii")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
