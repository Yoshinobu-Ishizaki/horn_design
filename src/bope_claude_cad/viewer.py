"""OCP Viewer の `show()` を包み、表示した形を記録する。ビューアーの ID(`faces_6` など)から面・辺を引くため。

`ocp_vscode.show` の代わりに、これを使う(引数は同じ)::

    from bope_claude_cad.viewer import show
    show(bender, holder, jaw, names=["bender", "clamp_holder", "clamp_jaw"], reset_camera=Camera.KEEP)

表示のたびに、渡した形を `output/viewer_registry/<部品名>.brep` に保存し、`index.json` に部品名・面数・辺数・
保存時刻(epoch)を書く。ビューアーは `show` のたびに表示全体を置き換えるので、記録も毎回置き換える。
ホバーの ID(`[clamp_jaw faces_6]`)は、その部品の `shape.faces()` / `shape.edges()` の 0 始まりの添字で、
BREP に保存しても並びは変わらない。そのため、部品名と ID だけで、形を作り直す関数なしに引ける::

    uv run python -m bope_claude_cad.pick_id --part clamp_jaw faces 6
    uv run python -m bope_claude_cad.pick_id --list

保存先は、リポジトリルート(`pyproject.toml` か `.git` のある上位のフォルダ)の `output/viewer_registry/`。
環境変数 `BOPE_VIEWER_REGISTRY` で変えられる。`output/` は git の管理外。
部品名を付けずに表示した形は `Part_<番号>` の名前で記録する(ビューアーの名前と一致しないことがあるので、
名前を付けて表示する)。
"""

from __future__ import annotations

import json
import os
import re
import time
import warnings
from pathlib import Path

INDEX = "index.json"


def _sibling(name: str):
    """同じフォルダの別モジュール。パッケージ(bope_claude_cad.<name>)としても、スキルの scripts/ の単体ファイルとしても読める。"""
    import importlib

    return importlib.import_module(f"{__package__}.{name}" if __package__ else name)


def find_root(start: Path | None = None) -> Path:
    """`pyproject.toml` か `.git` のある上位のフォルダ。見つからなければカレント。"""
    here = (start or Path.cwd()).resolve()
    for d in (here, *here.parents):
        if (d / "pyproject.toml").is_file() or (d / ".git").exists():
            return d
    return here


def registry_dir() -> Path:
    env = os.environ.get("BOPE_VIEWER_REGISTRY")
    return Path(env) if env else find_root() / "output" / "viewer_registry"


def _safe(name: str) -> str:
    return re.sub(r"[^\w.\-]", "_", name) or "part"


def _is_shape(obj) -> bool:
    return hasattr(obj, "faces") and hasattr(obj, "edges")


def record(objs, names=None, directory: Path | str | None = None) -> dict:
    """表示する形を記録し、index(辞書)を返す。形でないもの(座標系など)は飛ばす。"""
    from build123d import export_brep

    d = Path(directory) if directory is not None else registry_dir()
    d.mkdir(parents=True, exist_ok=True)
    for f in d.glob("*.brep"):
        f.unlink()
    parts: dict[str, dict] = {}
    names = list(names) if names else []
    for i, obj in enumerate(objs):
        if not _is_shape(obj):
            continue
        name = str(names[i]) if i < len(names) and names[i] is not None else f"Part_{i}"
        base, k = name, 2
        while name in parts:  # 同名は _2、_3 を付ける(ビューアーのパスとは違う名前になる)
            name = f"{base}_{k}"
            k += 1
        fname = f"{_safe(name)}.brep"
        export_brep(obj, str(d / fname))
        parts[name] = {"file": fname, "faces": len(obj.faces()), "edges": len(obj.edges())}
    index = {"saved_at": int(time.time()), "parts": parts}
    (d / INDEX).write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    return index


VIEWER_FILE = "viewer.json"


def _port_live(port: int) -> bool:
    from ocp_vscode.comms import port_check

    return bool(port_check(port))


def _live_ports() -> list[int]:
    from ocp_viewer_core.state import get_ports

    return [int(p) for p in get_ports() if _port_live(int(p))]


