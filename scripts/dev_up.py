#!/usr/bin/env python3
"""
Development Environment Launcher
Starts API and Dashboard simultaneously with health checks
"""

import io
import os
import platform
import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import requests

# Set UTF-8 encoding for Windows
if platform.system() == "Windows":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Configuration
API_PORT = int(os.getenv("API_PORT", "8002"))
DASH_PORT = int(os.getenv("DASH_PORT", "5000"))
HEALTH_TIMEOUT = 60  # seconds
HEALTH_RETRY_DELAY = 2  # seconds

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / "logs" / "dev"
PID_DIR = PROJECT_ROOT / ".dev"
API_PID_FILE = PID_DIR / "api.pid"
DASH_PID_FILE = PID_DIR / "dash.pid"

# Process handles
processes = {}


def setup_directories():
    """Create necessary directories"""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    PID_DIR.mkdir(parents=True, exist_ok=True)


def get_python_command():
    """Get the correct Python command for the platform"""
    if platform.system() == "Windows":
        # Try to use venv Python if available
        venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
        if venv_python.exists():
            return str(venv_python)
        venv_python = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
        if venv_python.exists():
            return str(venv_python)
    else:
        # Unix-like systems
        venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
        if venv_python.exists():
            return str(venv_python)
        venv_python = PROJECT_ROOT / "venv" / "bin" / "python"
        if venv_python.exists():
            return str(venv_python)

    # Fallback to system Python
    return sys.executable


def start_api():
    """Start the FastAPI server"""
    print(f"[>] Starting API server on port {API_PORT}...")

    python_cmd = get_python_command()

    # Check if src.api.main exists, otherwise try alternatives
    api_modules = ["src.api.main", "src.web.app", "sofia_ui.server", "api.main"]

    api_module = None
    for module in api_modules:
        module_file = module.replace(".", "/").replace("/", os.sep) + ".py"
        module_path = PROJECT_ROOT / module_file
        if module_path.exists():
            api_module = module
            print(f"  Found API module: {module}")
            break

    if not api_module:
        print("  [WARN] No API module found, trying default src.api.main")
        api_module = "src.api.main"

    cmd = [
        python_cmd,
        "-m",
        "uvicorn",
        f"{api_module}:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(API_PORT),
        "--reload",
    ]

    with (
        open(LOGS_DIR / "api.out.log", "w") as stdout,
        open(LOGS_DIR / "api.err.log", "w") as stderr,
    ):
        process = subprocess.Popen(
            cmd,
            stdout=stdout,
            stderr=stderr,
            cwd=PROJECT_ROOT,
            env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        )

        processes["api"] = process
        API_PID_FILE.write_text(str(process.pid))
        print(f"  [OK] API started (PID: {process.pid})")
        return process


def start_dashboard():
    """Start the Dashboard server"""
    print(f"[>] Starting Dashboard on port {DASH_PORT}...")

    python_cmd = get_python_command()

    # Check for dashboard server files
    dashboard_files = [
        "dashboard_server.py",
        "sofia_ui/server.py",
        "src/web/dashboard.py",
        "run_web_ui.py",
    ]

    dashboard_script = None
    for file in dashboard_files:
        script_path = PROJECT_ROOT / file
        if script_path.exists():
            dashboard_script = file
            print(f"  Found dashboard script: {file}")
            break

    if not dashboard_script:
        print("  [WARN] No dashboard script found, trying default dashboard_server.py")
        dashboard_script = "dashboard_server.py"

    cmd = [python_cmd, dashboard_script, "--port", str(DASH_PORT)]

    with (
        open(LOGS_DIR / "dash.out.log", "w") as stdout,
        open(LOGS_DIR / "dash.err.log", "w") as stderr,
    ):
        process = subprocess.Popen(
            cmd,
            stdout=stdout,
            stderr=stderr,
            cwd=PROJECT_ROOT,
            env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        )

        processes["dashboard"] = process
        DASH_PID_FILE.write_text(str(process.pid))
        print(f"  [OK] Dashboard started (PID: {process.pid})")
        return process


