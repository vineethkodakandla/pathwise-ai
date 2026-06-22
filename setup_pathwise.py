"""
PathWise AI — one-shot environment installer & checker.

Usage:
    python setup_pathwise.py          # check + install everything
    python setup_pathwise.py --check  # check only (no installs)

Covers:
  - Python version (>= 3.11)
  - Python deps from requirements.txt
  - Node.js + npm (>= 18)
  - Frontend deps from frontend/package.json
  - Optional: Docker, WSL2 (Mininet), Batfish container

Works on Windows / macOS / Linux.
"""
from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
REQ_FILE = ROOT / "requirements.txt"
FRONTEND = ROOT / "frontend"

GREEN = "\033[92m"; YELLOW = "\033[93m"; RED = "\033[91m"; DIM = "\033[2m"; END = "\033[0m"
if platform.system() == "Windows":
    import os
    os.system("")  # enable ANSI on Windows terminals


def ok(msg: str) -> None:   print(f"{GREEN}[OK]{END}   {msg}")
def warn(msg: str) -> None: print(f"{YELLOW}[WARN]{END} {msg}")
def err(msg: str) -> None:  print(f"{RED}[FAIL]{END} {msg}")
def info(msg: str) -> None: print(f"{DIM}[..]{END}   {msg}")


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    # On Windows, node/npm are .cmd shims — invoke via shell.
    use_shell = platform.system() == "Windows"
    call = " ".join(cmd) if use_shell else cmd
    return subprocess.run(call, check=check, capture_output=True,
                          text=True, shell=use_shell)


def have(binary: str) -> str | None:
    return shutil.which(binary)


def check_python() -> bool:
    v = sys.version_info
    if (v.major, v.minor) < (3, 11):
        err(f"Python {v.major}.{v.minor} detected — need >= 3.11")
        return False
    ok(f"Python {v.major}.{v.minor}.{v.micro}")
    return True


def check_node() -> bool:
    if not have("node"):
        err("Node.js not found — install from https://nodejs.org (LTS >= 18)")
        return False
    try:
        out = run(["node", "--version"]).stdout.strip()
        major = int(out.lstrip("v").split(".")[0])
        if major < 18:
            warn(f"Node {out} is older than recommended v18+")
        else:
            ok(f"Node.js {out}")
        return major >= 18
    except Exception as e:
        err(f"Could not query node: {e}"); return False


def check_npm() -> bool:
    if not have("npm"):
        err("npm not found (installed with Node.js)"); return False
    out = run(["npm", "--version"], check=False).stdout.strip()
    ok(f"npm {out}"); return True


def install_python_deps(do_install: bool) -> bool:
    if not REQ_FILE.exists():
        err(f"missing {REQ_FILE}"); return False
    if not do_install:
        info(f"would install: pip install -r {REQ_FILE.name}"); return True
    info("Installing Python dependencies …")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "--upgrade", "pip"])
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "-r", str(REQ_FILE)])
        ok("Python dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        err(f"pip install failed: {e}"); return False


def install_frontend_deps(do_install: bool) -> bool:
    pkg = FRONTEND / "package.json"
    if not pkg.exists():
        err(f"missing {pkg}"); return False
    if not do_install:
        info("would run: npm install --legacy-peer-deps (in frontend/)"); return True
    info("Installing frontend dependencies …")
    # --legacy-peer-deps is required: react-scripts@5 peer-deps typescript ^3||^4
    # while we ship typescript ^5; npm 7+ refuses without this flag.
    try:
        subprocess.check_call(["npm", "install", "--legacy-peer-deps"],
                              cwd=str(FRONTEND),
                              shell=platform.system() == "Windows")
        ok("Frontend dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        err(f"npm install failed: {e}"); return False


def check_optional() -> None:
    print()
    info("Optional components (not required for local demo):")
    if have("docker"):
        v = run(["docker", "--version"], check=False).stdout.strip()
        ok(f"Docker — {v}")
    else:
        warn("Docker not found — needed only for docker-compose deployment")
    if platform.system() == "Windows":
        if have("wsl"):
            ok("WSL available — needed for Mininet-based data generation")
        else:
            warn("WSL not found — install via `wsl --install` for Mininet support")
    else:
        if have("mn"):
            ok("Mininet found")
        else:
            warn("Mininet not found — needed only for training-data generation")


def verify_imports() -> bool:
    info("Verifying key imports …")
    mods = ["fastapi", "uvicorn", "pydantic", "jwt", "bcrypt",
            "numpy", "torch", "psutil"]
    missing = []
    for m in mods:
        try:
            __import__(m)
        except Exception:
            missing.append(m)
    if missing:
        err(f"Missing modules: {', '.join(missing)}"); return False
    ok("All key imports succeed")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="Check only; do not install")
    args = parser.parse_args()
    do_install = not args.check

    print("=" * 60)
    print("  PathWise AI — environment setup")
    print("=" * 60)

    results = [
        check_python(),
        check_node(),
        check_npm(),
        install_python_deps(do_install),
        install_frontend_deps(do_install),
    ]
    if do_install:
        results.append(verify_imports())
    check_optional()

    print("\n" + "=" * 60)
    if all(results):
        ok("PathWise AI is ready.")
        print(f"""
  Start backend:   python run.py
                   (or, for Windows QoS:  start_enforcer.bat  [as admin])
  Start frontend:  cd frontend && npm start
  Open:            http://localhost:3000
""")
        return 0
    err("Setup incomplete — see errors above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
