"""Start the local backend safely, or reuse the existing Interview Bot server."""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
from urllib.error import URLError
from urllib.request import urlopen

BACKEND = Path(__file__).resolve().parent
URL = "http://127.0.0.1:8000"


def backend_is_running():
    try:
        with urlopen(f"{URL}/health", timeout=2) as response:
            healthy = json.load(response).get("status") == "ok"
        with urlopen(f"{URL}/openapi.json", timeout=2) as response:
            schema = json.load(response)
        return healthy and schema.get("info", {}).get("title", "").startswith("Interview Bot") and "/api/interviews" in schema.get("paths", {})
    except (URLError, OSError, ValueError, AttributeError):
        return False


def port_available():
    try:
        with socket.socket() as listener:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            listener.bind(("127.0.0.1", 8000))
        return True
    except OSError:
        return False


def main(reload=False):
    if backend_is_running():
        print(f"Interview Bot is already running at {URL}. Reusing it; no second server is needed.")
        print("Open the frontend and continue. To load backend code changes, stop its original terminal with Ctrl+C first.")
        return 0
    if not port_available():
        print("Port 8000 is occupied by another process or blocked/reserved by Windows.")
        print("No process was stopped. Check the owner with: netstat -ano | findstr :8000")
        print("If an earlier backend is still starting, wait and run this command again.")
        print("For reserved ports, check: netsh interface ipv4 show excludedportrange protocol=tcp")
        return 1
    command = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]
    if reload:
        command.append("--reload")
    print(f"Starting Interview Bot at {URL}. Keep this terminal open. Stop with Ctrl+C.", flush=True)
    try:
        result = subprocess.call(command, cwd=BACKEND)
    except KeyboardInterrupt:
        return 0
    # Another launcher may have won the port between our check and startup.
    if result and backend_is_running():
        print(f"Interview Bot is running at {URL}; use the existing server.")
        return 0
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reload", action="store_true", help="Reload on Python changes; omit during a demo.")
    raise SystemExit(main(parser.parse_args().reload))
