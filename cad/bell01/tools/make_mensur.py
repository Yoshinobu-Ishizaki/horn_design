"""bell01 のメンズール(L-D 表、1 mm 間隔)を関数 D = a/(x+b)^p + c + q·x から作る。

`mensur/bell/make_bell.ipynb` の関数 a/(x+b)^p + c に、1次の項 q·x を足したもの(q=0 で元と同じ):
- D(0) = DF(リム径)、D'(0) = 2·tan(ANG)(リムの開き角)、D(XL) = DB(細い側)。
- a, c は D'(0) と D(0) から、b は D(XL) = DB から決まる。p, ANG, Q が形を決める。

履歴:
- 2018-03-30: p=0.83081841、ANG=-80°、Q=0(D(120)=65 に合わせた)。
- 2026-11-22: flare を RefBell に似せて p=2.5、ANG=-68°、Q=0。中間部(L 300〜600)が 3〜5 mm 細くなった。
- 2026-11-22: Q を足して全長で RefBell に似せた。p=6、ANG=-67°、Q=-0.0227(差はリム以外 ±1.2 mm 以内)。

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
DB = 16.0  # 細い側の径 (mm)
XL = 850.0  # 長さ (mm)
P = 6.0  # 形の指数
ANG = -67.0  # リムの開き角 (deg)
Q = -0.0227  # 1次の項の係数 (mm/mm)


def coefficients(p: float = P, ang: float = ANG, q: float = Q, df: float = DF, xl: float = XL, db: float = DB):
    k = 2 * math.tan(math.radians(ang))

    def ac(b):
        a = -(k - q) * b ** (p + 1) / p  # D'(0) = -p·a·b^(-p-1) + q = k
        return a, df - a / b**p  # D(0) = a/b^p + c = df

    def f(x, b):
        a, c = ac(b)
        return a / (x + b) ** p + c + q * x

    b = brentq(lambda b: f(xl, b) - db, 1e-4, 1e7)
    a, c = ac(b)
    return a, b, c


def diameter(x, p: float = P, ang: float = ANG, q: float = Q):
    a, b, c = coefficients(p, ang, q)
    x = np.asarray(x, dtype=float)
    return a / (x + b) ** p + c + q * x


def main(argv: list[str]) -> None:
    out = Path(argv[1]) if len(argv) > 1 else WD / "bell01-ld.csv"
    a, b, c = coefficients()
    x = np.arange(0, XL + 0.5, 1.0)
    np.savetxt(out, np.column_stack([x, diameter(x)]), delimiter=",", header="x,y", comments="", fmt="%.10g")
    print(f"p={P} ang={ANG} q={Q} a={a:.6g} b={b:.6f} c={c:.6f}")
    for xi in [0, 10, 20, 50, 120, 200, 300, 500, 840.635, 850]:
        print(f"  D({xi}) = {float(diameter(xi)):.3f}")
    xs = np.arange(XL, 3000, 0.01)
    print(f"  D=12 at L = {xs[np.argmax(diameter(xs) <= 12)]:.2f}")
    print(f"-> {out}")


if __name__ == "__main__":
    main(sys.argv)
