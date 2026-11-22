# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""配布する成果物(STEP/STL など)の manifest.json を作る。

使い方:
    uv run python make_manifest.py --tag v1.0.0 --out output/manifest.json output/step output/stl

記載: ソースのコミット SHA、タグ名、Python / build123d / OCP のバージョン、生成日時、
各ファイルの名前(--base からの相対)・サイズ・SHA256、合計サイズ。
引数のフォルダは再帰的に集める。出力先の manifest.json 自身は含めない。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from importlib import metadata
from pathlib import Path


def _git(*args: str, cwd: Path) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
        return r.stdout.strip() if r.returncode == 0 else ""
    except OSError:
        return ""


def _version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "not installed"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="成果物のファイルまたはフォルダ")
    ap.add_argument("--tag", required=True, help="タグ名(例: v1.0.0)")
    ap.add_argument("--out", required=True, help="出力する manifest.json のパス")
    ap.add_argument("--base", help="ファイル名の基準フォルダ(既定: --out のあるフォルダ)")
    ap.add_argument("--repo", default=".", help="ソースの git リポジトリ(既定: カレント)")
    ap.add_argument("--allow-dirty", action="store_true", help="未コミットの変更があっても作る(既定は止める)")
    a = ap.parse_args()

    repo = Path(a.repo).resolve()
    out = Path(a.out).resolve()
    base = Path(a.base).resolve() if a.base else out.parent

    if _git("status", "--porcelain", cwd=repo) and not a.allow_dirty:
        print("作業ツリーに未コミットの変更がある。コミットするか --allow-dirty を付ける。", file=sys.stderr)
        return 2

    files: list[Path] = []
    for p in map(Path, a.paths):
        if p.is_dir():
            files += sorted(x for x in p.rglob("*") if x.is_file())
        elif p.is_file():
            files.append(p)
        else:
            print(f"見つからない: {p}", file=sys.stderr)
            return 2
    files = [f.resolve() for f in files if f.resolve() != out]
    if not files:
        print("成果物が 1 つもない。", file=sys.stderr)
        return 2

    entries = []
    for f in files:
        size = f.stat().st_size
        if size == 0:
            print(f"空のファイル: {f}", file=sys.stderr)
            return 2
        try:
            name = f.relative_to(base).as_posix()
        except ValueError:
            name = f.name
        entries.append({"file": name, "size": size, "sha256": _sha256(f)})

    jst = timezone(timedelta(hours=9))
    manifest = {
        "tag": a.tag,
        "source_commit": _git("rev-parse", "HEAD", cwd=repo),
        "generated_at": datetime.now(jst).isoformat(timespec="seconds"),
        "versions": {
            "python": platform.python_version(),
            "build123d": _version("build123d"),
            "ocp": _version("cadquery-ocp-novtk") if _version("cadquery-ocp-novtk") != "not installed" else _version("cadquery-ocp"),
        },
        "total_size": sum(e["size"] for e in entries),
        "files": entries,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{out}: {len(entries)} files, {manifest['total_size'] / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
