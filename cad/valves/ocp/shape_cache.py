"""作った形をディスク(output/cache/)に覚えて、ソースも条件も変わっていなければ、計算せずに読み込む。

キー = タグ + 条件(params)+ 依存するソースファイルの中身。ソースは、起点のファイルが import する cad/ 内のファイルを
たどって集める(静的に import 文を読む)ので、依存するファイルを直したときだけ作り直す。
  cached(tag, params, root_file, builder)  builder() は {名前: Shape(または Shape のリスト)} か Shape を返す。
キャッシュを使わないとき: 環境変数 NO_SHAPE_CACHE=1。
"""

import ast
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CACHE = ROOT / "output" / "cache"
SEARCH = [HERE, ROOT / "cad" / "tubes" / "ocp", ROOT / "cad" / "bows" / "ocp", ROOT / "cad" / "bell03" / "ocp", ROOT / "cad" / "bell03" / "tools"]


def _local_imports(path: Path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module.split(".")[0]]
        for n in names:
            for d in SEARCH + [path.parent]:
                f = d / f"{n}.py"
                if f.is_file():
                    yield f
                    break


_SELF_HASH = "3c14d719a89a09662e41ea96449270ea7b47291a"  # shape_cache.py の(幾何キャッシュを足す前の)中身の SHA-1。キャッシュのキーを変えないための固定値


def source_hash(root_file) -> str:
    seen, todo = {}, [Path(root_file).resolve()]
    while todo:
        f = todo.pop()
        if f in seen:
            continue
        # shape_cache.py 自身の変更(幾何キャッシュの追加など)で、全部のキャッシュが無効にならないよう、固定の値を使う
        seen[f] = _SELF_HASH if f.name == "shape_cache.py" else hashlib.sha1(f.read_bytes()).hexdigest()
        todo += [g.resolve() for g in _local_imports(f)]
    return hashlib.sha1("".join(f"{k.name}{v}" for k, v in sorted(seen.items())).encode()).hexdigest()


