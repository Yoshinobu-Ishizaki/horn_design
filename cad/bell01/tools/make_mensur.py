"""bell01 のメンズール(L-D 表、1 mm 間隔)を関数 D = a/(x+b)^p + c から作る。

`mensur/bell/make_bell.ipynb` と同じ関数と条件:
- D(0) = DF(リム径)、D'(0) = 2·tan(ANG)(リムの開き角)、D(XL) = DB(細い側)。
- p は形の指数。a, c は D'(0) と D(0) から、b は D(XL) = DB から決まる。

元(2018-03-30)は p=0.83081841、ANG=-80°(D(120)=65 に合わせた)。flare が細かったので、
RefBell の flare(L ≤ 300)に近づけて p=2.5、ANG=-68° にした(2026-11-22)。

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
P = 2.5  # 形の指数
ANG = -68.0  # リムの開き角 (deg)


def coefficients(p: float = P, ang: float = ANG, df: float = DF, xl: float = XL, db: float = DB):
    k = 2 * math.tan(math.radians(ang))

    def ac(b):
        a = -k * b ** (p + 1) / p
        return a, df - a / b**p

    def f(x, b):
        a, c = ac(b)
        return a / (x + b) ** p + c

    b = brentq(lambda b: f(xl, b) - db, 1e-4, 1e6)
    a, c = ac(b)
    return a, b, c


def diameter(x, p: float = P, ang: float = ANG):
    a, b, c = coefficients(p, ang)
    return a / (np.asarray(x, dtype=float) + b) ** p + c


def main(argv: list[str]) -> None:
    out = Path(argv[1]) if len(argv) > 1 else WD / "bell01-ld.csv"
    a, b, c = coefficients()
    x = np.arange(0, XL + 0.5, 1.0)
    np.savetxt(out, np.column_stack([x, diameter(x)]), delimiter=",", header="x,y", comments="", fmt="%.10g")
    print(f"p={P} ang={ANG} a={a:.6f} b={b:.6f} c={c:.6f}")
    for xi in [0, 10, 20, 50, 120, 200, 300, 500, 840.635, 850]:
        print(f"  D({xi}) = {float(diameter(xi)):.3f}")
    print(f"-> {out}")


if __name__ == "__main__":
    main(sys.argv)
