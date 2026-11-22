"""bell01 と 1番管の芯線を寸法から作り、DXF に書き出す。

構成: 始点 (0,0)(リム側)から +Y へ直線 STRAIGHT → (時計回りの円弧 (R1, TH1)。TH1=0 なら無し)→ 渦巻き。
- ベルは、半径 RI の円板に当てて曲げる想定。直管部が円板に接する所から先は、管の内側が円板に沿う。
- ベルの渦巻き: 芯線と中心 C の距離を RI + D(L)/2 に保つ。管の各断面が半径 RI の円に接するので、
  曲げの内側のシルエットが円になる(直径 2·RI)。始点で接線が連続になるように C を置く。
  STRAIGHT を長くすると、円板が上に上がる(全体の高さが上がる)。
  ベルは L = TOTAL で終わる(メンズールの終点を変えないため)。
- 1番管: ベルの渦巻きをそのまま延ばし、内側の円の半径を RI から RI - BRANCH_DRI へ少しずつ減らして
  内側へ曲げる(減らし方は (s^2)、s は 1番管の中の 0〜1。始点で接線も曲率も連続)。
  長さは、メンズール関数が D_BRANCH_END(12.00)になる L まで(bell01-ld.csv の最後の行)。

    uv run python cad/bell01/tools/make_centerline.py [out.dxf]
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import ezdxf
import numpy as np
from build123d import Line, Spline, ThreePointArc, Vector, Wire
from scipy.integrate import cumulative_trapezoid
from scipy.interpolate import CubicSpline

WD = Path(__file__).resolve().parent.parent
LD_CSV = WD / "bell01-ld.csv"
TOTAL = 840.635  # ベルの芯線の全長 (mm)
STRAIGHT = 250.0  # 直線 (mm)。円板に接するまで
R1, TH1 = 100.0, 0.0  # 直線と渦巻きの間の円弧 (mm, deg)。0 なら円弧なし(直線から円板に巻き付ける)
RI = 137.5  # 曲げに使う円板の半径 (mm)。直径 275
BRANCH_DRI = 42.33  # 1番管で内側の円の半径を減らす量 (mm)。大きいほど内側へ曲がる
N_SPIRAL = 161  # ベルの渦巻きのスプラインの通過点の数
N_BRANCH = 161  # 1番管のスプラインの通過点の数


def _profile():
    a = np.loadtxt(LD_CSV, delimiter=",", skiprows=1)
    return CubicSpline(a[:, 0], a[:, 1]), float(a[-1, 0])


def ri_of(ls, ri=RI, dri=BRANCH_DRI, l_branch_end=None):
    """L ごとの内側の円の半径。ベルでは一定、1番管で (s^2) で減る。"""
    ls = np.asarray(ls, dtype=float)
    s = np.clip((ls - TOTAL) / (l_branch_end - TOTAL), 0, 1)
    return ri - dri * s**2


def geometry(straight=STRAIGHT, r1=R1, th1=TH1, ri=RI, dri=BRANCH_DRI, n=N_SPIRAL, nb=N_BRANCH):
    """直線・円弧の端点と、渦巻き(ベル・1番管)の点列を返す。"""
    D, l_end = _profile()
    q0 = np.array([0.0, straight])
    h0 = math.radians(90.0)
    c1 = q0 + r1 * np.array([math.sin(h0), -math.cos(h0)])  # 時計回り: 中心は右
    a0 = math.atan2(q0[1] - c1[1], q0[0] - c1[0])
    a1 = a0 - math.radians(th1)
    q1 = c1 + r1 * np.array([math.cos(a1), math.sin(a1)])
    qm = c1 + r1 * np.array([math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2)])
    h1 = h0 - math.radians(th1)
    l1 = straight + r1 * math.radians(th1)
    # 渦巻き: rho(L) = Ri(L) + r(L)、d(phi)/dL = -sqrt(1 - rho'^2)/rho(時計回り)
    ls = np.unique(np.concatenate([np.linspace(l1, TOTAL, 6001), np.linspace(TOTAL, l_end, 2001)]))
    rho = ri_of(ls, ri, dri, l_end) + D(ls) / 2
    drho = np.gradient(rho, ls)
    drho[ls <= TOTAL] = D(ls[ls <= TOTAL], 1) / 2  # ベルでは厳密に r'
    t = np.array([math.cos(h1), math.sin(h1)])
    right = np.array([t[1], -t[0]])
    u = drho[0] * t - math.sqrt(1 - drho[0] ** 2) * right  # C から始点への単位ベクトル
    c = q1 - rho[0] * u
    phi = math.atan2(u[1], u[0]) - cumulative_trapezoid(np.sqrt(1 - drho**2) / rho, ls, initial=0)
    pts = c + rho[:, None] * np.column_stack([np.cos(phi), np.sin(phi)])
    # 接線(単位ベクトル): dP/dL = rho' u + rho dphi/dL u_perp
    uu = np.column_stack([np.cos(phi), np.sin(phi)])
    up = np.column_stack([-np.sin(phi), np.cos(phi)])
    tan = drho[:, None] * uu - np.sqrt(1 - drho**2)[:, None] * up
    ib = int(np.searchsorted(ls, TOTAL))
    bell_idx = np.unique(np.linspace(0, ib, n).round().astype(int))
    br_idx = np.unique(np.linspace(ib, len(ls) - 1, nb).round().astype(int))
    return {"q0": q0, "qm": qm, "q1": q1, "c1": c1, "c": c, "ri": ri,
            "spiral": pts[bell_idx], "spiral_tan": tan[bell_idx[[0, -1]]],
            "branch": pts[br_idx], "branch_tan": tan[br_idx[[0, -1]]],
            "L_fine": ls, "fine": pts, "l_branch_end": l_end}


def _v(p) -> Vector:
    return Vector(float(p[0]), float(p[1]), 0)


def build_wire(**kw) -> Wire:
    """ベルの芯線(L = 0〜TOTAL)。"""
    g = geometry(**kw)
    t0, t1 = g["spiral_tan"]
    edges = [Line(_v((0, 0)), _v(g["q0"]))]
    if np.linalg.norm(g["q1"] - g["q0"]) > 1e-9:  # TH1 = 0 なら円弧なし(直線から直接渦巻き)
        edges.append(ThreePointArc(_v(g["q0"]), _v(g["qm"]), _v(g["q1"])))
    edges.append(Spline(*[_v(p) for p in g["spiral"]], tangents=(_v(t0), _v(t1))))
    return Wire(edges)


def build_branch_wire(**kw) -> Wire:
    """1番管の芯線(L = TOTAL〜D=12 の L)。始点はベルの終点。"""
    g = geometry(**kw)
    t0, t1 = g["branch_tan"]
    return Wire([Spline(*[_v(p) for p in g["branch"]], tangents=(_v(t0), _v(t1)))])


def write_dxf(out: Path, **kw) -> None:
    g = geometry(**kw)
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    msp.add_line((0, 0), tuple(g["q0"]))
    c1 = g["c1"]
    a0 = math.degrees(math.atan2(g["q0"][1] - c1[1], g["q0"][0] - c1[0]))
    a1 = math.degrees(math.atan2(g["q1"][1] - c1[1], g["q1"][0] - c1[0]))
    if abs(a0 - a1) > 1e-9:
        msp.add_arc(tuple(c1), float(np.linalg.norm(g["q0"] - c1)), a1, a0)
    for key, layer in [("spiral", "0"), ("branch", "branch1")]:
        tt = g[f"{key}_tan"]
        s = msp.add_spline(fit_points=[tuple(p) for p in g[key]], dxfattribs={"layer": layer})
        s.dxf.start_tangent = (*tt[0], 0)
        s.dxf.end_tangent = (*tt[1], 0)
    msp.add_circle(tuple(g["c"]), g["ri"], dxfattribs={"layer": "inner_circle"})  # 参考
    doc.saveas(out)


def main(argv: list[str]) -> None:
    out = Path(argv[1]) if len(argv) > 1 else WD / "bell01-ctr.dxf"
    g = geometry()
    w, wb = build_wire(), build_branch_wire()
    write_dxf(out)
    for name, x in [("bell", w), ("branch1", wb)]:
        e, te = x.position_at(1), x.tangent_at(1)
        print(f"{name}: length {x.length:.3f} end ({e.X:.3f},{e.Y:.3f}) dir {math.degrees(math.atan2(te.Y, te.X)):.2f}")
    print(f"bell length target {TOTAL}, branch1 target {g['l_branch_end'] - TOTAL:.3f}")
    print(f"joint tangent gap {(w.tangent_at(1) - wb.tangent_at(0)).length:.2e}, position gap {(w.position_at(1) - wb.position_at(0)).length:.2e}")
    print(f"inner circle: centre ({g['c'][0]:.3f},{g['c'][1]:.3f}) R {RI} (D {2 * RI}); branch RI -> {RI - BRANCH_DRI}")
    print(f"-> {out}")


if __name__ == "__main__":
    main(sys.argv)
