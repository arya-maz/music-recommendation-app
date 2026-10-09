"""Local install and launcher. Setup never authenticates with Spotify."""
from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"


class SetupError(Exception):
    pass


def venv_python() -> Path:
    return ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def npm_command() -> str:
    node, npm = shutil.which("node"), shutil.which("npm")
    if not node or not npm:
        raise SetupError("Install Node.js 20+ (including npm), then retry.")
    version = subprocess.check_output([node, "--version"], text=True).strip()
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise SetupError("Could not determine your Node.js version.")
    major, minor, _ = map(int, match.groups())
    if major < 20:
        raise SetupError("Use Node.js 20+; a supported LTS version is recommended.")
    return npm


def create_environment() -> bool:
    """Create a private config once; never read or replace an existing config."""
    template = (ROOT / ".env.example").read_text(encoding="utf-8")
    key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    template = template.replace("generate_during_setup", key)
    try:
        descriptor = os.open(ROOT / ".env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "w", encoding="utf-8") as config:
        config.write(template)
    return True


def setup() -> None:
    if not (3, 12) <= sys.version_info[:2] < (3, 13):
        raise SetupError("Run setup with Python 3.12 to match the supported dependency versions.")
    npm = npm_command()
    interpreter = venv_python()
    if not interpreter.exists():
        print("Creating the local Python environment...", flush=True)
        subprocess.run([sys.executable, "-m", "venv", str(ROOT / ".venv")], check=True)
    else:
        version = subprocess.check_output(
            [str(interpreter), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
            text=True,
        ).strip()
        if version != "3.12":
            raise SetupError("The existing .venv uses a different Python version. Use Python 3.12 in a fresh clone.")
    print("Installing application dependencies...", flush=True)
    subprocess.run([str(interpreter), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], check=True, cwd=ROOT)
    subprocess.run([str(interpreter), "-m", "pip", "check"], check=True, cwd=ROOT)
    subprocess.run([npm, "ci"], check=True, cwd=FRONTEND)
    if create_environment():
        print("Created .env with a local encryption key. Add your Spotify Client ID and Client Secret.")
    else:
        print("Existing .env preserved, including its encryption key and configuration.")
    print("Setup complete. Next: python manage.py run\nSee README.md for Spotify dashboard setup.")


def validate_configuration(interpreter: Path) -> None:
    # Read credentials only in the application environment. Never print their values.
    validation = """
import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet
load_dotenv('.env')
missing = [name for name in ('SPOTIFY_CLIENT_ID', 'SPOTIFY_CLIENT_SECRET')
           if not os.getenv(name) or os.getenv(name).startswith('your_')]
if missing:
    print('Edit .env and fill in: ' + ', '.join(missing))
    raise SystemExit(1)
try:
    Fernet(os.environ['SPOTIFY_TOKEN_ENCRYPTION_KEY'].encode('ascii'))
except (KeyError, ValueError, TypeError, UnicodeError):
    print('A valid SPOTIFY_TOKEN_ENCRYPTION_KEY is required; see README.md.')
    raise SystemExit(1)
expected = {
    'SPOTIFY_REDIRECT_URI': 'http://127.0.0.1:8000/api/auth/callback',
    'FRONTEND_AUTH_SUCCESS_URL': 'http://127.0.0.1:5173/',
    'FRONTEND_ORIGIN': 'http://127.0.0.1:5173',
}
incorrect = [name for name, value in expected.items() if os.getenv(name) != value]
if incorrect or os.getenv('APP_COOKIE_SECURE', 'true').lower() not in ('false', '0', 'no'):
    print('This launcher requires the local URLs and APP_COOKIE_SECURE=false from .env.example.')
    print('Use the manual commands in README.md for a custom configuration.')
    raise SystemExit(1)
"""
    subprocess.run([str(interpreter), "-c", validation], check=True, cwd=ROOT)


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def run() -> None:
    interpreter = venv_python()
    if not interpreter.exists() or not (FRONTEND / "node_modules").is_dir():
        raise SetupError("Run python manage.py setup first.")
    npm_command()
    validate_configuration(interpreter)
    for port in (8000, 5173):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                raise SetupError(f"Port {port} is already in use. Stop the existing service and retry.") from None
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    processes = []
    try:
        processes.append(subprocess.Popen(
            [str(interpreter), "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000", "--env-file", str(ROOT / ".env")],
            cwd=ROOT, env=environment,
        ))
        # Invoke Vite directly so shutdown manages the server rather than an npm wrapper.
        processes.append(subprocess.Popen(
            [shutil.which("node"), str(FRONTEND / "node_modules/vite/bin/vite.js"), "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
            cwd=FRONTEND,
        ))
        print("Starting Liner Notes at http://127.0.0.1:5173\nPress Ctrl+C to stop both services.", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(0.2)
        raise SetupError("A service stopped unexpectedly. Check its output above.")
    except KeyboardInterrupt:
        print("\nStopping Liner Notes...")
    finally:
        for process in reversed(processes):
            stop_process(process)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install or run Liner Notes locally.")
    parser.add_argument("command", choices=("setup", "run"))
    args = parser.parse_args()
    try:
        {"setup": setup, "run": run}[args.command]()
    except SetupError as error:
        print(str(error), file=sys.stderr)
        return 1
    except subprocess.CalledProcessError:
        print("A required command failed. Check the message above and retry.", file=sys.stderr)
        return 1
    except OSError:
        print("Could not access a required file or start a command. Check your installation and permissions.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nSetup interrupted. You can rerun it.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
