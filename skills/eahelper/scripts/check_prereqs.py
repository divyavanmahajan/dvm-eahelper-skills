#!/usr/bin/env python3
"""Cross-platform prerequisite checker for the eahelper skill.

Checks (in order):
  1. Python version (3.11+)
  2. `uv` on PATH
  3. `dvm-eahelper` installed (via `uv tool list` or `eahelper` on PATH)
  4. Playwright Chromium browser installed
  5. Port 9222 (Chrome/Edge debug port) reachability - informational only

Works identically on Windows and macOS/Linux. Uses only the standard library
so it runs with plain `python check_prereqs.py` before any project
dependencies are installed. No POSIX-only calls (no os.fork, no shutil.which
assumptions about executable bits, etc.) - uses pathlib and shutil.which,
both cross-platform.

Usage:
    python check_prereqs.py
    python3 check_prereqs.py
"""

from __future__ import annotations

import json
import platform
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

MIN_PYTHON = (3, 11)
DEBUG_PORT = 9222
PROXY_PORT = 8765

CHECK = "[OK]  "
WARN = "[WARN]"
FAIL = "[FAIL]"
INFO = "[INFO]"


def _print_result(status: str, label: str, detail: str = "") -> None:
    line = f"{status} {label}"
    if detail:
        line += f" - {detail}"
    print(line)


def check_python_version() -> bool:
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    if (version.major, version.minor) >= MIN_PYTHON:
        _print_result(CHECK, "Python version", f"{version_str} (>= {MIN_PYTHON[0]}.{MIN_PYTHON[1]} required)")
        return True
    _print_result(
        FAIL,
        "Python version",
        f"{version_str} found, but {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required. "
        f"Install a newer Python from https://www.python.org/downloads/",
    )
    return False


def _run(cmd: list[str]) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return 127, "", "not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timed out"


def check_uv() -> bool:
    uv_path = shutil.which("uv")
    if not uv_path:
        _print_result(
            FAIL,
            "uv",
            "not found on PATH. Install with:\n"
            '       macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh\n'
            '       Windows:     powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"',
        )
        return False
    code, out, _err = _run(["uv", "--version"])
    if code == 0:
        _print_result(CHECK, "uv", f"{out} ({uv_path})")
        return True
    _print_result(WARN, "uv", f"found at {uv_path} but `uv --version` failed")
    return False


def check_dvm_eahelper() -> bool:
    # Prefer checking `eahelper` directly on PATH (works for `uv tool install`).
    eahelper_path = shutil.which("eahelper")
    if eahelper_path:
        code, out, _err = _run(["eahelper", "--help"])
        if code == 0:
            _print_result(CHECK, "dvm-eahelper", f"eahelper found on PATH ({eahelper_path})")
            return True
        _print_result(WARN, "dvm-eahelper", f"eahelper found at {eahelper_path} but --help failed")

    # Fall back to `uv tool list` to see if it's installed as a uv tool.
    code, out, _err = _run(["uv", "tool", "list"])
    if code == 0 and "dvm-eahelper" in out:
        _print_result(CHECK, "dvm-eahelper", "installed via `uv tool install`")
        return True

    _print_result(
        FAIL,
        "dvm-eahelper",
        "not found. Install with:\n"
        "       uv tool install dvm-eahelper\n"
        "       (or run ad-hoc with: uvx dvm-eahelper -- --help)",
    )
    return False


def check_playwright_chromium() -> bool:
    # Playwright stores browsers under a versioned cache dir. Rather than
    # guess the exact path (it varies by Playwright version), ask Playwright
    # itself via a short Python subprocess, if the `playwright` package is
    # importable in this interpreter. This is best-effort: eahelper may
    # bundle its own environment (e.g. via `uv tool`), in which case this
    # check cannot see it and will fall back to a heuristic directory scan.
    code, out, _err = _run([sys.executable, "-c", "import playwright; print(playwright.__file__)"])
    if code == 0:
        code2, out2, _err2 = _run(
            [sys.executable, "-m", "playwright", "install", "--dry-run", "chromium"]
        )
        # `--dry-run` support varies by version; treat any zero exit as good news,
        # and fall through to the cache-dir heuristic otherwise.
        if code2 == 0:
            _print_result(CHECK, "Playwright Chromium", "playwright module found and reports chromium available")
            return True

    # Heuristic: look for a chromium-* folder in the standard Playwright cache locations.
    system = platform.system()
    if system == "Windows":
        cache_root = Path.home() / "AppData" / "Local" / "ms-playwright"
    elif system == "Darwin":
        cache_root = Path.home() / "Library" / "Caches" / "ms-playwright"
    else:
        cache_root = Path.home() / ".cache" / "ms-playwright"

    if cache_root.exists():
        chromium_dirs = sorted(cache_root.glob("chromium-*"))
        if chromium_dirs:
            _print_result(CHECK, "Playwright Chromium", f"found in {cache_root}")
            return True

    _print_result(
        WARN,
        "Playwright Chromium",
        "could not confirm install. If `eahelper proxy` fails with a Playwright "
        "'executable doesn't exist' error, run:\n"
        "       uv tool run --from dvm-eahelper playwright install chromium",
    )
    return False


def check_port(port: int, label: str) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.5)
        result = sock.connect_ex(("127.0.0.1", port))
    if result == 0:
        # Port is open - try to confirm it's actually a CDP endpoint (for 9222).
        if port == DEBUG_PORT:
            try:
                with urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2) as resp:
                    data = json.loads(resp.read().decode())
                    browser = data.get("Browser", "unknown browser")
                    _print_result(CHECK, label, f"open and responding as a CDP endpoint ({browser})")
                    return True
            except (urllib.error.URLError, OSError, json.JSONDecodeError):
                _print_result(WARN, label, "port is open but did not respond like a CDP debug endpoint")
                return False
        _print_result(CHECK, label, "open")
        return True

    _print_result(
        INFO,
        label,
        "not open (expected until you launch the debug browser - see references/browser-setup.md)",
    )
    return False


def main() -> int:
    print("eahelper prerequisite check")
    print(f"Platform: {platform.system()} {platform.release()} ({platform.machine()})")
    print("-" * 70)

    results = {
        "python": check_python_version(),
        "uv": check_uv(),
        "dvm_eahelper": check_dvm_eahelper(),
        "playwright_chromium": check_playwright_chromium(),
    }

    print("-" * 70)
    check_port(DEBUG_PORT, f"Chrome/Edge debug port ({DEBUG_PORT})")
    check_port(PROXY_PORT, f"eahelper proxy port ({PROXY_PORT})")

    print("-" * 70)
    required = ["python", "uv", "dvm_eahelper"]
    missing_required = [name for name in required if not results[name]]

    if not missing_required and results["playwright_chromium"]:
        print("All prerequisites look good. Next: launch the debug browser (references/browser-setup.md)")
        return 0
    if not missing_required:
        print("Core prerequisites OK. Playwright Chromium could not be confirmed - see warning above.")
        return 0

    print(f"Missing required prerequisites: {', '.join(missing_required)}")
    print("See references/install.md for install commands.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
