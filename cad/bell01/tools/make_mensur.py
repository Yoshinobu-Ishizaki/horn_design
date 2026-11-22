"""bell01 のメンズール(L-D 表、1 mm 間隔)を関数 D = a/(x+b)^p + c + q·x から作る。

`mensur/bell/make_bell.ipynb` の関数 a/(x+b)^p + c に、1次の項 q·x を足したもの(q=0 で元と同じ):
- D(0) = DF(リム径)、D'(0) = 2·tan(ANG)(リムの開き角)、D(X_END) = D_END(1番管の終わり)。
- a, c は D'(0) と D(0) から、b は D(X_END) = D_END から決まる。p, ANG, Q が形を決める。
- 表は L = 0〜X_END。ベルは芯線の長さ(840.635)で切り、その先は1番管。

履歴:
- 2018-03-30: p=0.83081841、ANG=-80°、Q=0、D(850)=16(D(120)=65 に合わせた)。
- 2026-11-22: flare を RefBell に似せて p=2.5、ANG=-68°、Q=0、D(850)=16。中間部が 3〜5 mm 細くなった。
- 2026-11-22: Q を足して RefBell に似せた。p=6、ANG=-67°、Q=-0.0227、D(850)=16。D=12 は L=1022.7。
- 2026-11-22: D=12 を L=1350 にした(1番管を長く)。D(850)=16 の条件は外し、L≤840 で RefBell に当てはめた:
  p=4.025、ANG=-67.41°、Q=-0.01165(差はリム以外 -1.5〜+2.2 mm、ベルの終点 D=18.37)。音程は後で calcimp で確かめる。
- 2026-11-22: Bb 管の音程(a' = 442 Hz、右手 220 mm、impedance/bell01/tune_mensur.py)に合わせて、
  第2倍音 -20、第3倍音 -10、第6倍音 F4 +16 セントになる p=3.0515、ANG=-68.005°、Q=-0.009141、
  D=12 の L = 1332.66(Bb の全長が 17.3 mm 短くなる)。前の形からの差は直径の二乗平均で 0.85 mm。
- 2026-11-22: f'(Bb 管の第6倍音)に対して、第2倍音 -20、第3倍音 -10 セント(f' は +16)。
  p=2.3619、ANG=-68.759°、Q=-0.006187、D=12 の L = 1333.49。前の形からの差は 0.76 mm。
- 2026-11-22: 基本形を、Bb 管・F 管の 3→6・4→8 倍音のオクターブの幅が +10 セント前後になるように
  (impedance/bell01/tune_octaves.py。Bb 管の f' +16、F 管の f' = Bb 管 + 10)。p=2.1061、ANG=-70.733°、
  Q=-0.005524、D=12 の L = 1304.93。前の形からの差は 2.72 mm。最低音域は後で局所的な摂動で動かす。

    uv run python cad/bell01/tools/make_mensur.py [out.csv]
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

WD = Path(__file__).resolve().parent.parent
DF = 300.0  # リム径 (mm)
X_END, D_END = 1304.93, 12.0  # 1番管の終わりの L (mm) と径 (mm)
P = 2.1061  # 形の指数
ANG = -70.733  # リムの開き角 (deg)
Q = -0.005524  # 1次の項の係数 (mm/mm)
# 局所的な摂動(基本形に足す): (A, L0, w, lam) ごとに A·exp(-((L-L0)/w)^2)·cos(2π(L-L0)/lam)。L はリムからの距離 (mm)
# 2026-11-22: Bb 管の bb(第4倍音)を f' に近づける(impedance/bell01/tune_perturb.py、lam は第4倍音の半波長 730 mm に固定、
# w = lam/4.3 で約1波長に区切る。範囲はリムから 166〜896 mm)。bb − f' が +4.5 → +1.9 セント
PERTURB: list[tuple[float, float, float, float]] = [(0.158, 530.5, 730.0 / 4.3, 730.0)]
# ⌀12 になった先に足す ⌀12 の円筒 (mm)。1番管の末端の直線にあたり、Bb 管の f' を +16 セントに保つ
D12_EXTRA = 1.69


def coefficients(p: float = P, ang: float = ANG, q: float = Q, df: float = DF, xe: float = X_END, de: float = D_END):
    k = 2 * math.tan(math.radians(ang))

    def ac(b):
        a = -(k - q) * b ** (p + 1) / p  # D'(0) = -p·a·b^(-p-1) + q = k
        return a, df - a / b**p  # D(0) = a/b^p + c = df

    def f(x, b):
        a, c = ac(b)
        return a / (x + b) ** p + c + q * x

    b = brentq(lambda b: f(xe, b) - de, 1e-3, 1e7)
    a, c = ac(b)
    return a, b, c


def perturbation(x, items=None):
    """局所的な摂動 Σ A·exp(-((L-L0)/w)^2)·cos(2π(L-L0)/lam)(mm)。"""
    x = np.asarray(x, dtype=float)
    out = np.zeros_like(x)
    for a_, l0, w, lam in (PERTURB if items is None else items):
        t = (x - l0) / w
        out += a_ * np.exp(-t * t) * np.cos(2 * math.pi * (x - l0) / lam)
    return out


def diameter(x, p: float = P, ang: float = ANG, q: float = Q, xe: float = X_END, perturb=None):
    """D(L)。perturb は局所的な摂動の並び(None なら PERTURB)。D(xe) = D_END は基本形で決まり、
    摂動は xe の近くで 0 になるように置く。"""
    a, b, c = coefficients(p, ang, q, xe=xe)
    x = np.asarray(x, dtype=float)
    return a / (x + b) ** p + c + q * x + perturbation(x, perturb)


def main(argv: list[str]) -> None:
    out = Path(argv[1]) if len(argv) > 1 else WD / "bell01-ld.csv"
    a, b, c = coefficients()
    x = np.append(np.arange(0, X_END, 1.0), X_END)
    d = diameter(x)
    if np.any(np.diff(d) >= 0):
        raise ValueError("D が単調に減っていない")
    np.savetxt(out, np.column_stack([x, d]), delimiter=",", header="x,y", comments="", fmt="%.10g")
    print(f"p={P} ang={ANG} q={Q} a={a:.6g} b={b:.6f} c={c:.6f}")
    for xi in [0, 10, 20, 50, 120, 200, 300, 500, 840.635, 850, 1000, 1200, X_END]:
        print(f"  D({xi}) = {float(diameter(xi)):.3f}")
    print(f"-> {out}")


if __name__ == "__main__":
    main(sys.argv)
