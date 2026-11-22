"""bell01(1番管 + ベル)を付けたホルンの入力インピーダンスを calcimp で計算し、Bb 管と F 管の音程を見る。

構成(マウスピース側から):
- 上流: kanutils のサンプル refhornBb000.men の x=0〜1413(マウスピース RefMP、吹込管、ロータリー・抜差管など。
  最後は ⌀12.0 の円筒)。RefHorn の T1(1番管にあたる部分)とベルの手前まで。
- bell01: メンズール関数(cad/bell01/tools/make_mensur.py)の L=1350(⌀12.00)から L=0(リム ⌀300)まで。
- 比較: RefHorn そのもの(refhornBb000.men)。
- F 管: 上流と 1番管の間に ⌀12.0 の円筒を足す。長さは、F 管の f'(第8倍音)が Bb 管の f'(第6倍音)より
  F_ABOVE_BB セント高くなるように決める(F 側の f' を Bb 側より少し高くしておく。低いと楽器として調整しにくい)。
  RefHorn も同じ方法で F 管を作る。
- 表示は第 N_MAX 倍音まで。
- 右手: kanutils の righthand(挿入深さ 220 mm)。メンズールを反転 → XY → 右手補正 → メンズール → 反転。

音程は、各倍音のピーク周波数を、Bb 管なら Bb1、F 管なら F1 の倍音列に最も近い平均律の音(A=440 Hz)と
比べたセント(A4 = 442 Hz)。calcimp の温度は既定の 24 ℃。

    uv run python impedance/bell01/intonation.py
"""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KAN = Path.home() / "develop/kanutils"
BIN = KAN / "src"
RefHorn = sorted(KAN.glob("sample/*Bb000.men"))[0]  # 上流のサンプル(kanutils/sample の *Bb000.men)
sys.path.insert(0, str(ROOT / "cad/bell01/tools"))
from make_mensur import D12_EXTRA, X_END, diameter  # noqa: E402

A4 = 442.0
UPSTREAM_END = "T1men"  # RefHorn の、この注記の行から先(T1 + ベル)を bell01 に置き換える
HAND_L = 220.0  # 右手の挿入深さ (mm)
MAXF, STEP = 1500.0, 1.0  # calcimp の最高周波数と刻み (Hz)
F_ABOVE_BB = 10.0  # F 管の f'(第8倍音)を Bb 管の f'(第6倍音)より何セント高くするか
REF_N = {"Bb": 6, "F": 8}  # f' にあたる倍音
N_MAX = 16  # 表示する倍音の上限
NOTE = ["c", "c#", "d", "eb", "e", "f", "f#", "g", "g#", "a", "bb", "b"]


def helmholtz(pc: int, octave: int) -> str:
    """ヘルムホルツ式の音名(c' = C4、c = C3、C = C2、C, = C1)。pc は c からの半音数。"""
    n = NOTE[pc]
    if octave >= 3:
        return n + "'" * (octave - 3)
    return n[0].upper() + n[1:] + "," * (2 - octave)
ROOTS = {"Bb": A4 * 2 ** (-35 / 12), "F": A4 * 2 ** (-40 / 12)}  # Bb1, F1(A4 = 442 で 58.54 Hz、43.85 Hz)


def read_refhorn() -> list[tuple[float, float, float, str]]:
    """refhornBb000.men(Shift-JIS、行末 CR)を (df, db, r, 注記) の行に。最終行(開口端)を除く。"""
    text = RefHorn.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n").decode("shift_jis")
    rows = []
    for line in text.splitlines()[1:]:
        f = line.split(",")
        if len(f) < 3 or not f[0].strip():
            continue
        df, db, r = float(f[0]), float(f[1]), float(f[2])
        if r == 0:  # 開口端の行
            continue
        rows.append((df, db, r, f[3].strip() if len(f) > 3 else ""))
    return rows


def bell01_rows(step: float = 1.0, d12_extra: float = D12_EXTRA, **mensur) -> list[tuple[float, float, float, str]]:
    """bell01 の ⌀12 の円筒(d12_extra、1番管の末端の直線)と、L=X_END(⌀12)から L=0(リム)まで。
    マウスピース側から並べる。mensur は diameter() の引数(p, ang, q, xe, perturb)。"""
    xe = mensur.get("xe", X_END)
    ls = np.append(np.arange(xe, 0, -step), 0.0)
    d = diameter(ls, **mensur)
    rows = [(float(d[i]), float(d[i + 1]), float(ls[i] - ls[i + 1]), "bell01") for i in range(len(ls) - 1)]
    return ([(12.0, 12.0, d12_extra, "bell01 d12")] if d12_extra > 0 else []) + rows


def write_men(path: Path, title: str, rows) -> None:
    lines = [title] + [f"{df:.6f},{db:.6f},{r:.6f},{c}" for df, db, r, c in rows]
    lines.append(f"{rows[-1][1]:.6f},0,0,")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(*args: str, out: Path | None = None) -> str:
    r = subprocess.run([str(BIN / args[0]), *args[1:]], capture_output=True, text=True, check=True)
    if out is not None:
        out.write_text(r.stdout)
    return r.stdout


