"""intonation.py の計算結果(.imp と .res)から、比較レポートの HTML(report.html)を作る。

- 入力インピーダンスの大きさ |Z|(縦軸は対数)を、bell01 と RefHorn で重ねる(Bb 管・F 管)。
- ピークとして認識できた倍音の音程を、a' = 440 Hz の平均律からのセントで比べる(Bb 管・F 管)。

    uv run python impedance/bell01/intonation.py   # 先に計算
    uv run python impedance/bell01/report.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from intonation import A4, HAND_L, MAXF, cents_vs_series

HERE = Path(__file__).resolve().parent
CASES = [("bell01", "Bb"), ("refhorn", "Bb"), ("bell01", "F"), ("refhorn", "F")]


def read_imp(path: Path, step: int = 2) -> list[list[float]]:
    a = np.loadtxt(path, delimiter=",", skiprows=1)
    a = a[1::step]  # 0 Hz を除き、2 Hz ごと
    z = np.hypot(a[:, 1], a[:, 2])
    return [[round(float(f), 1), float(f"{v:.5g}")] for f, v in zip(a[:, 0], z)]


def read_res(path: Path) -> np.ndarray:
    f = []
    for line in path.read_text().splitlines()[2:]:
        c = line.split(",")
        if len(c) >= 4:
            f.append(float(c[3]))
    return np.array(f)


def f_extra() -> dict[str, float]:
    """F 管で足した円筒の長さ(.men の 'F extra' 行)。"""
    out = {}
    for name in ("bell01", "refhorn"):
        for line in (HERE / f"{name}_F.men").read_text(encoding="utf-8").splitlines():
            if line.endswith("F extra"):
                out[name] = float(line.split(",")[2])
    return out


def men_length(path: Path) -> float:
    total = 0.0
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        c = line.split(",")
        if len(c) >= 3 and re.match(r"^-?[0-9.]", c[0]):
            total += float(c[2])
    return total


def main() -> None:
    data = {"imp": {}, "cents": {}}
    for name, key in CASES:
        base = HERE / f"{name}_{key}_rh"
        data["imp"][f"{name}_{key}"] = read_imp(base.with_suffix(".imp"))
        data["cents"][f"{name}_{key}"] = [
            {"n": n, "note": nm, "f": round(float(f), 2), "c": round(float(c), 1)}
            for n, nm, f, c in cents_vs_series(read_res(base.with_suffix(".res")), key)
        ]
    meta = {
        "a4": A4,
        "hand": HAND_L,
        "maxf": MAXF,
        "len": {f"{n}_{k}": round(men_length(HERE / f"{n}_{k}.men"), 1) for n, k in CASES},
        "extra": {k: round(v, 1) for k, v in f_extra().items()},
    }
    tpl = (HERE / "report_template.html").read_text(encoding="utf-8")
    html = tpl.replace("/*DATA*/null", json.dumps(data, separators=(",", ":"))).replace(
        "/*META*/null", json.dumps(meta, separators=(",", ":")))
    out = HERE / "report.html"
    out.write_text(html, encoding="utf-8")
    print(f"-> {out} ({out.stat().st_size / 1e3:.0f} kB)")


if __name__ == "__main__":
    main()