def bind_viewer(port: int, root: Path | str | None = None) -> Path:
    """このリポジトリ(root。既定はカレントの属するリポジトリ)が使うビューアのポートを記録する。

    ウィンドウ(リポジトリ)ごとに別のビューアを開く運用で、どのビューアに表示するかを決めておく。
    バックエンド(`python -m ocp_vscode --backend --port N`)を起動するときに、同じ N で呼ぶ。
    """
    d = (find_root(Path(root)) if root else find_root()) / "output" / "viewer_registry"
    d.mkdir(parents=True, exist_ok=True)
    p = d / VIEWER_FILE
    p.write_text(json.dumps({"port": int(port), "saved_at": int(time.time())}), encoding="utf-8")
    return p


def resolve_viewer_port(root: Path | str | None = None) -> int | None:
    """表示先のビューアのポートを決める。決められなければ None(ビューアが無い)。複数あって決められなければ例外。

    優先順位: 環境変数 BOPE_VIEWER_PORT(常駐プログラムが設定する)> このリポジトリに記録したポート(生きていれば)>
    開いているビューアが1つだけならそれ(記録もする)。記録が無く、ビューアが複数あるときは、
    ocp_vscode の対話の問い合わせ(端末では止まる)にせず、`bind_viewer` を促す例外にする。
    """
    env = os.environ.get("BOPE_VIEWER_PORT")
    if env:
        return int(env)
    f = (find_root(Path(root)) if root else find_root()) / "output" / "viewer_registry" / VIEWER_FILE
    if f.is_file():
        try:
            port = int(json.loads(f.read_text(encoding="utf-8"))["port"])
            if _port_live(port):
                return port
        except (OSError, ValueError, KeyError):
            pass
    live = _live_ports()
    if len(live) == 1:
        bind_viewer(live[0], root)
        return live[0]
    if live:
        raise RuntimeError(
            f"開いているビューアが複数あり({', '.join(map(str, live))})、このリポジトリのビューアが決まりません。"
            "このウィンドウのビューアのポートを `uv run python -m bope_claude_cad.viewer bind <ポート>` で記録してください")
    return None


def set_config(**cfg) -> None:
    """`ocp_vscode.set_viewer_config` と同じ。表示先は、このリポジトリのビューア(show と同じ決め方)。"""
    from ocp_vscode import set_viewer_config

    if "port" not in cfg:
        port = resolve_viewer_port()
        if port is not None:
            cfg["port"] = port
    set_viewer_config(**cfg)


# ---- 視点・表示の切り替え・スクショ(コマンドから呼べる) ----
VIEW_NAMES = {
    "top": "TOP", "bottom": "BOTTOM", "front": "FRONT", "back": "BACK", "left": "LEFT", "right": "RIGHT",
    "iso": "ISO", "fit": "CENTER",
    # 軸の名前: その側にカメラを置いて見る(+x = right、-y = front、+z = top)
    "+x": "RIGHT", "x": "RIGHT", "-x": "LEFT", "+y": "BACK", "y": "BACK", "-y": "FRONT",
    "+z": "TOP", "z": "TOP", "-z": "BOTTOM",
}


def set_view(name: str) -> str:
    """視点を変える(top / bottom / front / back / left / right / iso / fit、または +x -x +y -y +z -z の側から)。

    `show` の直後は切り替えが取りこぼされて視点が変わらないことがあるので、少し間を置いて 2 回送る。
    """
    import time as _time

    from ocp_vscode import Camera

    key = name.lower()
    if key not in VIEW_NAMES:
        raise ValueError(f"視点は {', '.join(VIEW_NAMES)} のどれか: {name!r}")
    cam = getattr(Camera, VIEW_NAMES[key])
    for i in range(2):
        set_config(reset_camera=cam)
        if i == 0:
            _time.sleep(0.5)
    return key


