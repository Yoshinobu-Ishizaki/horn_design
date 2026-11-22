"""intonation.py の計算結果(.imp と .res)から、比較レポートの HTML(report.html)を作る。

- 入力インピーダンスの大きさ |Z|(縦軸は対数)を、bell02 と RefHorn で重ねる(Bb 管・F 管)。
- ピークとして認識できた倍音の音程を、a' = A4 Hz の平均律からのセントで比べる(Bb 管・F 管)。
- bell02 の管内の音圧分布(calcspd)を、ベル開口を 0 とした芯線に沿った長さで示す(第2・3・4・6・8倍音)。

    uv run python impedance/bell02/intonation.py   # 先に計算(bell02 の決定値 refine_x1450r.json)
    uv run python impedance/bell02/report.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import subprocess
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scan_length as S  # noqa: E402

# I は bell01 の intonation.py。bell02 の intonation.py と名前がぶつかるので scan_length 経由で使う
I = S.I  # noqa: E741
A4, BIN, F_ABOVE_BB, HAND_L, MAXF, N_MAX, REF_N = I.A4, I.BIN, I.F_ABOVE_BB, I.HAND_L, I.MAXF, I.N_MAX, I.REF_N
cents_vs_series = I.cents_vs_series
_R = json.loads((HERE / "refine_x1450r.json").read_text())
X_END, D12_EXTRA = _R["xe"], 0.0
PERTURB = [(_R["x"][3], _R["x"][4], _R["x"][5] / 4.3, _R["x"][5])]
CASES = [("bell02", "Bb"), ("refhorn", "Bb"), ("bell02", "F"), ("refhorn", "F")]
SPD_N = [2, 3, 4, 6, 8]  # 音圧分布を出す倍音


def spd(men: Path, res: Path, ns=SPD_N, step: float = 3.0) -> dict:
    """calcspd -m -r で各倍音の音圧分布を求め、ベル開口からの距離 (mm) と dB の組にする。"""
    out = subprocess.run([str(BIN / "calcspd"), "-m", "-p", "2", "-r", str(res), str(men)],
                         capture_output=True, text=True, check=True).stdout.splitlines()
    head = out[1].lstrip("% ").split(",")
    data = np.array([[float(v) for i, v in enumerate(line.split(",")) if i != 2 and v != ""]
                     for line in out[2:] if line and line[0] in "-0123456789"])
    total = data[-1, 0]
    x = total - data[:, 0]
    cols = {}
    for n in ns:
        j = 3 + (n - 1)  # 列: L, D, CMT, 1..(倍音)
        label = head[j]
        y = data[:, j - 1]  # CMT 列を除いたので 1 つずれる
        keep = np.concatenate([[True], np.diff(np.floor(x / step)) != 0])
        keep[-1] = True  # ベル開口(0 mm)を残す
        cols[str(n)] = {"label": label, "pts": [[round(float(a), 1), round(float(b), 2)] for a, b in zip(x[keep], y[keep])]}
    return {"total": round(float(total), 1), "modes": cols}


def read_imp(path: Path, step: int = 2) -> list[list[float]]:
    a = np.loadtxt(path, delimiter=",", skiprows=1)
    a = a[1::step]  # 0 Hz を除き、2 Hz ごと
    z = np.hypot(a[:, 1], a[:, 2])
    return [[round(float(f), 1), float(f"{v:.5g}")] for f, v in zip(a[:, 0], z)]


def read_res_db(path: Path) -> np.ndarray:
    """imppeak の .res の、各ピークの高さ (dB)。"""
    v = []
    for line in path.read_text().splitlines()[2:]:
        c = line.split(",")
        if len(c) >= 6:
            v.append(float(c[5]))
    return np.array(v)


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
    for name in ("bell02", "refhorn"):
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
    data = {"imp": {}, "cents": {}, "spd": {}, "db": {}}
    for key in ("Bb", "F"):
        base = HERE / f"bell02_{key}_rh"
        data["spd"][key] = spd(base.with_suffix(".men"), base.with_suffix(".res"))
    for name, key in CASES:
        base = HERE / f"{name}_{key}_rh"
        data["imp"][f"{name}_{key}"] = read_imp(base.with_suffix(".imp"))
        data["db"][f"{name}_{key}"] = [{"n": i + 1, "db": round(float(v), 2)}
                                       for i, v in enumerate(read_res_db(base.with_suffix(".res"))) if i + 1 <= N_MAX]
        data["cents"][f"{name}_{key}"] = [
            {"n": n, "note": nm, "f": round(float(f), 2), "c": round(float(c), 1)}
            for n, nm, f, c in cents_vs_series(read_res(base.with_suffix(".res")), key)
            if n <= N_MAX
        ]
    meta = {
        "a4": A4,
        "hand": HAND_L,
        "maxf": MAXF,
        "len": {f"{n}_{k}": round(men_length(HERE / f"{n}_{k}.men"), 1) for n, k in CASES},
        "extra": {k: round(v, 1) for k, v in f_extra().items()},
        "ref": REF_N,
        "f_above_bb": F_ABOVE_BB,
        "nmax": N_MAX,
        "bell02_len": round(X_END + D12_EXTRA, 2),
        "perturb": [{"a": a, "l0": l0, "lam": lam, "lo": round(l0 - lam / 2, 1), "hi": round(l0 + lam / 2, 1)}
                    for a, l0, w, lam in PERTURB],
    }
    tpl = (HERE / "report_template.html").read_text(encoding="utf-8")
    html = tpl.replace("/*DATA*/null", json.dumps(data, separators=(",", ":"))).replace(
        "/*META*/null", json.dumps(meta, separators=(",", ":")))
    out = HERE / "report.html"
    out.write_text(html, encoding="utf-8")
    print(f"-> {out} ({out.stat().st_size / 1e3:.0f} kB)")


if __name__ == "__main__":
    main()
