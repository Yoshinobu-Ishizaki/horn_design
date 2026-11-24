"""設計スクリプトを実行する常駐プログラム(build123d などの読み込みを毎回しないため)。ビューア1つにつき1つ。

llm_usage の press-die-design-assist/cad/runner.py を参考に、bope_claude_cad 向けに作り直した。
build123d・ocp_vscode の読み込みを起動時の1回で済ませ、あとは頼まれるたびに、スクリプトをその中で実行する
(表示は `show` がそのまま行う)。`history undo --run` などが使う。

**ビューアと対にする**: ウィンドウ(リポジトリ)ごとに別のビューアを開く運用で、表示先が混ざらないようにする。
- 常駐プログラムは、ビューアのポート V ごとに1つ。待ち受けるポートは V + 1000(ビューア 3939 なら 4939)
- 起動時に V に固定し、実行するスクリプトの `show` も V に表示する(環境変数 OCP_VIEWER_PORT)
- V のビューアが閉じたら、常駐プログラムも終わる
- 頼む側は、スクリプトのあるリポジトリが使うビューアを選ぶ(`viewer.resolve_viewer_port`。
  `viewer bind <ポート>` で記録したもの。無ければ、開いているビューアが1つだけならそれ)

コマンドライン(`--viewer V` を省くと、カレントのリポジトリのビューア)::

    uv run python -m bope_claude_cad.runner run <スクリプト>   常駐プログラムでスクリプトを実行する(無ければ起動する)
    uv run python -m bope_claude_cad.runner start|stop|status [--viewer V]
    uv run python -m bope_claude_cad.runner list              動いている常駐プログラム(ビューアのポートごと)

- 受け付けるのは 127.0.0.1 だけ(同じPCの中から)
- 実行のたびにスクリプトを読み直す。自作のモジュール(リポジトリの中の lib/ など、スクリプトのフォルダ、ライブラリ
  bope_claude_cad 自身)は、実行の前後に読み込み済みの一覧から捨てるので、直した内容が次の実行に反映される
  (スクリプトがリポジトリの外にあっても、ライブラリの修正は反映される。2026-11-13: 以前は反映されず、redo が古い viewer で失敗した)
- 起動時に読み込んでおくのは build123d と ocp_vscode だけ(これらは直さないので持ち越す)
- IDLE_SECONDS の間なにも頼まれなければ、自分で終わる
- 1つずつ順に実行する(同時には実行しない)。スクリプトの出力は、頼んだ側に返す
- 環境変数 `OCP_RUNNER=0` で使わない(`run` を呼んでも、常駐させず今のプロセスで実行する)
- 常駐プログラムは pythonw で起動する(黒いウィンドウを出さない)。ログは `~/.bope_claude_cad/runner.log`
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import runpy
import socket
import socketserver
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

PORT_OFFSET = 1000  # 常駐プログラムのポート = ビューアのポート + これ
IDLE_SECONDS = 4 * 3600
VIEWER_CHECK_SECONDS = 30  # ビューアが生きているかを見る間隔
HOME = Path.home() / ".bope_claude_cad"
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def _sibling(name: str):
    """同じフォルダの別モジュール。パッケージ(bope_claude_cad.<name>)としても、スキルの scripts/ の単体ファイルとしても読める。"""
    import importlib

    return importlib.import_module(f"{__package__}.{name}" if __package__ else name)


def runner_port(viewer_port: int) -> int:
    return int(viewer_port) + PORT_OFFSET


# ---- クライアント側 ----
def request(viewer_port: int, message: dict, timeout: float = 600) -> dict:
    with socket.create_connection(("127.0.0.1", runner_port(viewer_port)), timeout=timeout) as sock:
        sock.sendall((json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"))
        line = sock.makefile("rb").readline()
    return json.loads(line.decode("utf-8"))


def is_running(viewer_port: int) -> bool:
    try:
        request(viewer_port, {"cmd": "ping"}, timeout=2)
        return True
    except OSError:
        return False


def start(viewer_port: int, wait: int = 180) -> None:
    """viewer_port のビューアと対の常駐プログラムを起動する(動いていれば何もしない)。"""
    if is_running(viewer_port):
        return
    HOME.mkdir(parents=True, exist_ok=True)
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    # ファイルを直接起動する(パッケージとしても、スキルの scripts/ の単体ファイルとしても同じ。-m は使わない)
    command = [str(pythonw if pythonw.exists() else exe), str(Path(__file__).resolve()), "serve",
               "--viewer", str(viewer_port)]
    log = open(HOME / "runner.log", "a", encoding="utf-8")  # noqa: SIM115  子プロセスが持ち続ける
    flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    kwargs = {"stdout": log, "stderr": log, "stdin": subprocess.DEVNULL,
              "env": {**os.environ, "PYTHONIOENCODING": "utf-8", "OCP_RUNNER": "1"}}
    try:
        subprocess.Popen(command, creationflags=flags | CREATE_BREAKAWAY_FROM_JOB, **kwargs)
    except OSError:
        subprocess.Popen(command, creationflags=flags, **kwargs)
    for _ in range(wait):
        time.sleep(1)
        if is_running(viewer_port):
            return
    raise RuntimeError(f"常駐プログラムを起動できませんでした。{HOME / 'runner.log'} を見てください")


def stop(viewer_port: int) -> None:
    if is_running(viewer_port):
        request(viewer_port, {"cmd": "stop"})
        while is_running(viewer_port):
            time.sleep(0.5)


def running_viewers(candidates: range | list[int] | None = None) -> list[int]:
    """動いている常駐プログラムの、ビューアのポート。候補は ~/.ocpvscode のビューアのポート(既定)。"""
    if candidates is None:
        from ocp_viewer_core.state import get_ports

        candidates = [int(p) for p in get_ports()]
    return [p for p in candidates if is_running(p)]


def run_script(script: Path | str, cwd: Path | str | None = None) -> int:
    """スクリプトのあるリポジトリのビューアと対の常駐プログラムで実行し、出力を表示して終了コードを返す。

    OCP_RUNNER=0 なら、今のプロセスの外(子プロセス)で普通に実行する。
    """
    resolve_viewer_port = _sibling("viewer").resolve_viewer_port

    script = Path(script).resolve()
    cwd = Path(cwd) if cwd else Path.cwd()
    if os.environ.get("OCP_RUNNER") == "0":
        return subprocess.call([sys.executable, str(script)], cwd=cwd)
    try:
        viewer = resolve_viewer_port(script.parent)
    except RuntimeError as ex:
        print(ex)
        return 1
    if viewer is None:
        print("ビューアが開いていません。VS Code で OCP CAD Viewer を開いてから実行してください")
        return 1
    if not is_running(viewer):
        print(f"ビューア {viewer} と対の常駐プログラムを起動します(この1回だけ数秒〜数十秒かかります)", flush=True)
        start(viewer)
    started = time.perf_counter()
    response = request(viewer, {"cmd": "run", "script": str(script), "cwd": str(cwd)})
    print(response["output"], end="")
    print(f"({time.perf_counter() - started:.1f} 秒、ビューア {viewer})")
    return response["code"]


# ---- サーバー側 ----
def _repo_root(start: Path) -> Path:
    for d in (start, *start.parents):
        if (d / "pyproject.toml").is_file() or (d / ".git").exists():
            return d
    return start


LIBRARY_DIR = Path(__file__).resolve().parent   # このモジュールのあるフォルダ(bope_claude_cad、またはスキルの scripts/)


def _purge(roots) -> None:
    """roots のどれかの下にあるモジュールを、読み込み済みの一覧から捨てる(次の import で読み直される)。
    第三者のパッケージ(.venv・site-packages)と、常駐プログラム自身(__main__ と、このモジュール)は残す。"""
    keep = {"__main__", __name__}
    for name, mod in list(sys.modules.items()):
        path = getattr(mod, "__file__", None)
        if not path or name in keep:
            continue
        p = Path(path).resolve()
        if ".venv" in p.parts or "site-packages" in p.parts:
            continue
        if any(p.is_relative_to(r) for r in roots):
            del sys.modules[name]


def run(req: dict, viewer_port: int) -> dict:
    """スクリプトを viewer_port のビューアに向けて実行して、出力と終了コードを返す。"""
    script = Path(req["script"]).resolve()
    cwd = Path(req["cwd"]).resolve()
    root = _repo_root(script.parent)
    # スクリプトが読み込む自作のモジュール(リポジトリ内、スクリプトのフォルダ、ライブラリ自身)は、毎回読み込み直す。
    # スクリプトがリポジトリの外(作業用のフォルダなど)にあっても、ライブラリの修正が反映されるように、ライブラリのフォルダも含める
    fresh_roots = [root, script.parent, LIBRARY_DIR]
    _purge(fresh_roots)
    saved_argv, saved_cwd = sys.argv, Path.cwd()
    os.chdir(cwd)
    sys.argv = [str(script)]
    sys.path.insert(0, str(script.parent))  # python script.py と同じ
    os.environ["OCP_VIEWER_PORT"] = str(viewer_port)  # show などの表示先を、この常駐プログラムのビューアに固定する
    out = io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exc:
        if exc.code not in (None, 0):
            if not isinstance(exc.code, int):
                out.write(f"{exc.code}\n")
            code = exc.code if isinstance(exc.code, int) else 1
    except Exception:  # noqa: BLE001  スクリプトの誤りで常駐プログラムを落とさない
        out.write(traceback.format_exc())
        code = 1
    finally:
        os.environ.pop("OCP_VIEWER_PORT", None)
        sys.argv = saved_argv
        os.chdir(saved_cwd)
        with contextlib.suppress(ValueError):
            sys.path.remove(str(script.parent))
        _purge(fresh_roots)   # 次の実行で直した内容を読み直すため、読み込んだ自作のモジュールは捨てる
    return {"output": out.getvalue(), "code": code}


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.server.last_used = time.time()
        req = json.loads(self.rfile.readline().decode("utf-8"))
        if req["cmd"] == "ping":
            response = {"output": "", "code": 0}
        elif req["cmd"] == "stop":
            response = {"output": "常駐プログラムを止めました\n", "code": 0}
            threading.Thread(target=self.server.shutdown).start()
        else:
            response = run(req, self.server.viewer_port)
        self.wfile.write((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))


def serve(viewer_port: int, watch_viewer: bool = True) -> None:
    import build123d  # noqa: F401  読み込みを先に済ませておく
    import ocp_vscode  # noqa: F401

    os.environ["OCP_RUNNER"] = "1"
    port = runner_port(viewer_port)
    try:
        server = socketserver.TCPServer(("127.0.0.1", port), Handler)
    except OSError:
        print(f"ポート {port} は使用中です(ビューア {viewer_port} と対の常駐プログラムがすでに動いている?)", flush=True)
        return
    server.last_used = time.time()
    server.viewer_port = viewer_port
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"{stamp} 起動しました (pid {os.getpid()}, ビューア {viewer_port}, port {port})", flush=True)

    def watch():
        _port_live = _sibling("viewer")._port_live

        dead = 0
        while True:
            time.sleep(VIEWER_CHECK_SECONDS)
            if time.time() - server.last_used >= IDLE_SECONDS:
                print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} 使われていないので終わります", flush=True)
                break
            if watch_viewer:
                dead = 0 if _port_live(viewer_port) else dead + 1
                if dead >= 2:  # 1回の取りこぼしでは終わらない
                    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} ビューア {viewer_port} が閉じたので終わります", flush=True)
                    break
        server.shutdown()

    threading.Thread(target=watch, daemon=True).start()
    with server:
        server.serve_forever()
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} 終了しました", flush=True)


def _viewer_arg(args: list[str]) -> tuple[list[str], int | None]:
    """`--viewer V` を取り出す。無ければ、カレントのリポジトリのビューア(決められなければ None)。"""
    resolve_viewer_port = _sibling("viewer").resolve_viewer_port

    if "--viewer" in args:
        i = args.index("--viewer")
        return args[:i] + args[i + 2:], int(args[i + 1])
    return args, resolve_viewer_port()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(__doc__)
        return 2
    cmd = args[0]
    if cmd == "list":
        live = running_viewers()
        print("\n".join(f"ビューア {p} と対(port {runner_port(p)})" for p in live) or "動いている常駐プログラムはありません")
        return 0
    try:
        rest, viewer = _viewer_arg(args[1:])
    except RuntimeError as ex:
        print(ex)
        return 1
    if cmd == "run" and rest:
        return run_script(rest[0])
    if viewer is None:
        print("ビューアが決まりません(開いていないか、`--viewer <ポート>` で指定してください)")
        return 1
    if cmd == "serve":
        serve(viewer)
    elif cmd == "start":
        start(viewer)
        print(f"ビューア {viewer} と対の常駐プログラムが動いています(port {runner_port(viewer)})")
    elif cmd == "stop":
        stop(viewer)
        print("止めました")
    elif cmd == "status":
        print(f"ビューア {viewer}: " + ("動いています" if is_running(viewer) else "動いていません"))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