def visibility(cmd: str, names: list[str]) -> list[str]:
    """部品の表示・非表示。cmd は "only"(指定だけ表示)・"hide"(指定を隠す)・"all"(全部表示)。

    names は `show(..., names=[...])` の部品名(組立の入れ子なら、組立名でも部品名でもよい)。
    次に `show` し直すと元に戻る。表示中の部品名(最上位)のリストを返す。
    """
    from ocp_vscode import status

    port = resolve_viewer_port()
    states = status(port=port)["states"]

    def labels(key: str) -> set[str]:
        return {s for s in key.split("/")[2:] if s}   # "/Group/<組立>/<部品>" の組立名・部品名

    known = set().union(*(labels(k) for k in states)) if states else set()
    unknown = [n for n in names if n not in known]
    if unknown:
        raise ValueError(f"部品 {', '.join(unknown)} はありません。表示中の部品: {', '.join(sorted(known))}")
    new = {}
    for key, cur in states.items():
        hit = bool(labels(key) & set(names))
        if cmd == "only":
            visible = hit
        elif cmd == "hide":
            visible = not hit and cur != [0, 0]
        else:
            visible = True
        new[key] = [1, 1] if visible else [0, 0]
    set_config(states=new)
    return sorted({k.split("/")[2] for k, v in new.items() if v != [0, 0]})


def screenshot(path: Path | str) -> Path:
    """ビューアの画面を PNG に保存する(見え方を確かめるため)。視点を変えた直後は、少し待ってから撮る。"""
    from ocp_vscode import save_screenshot

    save_screenshot(str(path), port=resolve_viewer_port())
    return Path(path)


def _record_history(note: str, frame) -> None:
    """呼び出したスクリプトの写しを履歴に残す(history.py)。スクリプトのファイルが無ければ(対話実行など)何もしない。"""
    history = _sibling("history")

    if not history.enabled():
        return
    path = frame.f_globals.get("__file__") if frame else None
    if path and Path(path).is_file():
        history.record(path, note)
        history.set_last(path)


def show(*objs, names=None, note: str = "表示", **kwargs):
    """`ocp_vscode.show` と同じ(`note` だけ追加)。表示の前に、形と呼び出したスクリプトを記録する。

    記録に失敗しても表示は止めない。`note` は履歴(`bope_claude_cad.history list`)に出る説明。
    """
    import inspect

    from ocp_vscode import show as _show

    try:
        record(objs, names)
    except Exception as ex:  # noqa: BLE001
        warnings.warn(f"表示した形の記録に失敗: {type(ex).__name__}: {ex}", stacklevel=2)
    try:
        _record_history(note, inspect.currentframe().f_back)
    except Exception as ex:  # noqa: BLE001
        warnings.warn(f"履歴の記録に失敗: {type(ex).__name__}: {ex}", stacklevel=2)
    if "port" not in kwargs:  # 表示先は、このリポジトリのビューア(複数あっても混ざらないように)
        port = resolve_viewer_port()
        if port is not None:
            kwargs["port"] = port
    return _show(*objs, names=names, **kwargs)


AXES = {"x": 0, "y": 1, "z": 2}


def _far(extent: float) -> float:
    """使わない切断面を置く距離。形状の外形より少し外(極端な値はビューアの描画を乱す)。"""
    return round(extent + 10)


def _extent(directory: Path | str | None = None) -> float:
    """記録にある全部品の、原点からの最大の広がり。"""
    from build123d import import_brep

    d = Path(directory) if directory is not None else registry_dir()
    ext = 0.0
    for info in read_index(d)["parts"].values():
        b = import_brep(str(d / info["file"])).bounding_box()
        ext = max(ext, *(abs(v) for v in (b.min.X, b.min.Y, b.min.Z, b.max.X, b.max.Y, b.max.Z)))
    return ext


def section(axis: str, position: float, keep_plus: bool = False, extent: float | None = None) -> None:
    """軸 axis(x/y/z)に垂直な面 `axis=position` で切る。keep_plus なら大きい側を残す(既定は小さい側)。

    切り口は部品ごとの色(clip_object_colors)。使わない 2 軸の切断面は形状の外に置く。
    """

    far = _far(_extent() if extent is None else extent)
    axis = axis.lower()
    cfg = {"tab": "clip", "clip_intersection": False, "clip_planes": False, "clip_object_colors": True}
    for name, i in AXES.items():
        normal = [0, 0, 0]
        if name == axis:
            normal[i] = 1 if keep_plus else -1  # n・p + d >= 0 の側を残す
            slider = -position if keep_plus else position
        else:
            normal[i] = -1
            slider = far
        cfg[f"clip_normal_{i}"] = normal
        cfg[f"clip_slider_{i}"] = slider
    set_config(**cfg)