def cached(tag, params, root_file, builder):
    from build123d import export_brep, import_brep

    key = hashlib.sha1(f"{tag}|{params!r}|{source_hash(root_file)}".encode()).hexdigest()[:16]
    d = CACHE / f"{tag}_{key}"
    meta = d / "meta.json"
    if meta.exists() and not os.environ.get("NO_SHAPE_CACHE"):
        m = json.loads(meta.read_text(encoding="utf-8"))
        return _unpack(m["tree"], d, import_brep)
    out = builder()
    try:
        d.mkdir(parents=True, exist_ok=True)
        cnt = [0]
        tree = _pack(out, d, export_brep, cnt)
        meta.write_text(json.dumps({"tree": tree}, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        print(f"キャッシュに書けない: {e}", file=sys.stderr)
    return out


def _pack(x, d, export_brep, cnt):
    if isinstance(x, dict):
        return {"dict": [[k, _pack(v, d, export_brep, cnt)] for k, v in x.items()]}
    if isinstance(x, (list, tuple)):
        return {"tuple" if isinstance(x, tuple) else "list": [_pack(v, d, export_brep, cnt) for v in x]}
    if isinstance(x, (int, float, str, bool)) or x is None:
        return {"val": x}
    cnt[0] += 1
    name = f"s{cnt[0]}.brep"
    export_brep(x, str(d / name))
    return {"shape": name}


def _unpack(t, d, import_brep):
    (k, v), = t.items()
    if k == "dict":
        return {a: _unpack(b, d, import_brep) for a, b in v}
    if k in ("list", "tuple"):
        r = [_unpack(b, d, import_brep) for b in v]
        return tuple(r) if k == "tuple" else r
    if k == "val":
        return v
    return _load_shape(d / v, import_brep)


def _load_shape(path, import_brep):
    """形の読み込み。BinTools(バイナリ)の兄弟ファイル(.bin)があればそれを読む(テキストの BRep より桁違いに速い)。なければ BRep を読んで .bin も作る。"""
    from build123d import Shape
    from OCP.BinTools import BinTools
    from OCP.TopoDS import TopoDS_Shape

    binp = path.with_suffix(".bin")
    if binp.exists():
        sh = TopoDS_Shape()
        BinTools.Read_s(sh, str(binp))
        return Shape.cast(sh)
    sh = import_brep(str(path))
    try:
        BinTools.Write_s(sh.wrapped, str(binp))
    except Exception:  # noqa: BLE001
        pass
    return sh


# ---- 形の幾何計算のキャッシュ(import しただけで有効になる。スキルや呼び出し側の書き方に依存しない)----------------------------
# 形(位置も含む)の指紋 = 形を BinTools で書き出した中身の SHA-1。同じ指紋の組の最短距離(distance_to)は、一度測ったらディスクに覚えて、
# 次からは測らない。形や置き場所が変わった部品の組だけ測り直す。NO_SHAPE_CACHE=1 で無効。
_FP = {}
_DIST = {}
_DIST_FILE = CACHE / "geom_distance.txt"
_STATS = {"hit": 0, "miss": 0}


def fingerprint(shape) -> str:
    """形の指紋(位置を含む)。同じオブジェクトは 1 度だけ計算する。"""
    k = id(shape)
    hit = _FP.get(k)
    if hit is not None and hit[0] is shape:
        return hit[1]
    import io

    from OCP.BinTools import BinTools, BinTools_FormatVersion

    from OCP.BRepTools import BRepTools

    BRepTools.Clean_s(shape.wrapped)  # 付いている三角形分割を外す(メッシュの有無で指紋が変わるのを避ける。必要なときにまた付く)
    buf = io.BytesIO()
    # 三角形分割(メッシュ)は含めない: 表示や計測でメッシュが付いたかどうかで指紋が変わらないように
    BinTools.Write_s(shape.wrapped, buf, False, False, BinTools_FormatVersion.BinTools_FormatVersion_CURRENT)
    h = hashlib.sha1(buf.getvalue()).hexdigest()
    _FP[k] = (shape, h)
    return h


def _load_dist():
    if _DIST_FILE.exists():
        for line in _DIST_FILE.read_text(encoding="utf-8").splitlines():
            p = line.split()
            if len(p) == 3:
                _DIST[(p[0], p[1])] = float(p[2])
    _DIST["_loaded"] = True


def install_geometry_cache():
    """build123d の Shape.distance_to(形どうし)をディスクキャッシュ付きにする。"""
    from build123d.topology.shape_core import Shape

    if getattr(Shape, "_horn_cached", False) or os.environ.get("NO_SHAPE_CACHE"):
        return
    orig = Shape.distance_to

    def distance_to(self, other):
        if not isinstance(other, Shape) or self._wrapped is None or not other:
            return orig(self, other)
        if "_loaded" not in _DIST:
            _load_dist()
        a, b = sorted((fingerprint(self), fingerprint(other)))
        v = _DIST.get((a, b))
        if v is not None:
            _STATS["hit"] += 1
            return v
        _STATS["miss"] += 1
        v = orig(self, other)
        _DIST[(a, b)] = v
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
            with open(_DIST_FILE, "a", encoding="utf-8") as f:
                f.write(f"{a} {b} {v!r}\n")
        except OSError:
            pass
        return v

    Shape.distance_to = distance_to
    Shape._horn_cached = True

    # 辺・ワイヤの長さ(Mixin1D.length)も、同じ形(TShape + 位置 + 向きが同じ)なら 1 度だけ測る。Wire.position_at は呼ぶたびに全部の辺の長さを
    # 測り直すので、点を多数取る処理(6001 点で 27 秒)が桁違いに遅かった。形への参照を持っておくので、メモリ上の別の形と取り違えない
    from build123d.topology.one_d import Mixin1D

    orig_len = Mixin1D.length.fget
    memo = {}

    def length(self):
        k = hash(self.wrapped)
        hit = memo.get(k)
        if hit is not None:
            return hit[1]
        v = orig_len(self)
        memo[k] = (self.wrapped, v)
        return v

    Mixin1D.length = property(length)

    # 三角形分割(Shape.tessellate)も、形の指紋 + 許容差ごとにディスクに覚える
    orig_tess = Shape.tessellate
    tdir = CACHE / "tess"

    def tessellate(self, tolerance, angular_tolerance=0.1):
        import numpy as np
        from build123d import Vector

        key = hashlib.sha1(f"{fingerprint(self)}|{tolerance!r}|{angular_tolerance!r}".encode()).hexdigest()[:24]
        f = tdir / f"{key}.npz"
        if f.exists():
            z = np.load(f)
            return [Vector(*row) for row in z["v"].tolist()], [tuple(r) for r in z["t"].tolist()]
        v, t = orig_tess(self, tolerance, angular_tolerance)
        try:
            tdir.mkdir(parents=True, exist_ok=True)
            np.savez(f, v=np.array([[q.X, q.Y, q.Z] for q in v]).reshape(-1, 3), t=np.array(t, dtype=np.int64).reshape(-1, 3))
        except OSError:
            pass
        return v, t

    Shape.tessellate = tessellate


try:
    install_geometry_cache()
except Exception as e:  # noqa: BLE001  build123d が読めない環境でも shape_cache 自体は使えるように
    print(f"geometry cache not installed: {e}", file=sys.stderr)


_T0 = [None, None]


def phase(name):
    """OCP_TIMING=1(または --timing)のとき、前の phase からの経過秒を出す(重い所を探すための目印。何もしなければ無害)。"""
    import time

    if not os.environ.get("OCP_TIMING") and "--timing" not in sys.argv:
        return
    now = time.time()
    if _T0[0] is None:
        _T0[0] = _T0[1] = now
    print(f"[timing] +{now - _T0[1]:6.2f}s (total {now - _T0[0]:6.2f}s) {name}", flush=True)
    _T0[1] = now


def memo_value(tag, params, root_file, fn):
    """純粋な計算(数値・配列を返す)の結果を、引数 params と root_file の(import をたどった)ソースが同じなら、計算せずにディスクから読む。"""
    import pickle

    key = hashlib.sha1(f"{tag}|{params!r}|{source_hash(root_file)}".encode()).hexdigest()[:16]
    f = CACHE / f"memo_{tag}_{key}.pkl"
    if f.exists() and not os.environ.get("NO_SHAPE_CACHE"):
        return pickle.loads(f.read_bytes())
    v = fn()
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        f.write_bytes(pickle.dumps(v))
    except OSError:
        pass
    return v
