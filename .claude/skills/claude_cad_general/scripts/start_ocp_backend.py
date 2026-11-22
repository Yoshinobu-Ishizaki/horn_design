"""OCP CAD Viewer の計測用バックエンドを起動する(すでに動いていれば何もしない)。

使い方(Bash の run_in_background で動かしたままにする):
    PYTHONIOENCODING=utf-8 uv run python <skill>/scripts/start_ocp_backend.py [--port 3939] [--check]

--check は、動いているかだけを調べて終了する(動いていれば 0、いなければ 1)。
ポートの既定は 3939。~/.ocpvscode に port があればそれを使う。
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

MARK = "ocp_vscode --backend"


def default_port() -> int:
    try:
        cfg = json.loads((Path.home() / ".ocpvscode").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 3939
    if isinstance(cfg, dict):
        if isinstance(cfg.get("port"), int):
            return cfg["port"]
        for svc in (cfg.get("services") or {}).values():
            if isinstance(svc, dict) and isinstance(svc.get("port"), int):
                return svc["port"]
    return 3939


def running_commandlines() -> list[str]:
    if sys.platform == "win32":
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_Process | ForEach-Object { $_.CommandLine }",
        ]
    else:
        cmd = ["ps", "-eo", "args"]
    out = subprocess.run(cmd, capture_output=True, text=True, errors="replace", check=False).stdout
    return [ln for ln in out.splitlines() if MARK in ln]


def is_running(port: int) -> bool:
    me = str(Path(__file__).name)
    return any(f"--port {port}" in ln and me not in ln for ln in running_commandlines())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=default_port())
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if is_running(args.port):
        print(f"backend はすでに動いています(port {args.port})")
        return 0
    if args.check:
        print(f"backend は動いていません(port {args.port})")
        return 1
    return subprocess.call([sys.executable, "-m", "ocp_vscode", "--backend", "--port", str(args.port)])


if __name__ == "__main__":
    sys.exit(main())