def section_off(extent: float | None = None) -> None:
    """断面をやめる(切断面を形状の外へ戻す)。"""

    far = _far(_extent() if extent is None else extent)
    set_config(tab="tree", **{f"clip_normal_{i}": [-1 if j == i else 0 for j in range(3)] for i in range(3)},
                      **{f"clip_slider_{i}": far for i in range(3)})


def feature_axis(shape, kind: str | None = None, index: int | None = None):
    """面(円筒面)か辺(円)の指定から (軸上の点, 軸の向き, 軸上の注目点) を返す。

    kind は "faces" / "edges"(ホバーの ID の種類)、index はその 0 始まりの添字。
    円筒面ならその軸。円の辺なら円の中心と法線。指定が無い・どちらでもないときは、
    部品で一番大きい円筒面の軸。円筒が無ければ None。
    注目点は軸の上で、選んだものの中央の高さ(切り口を映す中心)。
    """
    from build123d import Vector
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder

    def cyl(face):
        s = BRepAdaptor_Surface(face.wrapped)
        if s.GetType() != GeomAbs_Cylinder:
            return None
        a = s.Cylinder().Axis()
        p, d = a.Location(), a.Direction()
        return Vector(p.X(), p.Y(), p.Z()), Vector(d.X(), d.Y(), d.Z())

    found, near = None, shape.bounding_box().center()
    if kind == "faces" and index is not None:
        face = shape.faces()[index]
        found, near = cyl(face), face.center()
    elif kind == "edges" and index is not None:
        edge = shape.edges()[index]
        if edge.geom_type.name == "CIRCLE":
            found = (edge.arc_center, edge.normal())
            near = edge.arc_center
            # 同じ軸上の穴(円筒面)があれば、その中央の高さを注目点にする
            best = None
            for f in shape.faces():
                c = cyl(f)
                if c is None or abs(abs(c[1].dot(found[1])) - 1) > 1e-6:
                    continue
                off = (c[0] - near) - found[1] * (c[0] - near).dot(found[1])
                if off.length < 1e-3 and (best is None or f.area > best[0]):
                    best = (f.area, f.center())
            if best:
                near = best[1]
    if found is None:
        cyls = [(f.area, cyl(f)) for f in shape.faces() if cyl(f)]
        if not cyls:
            return None
        found = max(cyls, key=lambda t: t[0])[1]
        near = shape.bounding_box().center()
    point, direction = found
    return point, direction, point + direction * (near - point).dot(direction)


def axis_section(part: str, kind: str | None = None, index: int | None = None, directory=None):
    """記録した部品 part の穴・ボルトなどの軸を通る面で切り、軸が真ん中に来るよう切り口を正面から映す。

    kind/index はホバーの ID(`faces_6` → "faces", 6)。省略すると、部品で一番大きい円筒面の軸。
    軸が Y 寄りなら X で、それ以外は Y で切って手前半分を消し、標準の視点(LEFT / FRONT)で見る。
    カメラの位置だけを指定すると、向き(回転)が合わずに図が全部消えた(2026-11-13 実機で確認)ので、
    `position` / `target` は使わない。
    """
    from ocp_vscode import Camera

    shape = load_part(part, directory)
    res = feature_axis(shape, kind, index)
    if res is None:
        raise ValueError(f"部品 {part!r} に円筒面がありません")
    _point, direction, center = res
    ext = _extent(directory)
    if abs(direction.Y) > max(abs(direction.X), abs(direction.Z)):
        section("x", center.X, keep_plus=True, extent=ext)
        set_config(reset_camera=Camera.LEFT)
    else:
        section("y", center.Y, keep_plus=True, extent=ext)
        set_config(reset_camera=Camera.FRONT)
    return center, direction


def read_index(directory: Path | str | None = None) -> dict:
    d = Path(directory) if directory is not None else registry_dir()
    p = d / INDEX
    if not p.is_file():
        raise FileNotFoundError(f"記録が無い: {p}(`bope_claude_cad.viewer.show` で表示してから)")
    return json.loads(p.read_text(encoding="utf-8"))


