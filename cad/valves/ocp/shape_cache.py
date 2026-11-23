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
SEARCH = [HERE, ROOT / "cad" / "tubes" / "ocp", ROOT / "cad" / "bows" / "ocp"]


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


def source_hash(root_file) -> str:
    seen, todo = {}, [Path(root_file).resolve()]
    while todo:
        f = todo.pop()
        if f in seen:
            continue
        seen[f] = hashlib.sha1(f.read_bytes()).hexdigest()
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
    return import_brep(str(d / v))