def check_health(name: str, url: str, timeout: int = HEALTH_TIMEOUT) -> bool:
    """Check if a service is healthy"""
    print(f"[?] Checking {name} health at {url}...")

    start_time = time.time()
    last_error = None

    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code in [200, 404]:  # 404 is ok for root paths
                print(f"  [OK] {name} is healthy (status: {response.status_code})")
                return True
        except requests.exceptions.ConnectionError:
            last_error = "Connection refused"
        except requests.exceptions.Timeout:
            last_error = "Request timeout"
        except Exception as e:
            last_error = str(e)

        # Check if process is still running
        if name.lower() in processes:
            process = processes[name.lower()]
            if process.poll() is not None:
                print(f"  [ERROR] {name} process died (exit code: {process.poll()})")
                # Check error log
                err_log = LOGS_DIR / f"{name.lower()[:4]}.err.log"
                if err_log.exists():
                    with open(err_log) as f:
                        last_lines = f.readlines()[-10:]
                        if last_lines:
                            print("  Last error output:")
                            for line in last_lines:
                                print(f"    {line.rstrip()}")
                return False

        time.sleep(HEALTH_RETRY_DELAY)

    print(f"  [ERROR] {name} health check failed after {timeout}s")
    if last_error:
        print(f"  Last error: {last_error}")
    return False


def open_browsers():
    """Open the development URLs in browser"""
    urls = [f"http://localhost:{API_PORT}/dev", f"http://localhost:{DASH_PORT}/"]

    print("\n[BROWSER] Opening browsers...")
    for url in urls:
        print(f"  Opening: {url}")
        webbrowser.open(url)


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print("\n\n[STOP] Shutting down services...")

    for name, process in processes.items():
        if process and process.poll() is None:
            print(f"  Stopping {name} (PID: {process.pid})...")
            if platform.system() == "Windows":
                process.terminate()
            else:
                process.send_signal(signal.SIGTERM)

            # Wait for graceful shutdown
            try:
                process.wait(timeout=5)
                print(f"  [OK] {name} stopped")
            except subprocess.TimeoutExpired:
                print(f"  [WARN]  Force killing {name}")
                process.kill()

    # Clean up PID files
    API_PID_FILE.unlink(missing_ok=True)
    DASH_PID_FILE.unlink(missing_ok=True)

    print("\n[EXIT] Goodbye!")
    sys.exit(0)


def main():
    """Main entry point"""
    # Set UTF-8 encoding for Windows
    if platform.system() == "Windows":
        import codecs

        if sys.stdout.encoding != "utf-8":
            sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        if sys.stderr.encoding != "utf-8":
            sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    print("=" * 60)
    print(" [LAUNCH] SOFIA V2 - Development Environment Launcher")
    print("=" * 60)
    print(f"API Port: {API_PORT}")
    print(f"Dashboard Port: {DASH_PORT}")
    print(f"Logs: {LOGS_DIR}")
    print("=" * 60)

    # Setup
    setup_directories()

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start services
    try:
        api_process = start_api()
        time.sleep(2)  # Give API a head start

        dash_process = start_dashboard()

        print("\n[WAIT] Waiting for services to be ready...")

        # Health checks
        api_healthy = check_health("API", f"http://127.0.0.1:{API_PORT}/api/dev/status")

        # If API dev endpoint doesn't exist, try root
        if not api_healthy:
            print("  Trying API root endpoint...")
            api_healthy = check_health("API", f"http://127.0.0.1:{API_PORT}/")

        dash_healthy = check_health("Dashboard", f"http://127.0.0.1:{DASH_PORT}/")

        if api_healthy and dash_healthy:
            print("\n[OK] All services are ready!")

            # Open browsers
            open_browsers()

            # Print access info
            print("\n" + "=" * 60)
            print(" [READY] Development Environment Ready!")
            print("=" * 60)
            print(f"[API]       http://localhost:{API_PORT}/dev")
            print(f"[DASHBOARD] http://localhost:{DASH_PORT}/")
            print(f"[LOGS] API Logs:  {LOGS_DIR}/api.*.log")
            print(f"[LOGS] Dash Logs: {LOGS_DIR}/dash.*.log")
            print("\n[INFO] Press Ctrl+C to stop all services")
            print("=" * 60)

            # Keep running
            while True:
                time.sleep(1)
                # Check if processes are still alive
                for name, process in processes.items():
                    if process.poll() is not None:
                        print(f"\n[WARN]  {name} died unexpectedly!")
                        signal_handler(None, None)
        else:
            print("\n[ERROR] Service startup failed!")
            if not api_healthy:
                print("  - API failed to start")
            if not dash_healthy:
                print("  - Dashboard failed to start")

            print("\n[LOGS] Check logs for details:")
            print(f"  - {LOGS_DIR}/api.err.log")
            print(f"  - {LOGS_DIR}/dash.err.log")

            signal_handler(None, None)

    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        signal_handler(None, None)


if __name__ == "__main__":
    main()