def load_part(name: str, directory: Path | str | None = None):
    """部品名から、最後に表示した形を読み込む。パス形式(`assy/clamp_jaw`)は最後の節を使う。"""
    from build123d import import_brep

    d = Path(directory) if directory is not None else registry_dir()
    parts = read_index(d)["parts"]
    key = name.strip("/").split("/")[-1]  # ホバーの `[部品名]` やツリーのパスの最後の節でも引ける
    hits = [n for n in parts if n == name or n.split("/")[-1] == key]
    if not hits:
        raise KeyError(f"部品 {key!r} が記録に無い。記録にある部品: {', '.join(parts) or '(なし)'}")
    return import_brep(str(d / parts[hits[0]]["file"]))


def main(argv: list[str] | None = None) -> int:
    """`python -m bope_claude_cad.viewer <コマンド>`(スキルの scripts/ の単体ファイルなら `uv run python <スクリプト>/viewer.py <コマンド>`)。

    bind <ポート>                         このリポジトリが使うビューアを記録する(バックエンドと同じポート)
    status                                このリポジトリのビューアのポートを確認する
    view top|bottom|front|back|left|right|iso|fit|+x|-x|+y|-y|+z|-z   視点(+x は +X 側から見る)
    section x|y|z <位置> [+|-]            軸に垂直な面で切る(+ は大きい側を残す。既定は小さい側)
    section off                           断面をやめる
    axis <部品名> [faces|edges <N>]       穴・ボルトの軸を通る面で切り、正面から見る(省略時は一番大きい円筒面)
    only <部品名>... / hide <部品名>... / all   部品の表示・非表示(次に show すると戻る)
    transparent on|off                    半透明
    shot <保存先.png>                     画面を PNG に保存する
    """
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["bind"] and len(args) == 2:
        print(f"記録しました: {bind_viewer(int(args[1]))}(ポート {args[1]})")
        return 0
    try:
        cmd, rest = (args[0] if args else ""), args[1:]
        if cmd == "status":
            port = resolve_viewer_port()
            print(f"このリポジトリのビューア: {port if port is not None else 'なし(開いていない)'}")
            return 0
        if cmd == "view" and len(rest) == 1:
            print(f"視点を {set_view(rest[0])} にしました")
            return 0
        if cmd == "section" and rest == ["off"]:
            section_off()
            print("断面をやめました")
            return 0
        if cmd == "section" and len(rest) in (2, 3) and rest[0].lower() in AXES:
            keep_plus = len(rest) == 3 and rest[2] == "+"
            section(rest[0], float(rest[1]), keep_plus)
            print(f"{rest[0].upper()}={float(rest[1]):g} の面で切り、{'大きい' if keep_plus else '小さい'}側を残しました")
            return 0
        if cmd == "axis" and len(rest) in (1, 3):
            kind, index = (rest[1], int(rest[2])) if len(rest) == 3 else (None, None)
            center, direction = axis_section(rest[0], kind, index)
            print(f"{rest[0]} の軸(中心 ({center.X:.2f}, {center.Y:.2f}, {center.Z:.2f})、"
                  f"向き ({direction.X:.2f}, {direction.Y:.2f}, {direction.Z:.2f}))で切りました")
            return 0
        if cmd in ("only", "hide") and rest:
            print(f"表示中の部品: {', '.join(visibility(cmd, rest)) or 'なし'}")
            return 0
        if cmd == "all" and not rest:
            print(f"表示中の部品: {', '.join(visibility('all', [])) or 'なし'}")
            return 0
        if cmd == "transparent" and len(rest) == 1 and rest[0] in ("on", "off"):
            set_config(transparent=rest[0] == "on")
            print(f"半透明表示を {rest[0]} にしました")
            return 0
        if cmd == "shot" and len(rest) == 1:
            print(f"保存しました: {screenshot(rest[0])}")
            return 0
    except (RuntimeError, ValueError, KeyError, FileNotFoundError) as ex:
        print(ex)
        return 1
    print(main.__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