def with_right_hand(men: Path) -> Path:
    """右手補正を掛けたメンズール(name_rh.men)を作る。"""
    base = men.with_suffix("")
    rev, xy, xyh, revh, out = (Path(f"{base}{s}") for s in ("_rev.men", "_rev.xy", "_rev_rh.xy", "_rev_rh.men", "_rh.men"))
    run("reversemen", str(men), out=rev)
    run("men2xy", str(rev), out=xy)
    run("righthand", "-L", str(HAND_L), str(xy), out=xyh)
    run("xy2men", str(xyh), out=revh)
    run("reversemen", str(revh), out=out)
    for p in (rev, xy, xyh, revh):
        p.unlink()
    return out


def peaks(men: Path) -> np.ndarray:
    """calcimp → imppeak。ピーク周波数の配列(低い順)。"""
    imp = men.with_suffix(".imp")
    run("calcimp", "-m", str(MAXF), "-s", str(STEP), "-o", str(imp), str(men))
    res = men.with_suffix(".res")
    run("imppeak", "-o", str(res), str(imp))
    f = []
    for line in res.read_text().splitlines()[2:]:
        c = line.split(",")
        if len(c) >= 4:
            f.append(float(c[3]))
    return np.array(f)


def cents_vs_series(freqs: np.ndarray, key: str) -> list[tuple[int, str, float, float]]:
    """倍音番号 n(ピークの低い順に 1, 2, …)、目標の平均律の音、周波数、セント。n=1(ペダル)も含む。"""
    root = ROOTS[key]
    out = []
    for n, f in enumerate(freqs, start=1):
        k = round(12 * math.log2(n * root / A4))  # A4 からの半音数(n 倍音に最も近い平均律の音)
        target = A4 * 2 ** (k / 12)
        name = helmholtz((k + 9) % 12, 4 + (k + 9) // 12)
        out.append((n, name, f, 1200 * math.log2(f / target)))
    return out


def build_rows(name: str, rows, out_dir: Path = HERE) -> Path:
    """行の並びからメンズールを書き、右手補正を掛けたメンズールを返す(out_dir に書く)。"""
    men = Path(out_dir) / f"{name}.men"
    write_men(men, name, list(rows))
    return with_right_hand(men)


def build(name: str, up_rows, tail_rows, extra: float) -> Path:
    rows = list(up_rows)
    if extra > 0:
        rows.append((12.0, 12.0, extra, "F extra"))
    return build_rows(name, rows + list(tail_rows))


def tune_f(name, up_rows, tail_rows, bb_ref_cents: float) -> tuple[float, Path]:
    """F 管の円筒の長さを、F 管の f'(第8倍音)が bb_ref_cents + F_ABOVE_BB セントになるように決める。"""
    def err(extra):
        men = build(name, up_rows, tail_rows, extra)
        c = {n: ct for n, _, _, ct in cents_vs_series(peaks(men), "F")}
        return c[REF_N["F"]] - (bb_ref_cents + F_ABOVE_BB)

    extra = brentq(err, 700, 1300, xtol=0.05)
    return extra, build(name, up_rows, tail_rows, extra)


def main() -> None:
    hr = read_refhorn()
    i_up = next(i for i, r in enumerate(hr) if UPSTREAM_END in r[3])
    up, hr_tail = hr[:i_up], hr[i_up:]
    b01 = bell01_rows()
    up_len = sum(r[2] for r in up)
    print(f"upstream (RefHorn x=0..{up_len:.1f}) + bell01 {X_END:.1f} = {up_len + X_END:.1f} mm; "
          f"RefHorn = {up_len + sum(r[2] for r in hr_tail):.1f} mm")

    res = {}
    for name, tail in [("bell01", b01), ("refhorn", hr_tail)]:
        res[(name, "Bb")] = cents_vs_series(peaks(build(f"{name}_Bb", up, tail, 0.0)), "Bb")
        bb_ref = next(c for n, _, _, c in res[(name, "Bb")] if n == REF_N["Bb"])
        extra, men = tune_f(f"{name}_F", up, tail, bb_ref)
        res[(name, "F")] = cents_vs_series(peaks(men), "F")
        print(f"{name}: F extra cylinder {extra:.1f} mm")

    lines = []
    for key in ("Bb", "F"):
        a = {n: (nm, f, c) for n, nm, f, c in res[("bell01", key)]}
        b = {n: (nm, f, c) for n, nm, f, c in res[("refhorn", key)]}
        lines.append(f"\n{key} horn (cents vs equal temperament, A={A4:.0f})")
        lines.append(" n  note     bell01 Hz  cents |  RefHorn Hz  cents | diff")
        for n in sorted(k for k in set(a) & set(b) if k <= N_MAX):
            lines.append(f"{n:2d}  {a[n][0]:5s} {a[n][1]:9.2f} {a[n][2]:+6.1f} | {b[n][1]:9.2f} {b[n][2]:+6.1f} | "
                         f"{a[n][2] - b[n][2]:+6.1f}")
    text = "\n".join(lines)
    print(text)
    (HERE / "intonation.txt").write_text(text.lstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
