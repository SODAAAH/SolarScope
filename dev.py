import os
import sys
import time
import signal
import subprocess

def kill_pid(pid: int):
    try:
        subprocess.call(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

def free_port(port: int):
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8", errors="ignore")
        pids = set()
        for line in out.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.strip().split()
                if parts and parts[-1].isdigit():
                    pids.add(int(parts[-1]))
        for pid in pids:
            if pid != os.getpid():
                kill_pid(pid)
    except Exception:
        pass

def main():
    free_port(8000)
    free_port(5173)

    root = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(root, "frontend")
    vite_bin = os.path.join(frontend_dir, "node_modules", "vite", "bin", "vite.js")

    backend_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--reload"
    ]

    if os.path.exists(vite_bin):
        frontend_cmd = ["node", vite_bin]
    else:
        frontend_cmd = ["npm", "run", "dev"]

    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=root,
        stdin=subprocess.DEVNULL
    )
    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=frontend_dir,
        stdin=subprocess.DEVNULL
    )

    def cleanup(signum=None, frame=None):
        if backend_proc and backend_proc.poll() is None:
            kill_pid(backend_proc.pid)
        if frontend_proc and frontend_proc.poll() is None:
            kill_pid(frontend_proc.pid)
        free_port(8000)
        free_port(5173)
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        while True:
            time.sleep(1.0)
            if backend_proc.poll() is not None:
                backend_proc = subprocess.Popen(
                    backend_cmd,
                    cwd=root,
                    stdin=subprocess.DEVNULL
                )
            if frontend_proc.poll() is not None:
                frontend_proc = subprocess.Popen(
                    frontend_cmd,
                    cwd=frontend_dir,
                    stdin=subprocess.DEVNULL
                )
    except KeyboardInterrupt:
        cleanup()
    finally:
        cleanup()

if __name__ == "__main__":
    main()
