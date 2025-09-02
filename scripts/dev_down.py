#!/usr/bin/env python3
"""
Development Environment Shutdown
Cleanly stops services started by dev_up.py
"""

import os
import sys
import signal
import time
from pathlib import Path
import platform
import psutil

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
PID_DIR = PROJECT_ROOT / ".dev"
API_PID_FILE = PID_DIR / "api.pid"
DASH_PID_FILE = PID_DIR / "dash.pid"
LOGS_DIR = PROJECT_ROOT / "logs" / "dev"


def read_pid(pid_file: Path) -> int:
    """Read PID from file"""
    if not pid_file.exists():
        return None
    
    try:
        with open(pid_file, "r") as f:
            return int(f.read().strip())
    except (ValueError, IOError):
        return None


def is_process_running(pid: int) -> bool:
    """Check if a process is running"""
    try:
        return psutil.pid_exists(pid)
    except:
        # Fallback method if psutil not available
        if platform.system() == "Windows":
            import subprocess
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True
            )
            return str(pid) in result.stdout
        else:
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False


def stop_process(name: str, pid: int) -> bool:
    """Stop a process gracefully"""
    if not is_process_running(pid):
        print(f"  ⚠️  {name} not running (PID: {pid})")
        return True
    
    print(f"  Stopping {name} (PID: {pid})...")
    
    try:
        if platform.system() == "Windows":
            # Windows: Send CTRL_C_EVENT or terminate
            import subprocess
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False)
        else:
            # Unix: Send SIGTERM first, then SIGKILL if needed
            os.kill(pid, signal.SIGTERM)
            
            # Wait for graceful shutdown
            for _ in range(10):  # 5 seconds timeout
                time.sleep(0.5)
                if not is_process_running(pid):
                    print(f"  ✅ {name} stopped gracefully")
                    return True
            
            # Force kill if still running
            print(f"  ⚠️  Force killing {name}")
            os.kill(pid, signal.SIGKILL)
        
        # Verify stopped
        time.sleep(1)
        if not is_process_running(pid):
            print(f"  ✅ {name} stopped")
            return True
        else:
            print(f"  ❌ Failed to stop {name}")
            return False
            
    except Exception as e:
        print(f"  ❌ Error stopping {name}: {e}")
        return False


def kill_orphan_processes():
    """Kill any orphaned uvicorn/python processes on our ports"""
    ports = [8002, 5000]
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'connections']):
            try:
                # Check if process is using our ports
                for conn in proc.connections():
                    if conn.laddr.port in ports and conn.status == 'LISTEN':
                        print(f"  Found orphan process on port {conn.laddr.port} (PID: {proc.pid})")
                        proc.terminate()
                        proc.wait(timeout=5)
                        print(f"  ✅ Killed orphan process {proc.pid}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except ImportError:
        # psutil not available, try netstat
        if platform.system() != "Windows":
            import subprocess
            for port in ports:
                try:
                    result = subprocess.run(
                        ["lsof", "-ti", f":{port}"],
                        capture_output=True,
                        text=True
                    )
                    if result.stdout:
                        pid = int(result.stdout.strip())
                        os.kill(pid, signal.SIGTERM)
                        print(f"  ✅ Killed process on port {port} (PID: {pid})")
                except:
                    pass


def clean_up():
    """Clean up PID files and temporary files"""
    # Remove PID files
    API_PID_FILE.unlink(missing_ok=True)
    DASH_PID_FILE.unlink(missing_ok=True)
    
    # Clean up empty PID directory
    if PID_DIR.exists() and not any(PID_DIR.iterdir()):
        PID_DIR.rmdir()
    
    print("  ✅ Cleaned up PID files")


def main():
    """Main entry point"""
    print("="*60)
    print(" 🛑 SOFIA V2 - Development Environment Shutdown")
    print("="*60)
    
    services_stopped = False
    
    # Stop API
    api_pid = read_pid(API_PID_FILE)
    if api_pid:
        if stop_process("API Server", api_pid):
            services_stopped = True
    else:
        print("  ℹ️  No API PID file found")
    
    # Stop Dashboard
    dash_pid = read_pid(DASH_PID_FILE)
    if dash_pid:
        if stop_process("Dashboard", dash_pid):
            services_stopped = True
    else:
        print("  ℹ️  No Dashboard PID file found")
    
    # Kill any orphaned processes
    print("\n🔍 Checking for orphaned processes...")
    kill_orphan_processes()
    
    # Clean up
    print("\n🧹 Cleaning up...")
    clean_up()
    
    # Final message
    print("\n" + "="*60)
    if services_stopped:
        print(" ✅ Services stopped successfully")
    else:
        print(" ℹ️  No services were running")
    
    if LOGS_DIR.exists():
        print(f"\n📝 Logs preserved in: {LOGS_DIR}")
    
    print("="*60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())