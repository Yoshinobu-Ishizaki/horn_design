"""重い import(build123d・OCP・scipy・ocp_vscode)を、毎回しないための常駐プロセス。

起動(1 回だけ。動かしたままにする):
    BOPE_VIEWER_PORT=3940 PYTHONDONTWRITEBYTECODE=1 uv run python cad/valves/ocp/warm.py serve
スクリプトの実行(システムの python3 で十分。標準ライブラリだけなので 0.05 秒で始まる):
    python3 cad/valves/ocp/warm.py run cad/valves/ocp/valve3_bb3_slide.py [引数...]
常駐側が、受け取ったスクリプトを runpy で実行し、出力を返す。実行のたびに、cad/ 内の自分たちのモジュールは import し直す
(ソースを直した分が反映される)。重いライブラリは読み込み済みのまま。止めるには `warm.py stop`。
作った形のキャッシュは shape_cache.py(ソースが変わっていなければ読み込むだけ)。
"""

import json
import os
import socket
import sys
from pathlib import Path

SOCK = str(Path(__file__).resolve().parents[3] / "output" / "cache" / "warm.sock")


def client(cmd, args):
    s = socket.socket(socket.AF_UNIX)
    try:
        s.connect(SOCK)
    except OSError:
        sys.exit("常駐プロセスが動いていない。先に: uv run python cad/valves/ocp/warm.py serve")
    req = {"cmd": cmd, "argv": args, "cwd": os.getcwd(), "env": {k: v for k, v in os.environ.items() if k.startswith(("BOPE", "NO_SHAPE"))}}
    s.sendall((json.dumps(req) + "\n").encode())
    buf = b""
    while True:
        data = s.recv(65536)
        if not data:
            break
        buf += data
        cut = buf.rfind(b"\n")
        if cut >= 0:
            sys.stdout.buffer.write(buf[: cut + 1])
            sys.stdout.buffer.flush()
            buf = buf[cut + 1 :]
    rc = 0
    if buf.startswith(b"\x00EXIT"):
        rc = int(buf[5:] or 0)
    elif buf:
        sys.stdout.buffer.write(buf)
    sys.exit(rc)


def serve():
    import io
    import runpy
    import traceback

    # 重いライブラリを先に読む
    import build123d  # noqa: F401
    import numpy  # noqa: F401
    import scipy.optimize  # noqa: F401
    from ocp_vscode import Camera  # noqa: F401
    from bope_claude_cad.viewer import show  # noqa: F401

    root = Path(__file__).resolve().parents[3]
    mine = str(root / "cad")
    Path(SOCK).parent.mkdir(parents=True, exist_ok=True)
    if os.path.exists(SOCK):
        os.unlink(SOCK)
    srv = socket.socket(socket.AF_UNIX)
    srv.bind(SOCK)
    srv.listen(1)
    print("常駐プロセスを起動した:", SOCK, flush=True)
    while True:
        conn, _ = srv.accept()
        f = conn.makefile("rwb")
        req = json.loads(f.readline())
        if req["cmd"] == "stop":
            conn.sendall(b"stop\n\x00EXIT0")
            f.close()
            conn.close()
            break

        class Out(io.TextIOBase):
            def write(self, t):
                try:
                    conn.sendall(t.encode("utf-8", "replace"))
                except OSError:
                    pass
                return len(t)

            def flush(self):
                pass

        rc = 0
        old = (sys.stdout, sys.stderr, sys.argv, list(sys.path), os.getcwd(), dict(os.environ))
        sys.stdout = sys.stderr = Out()
        script = str(Path(req["argv"][0]).resolve())
        sys.argv = [script] + req["argv"][1:]
        os.environ.update(req["env"])
        for name in [n for n, m in sys.modules.items() if (getattr(m, "__file__", None) or "").startswith(mine)]:
            del sys.modules[name]  # 自分たちのモジュールだけ import し直す
        try:
            os.chdir(req["cwd"])
            sys.path.insert(0, str(Path(script).parent))
            runpy.run_path(script, run_name="__main__")
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
            if isinstance(e.code, str):
                print(e.code)
        except BaseException:
            traceback.print_exc()
            rc = 1
        finally:
            sys.stdout, sys.stderr, sys.argv = old[0], old[1], old[2]
            sys.path[:] = old[3]
            os.chdir(old[4])
        try:
            conn.sendall(b"\n\x00EXIT%d" % rc)
        except OSError:
            pass
        f.close()
        conn.shutdown(socket.SHUT_RDWR)
        conn.close()


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    if c == "serve":
        serve()
    elif c in ("run", "stop"):
        client(c, sys.argv[2:])
    else:
        sys.exit(__doc__)
