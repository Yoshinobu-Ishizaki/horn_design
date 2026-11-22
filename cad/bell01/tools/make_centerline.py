"""bell01 の芯線を寸法から作り、DXF に書き出す。

構成: 始点 (0,0)(リム側)から +Y へ直線 STRAIGHT → 時計回りの円弧 (R1, TH1) → 渦巻き(終点まで)。
渦巻きは、巻きの内側のシルエットが中心 C・半径 RI の円になるように、芯線と C の距離を RI + D(L)/2 に保つ
(管の各断面が、内側の円に接する)。D(L) は bell01-ld.csv。始点で円弧と接線が連続になるように C を置く。
全長は TOTAL(メンズールの終点を変えないため)。

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
TOTAL = 840.635  # 芯線の全長 (mm)
STRAIGHT = 275.0  # 直線 (mm)
R1, TH1 = 125.0, 58.0  # 円弧の半径 (mm) と角度 (deg)
RI = 142.5  # 巻きの内側のシルエットの円の半径 (mm)。直径 285
N_SPIRAL = 161  # 渦巻きの点の数(スプラインの通過点)


def _profile():
    a = np.loadtxt(LD_CSV, delimiter=",", skiprows=1)
    return CubicSpline(a[:, 0], a[:, 1])


def geometry(straight=STRAIGHT, r1=R1, th1=TH1, ri=RI, n=N_SPIRAL):
    """直線・円弧の端点と、渦巻きの点列を返す。"""
    D = _profile()
    q0 = np.array([0.0, straight])
    h0 = math.radians(90.0)
    c1 = q0 + r1 * np.array([math.sin(h0), -math.cos(h0)])  # 時計回り: 中心は右
    a0 = math.atan2(q0[1] - c1[1], q0[0] - c1[0])
    a1 = a0 - math.radians(th1)
    q1 = c1 + r1 * np.array([math.cos(a1), math.sin(a1)])
    qm = c1 + r1 * np.array([math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2)])
    h1 = h0 - math.radians(th1)
    l1 = straight + r1 * math.radians(th1)
    # 渦巻き: rho(L) = RI + r(L)、d(phi)/dL = -sqrt(1 - r'^2)/rho(時計回り)
    t = np.array([math.cos(h1), math.sin(h1)])
    right = np.array([t[1], -t[0]])
    drl = float(D(l1, 1)) / 2
    u = drl * t - math.sqrt(1 - drl**2) * right  # C から始点への単位ベクトル
    rho0 = ri + float(D(l1)) / 2
    c = q1 - rho0 * u
    ls = np.linspace(l1, TOTAL, 4001)
    r = D(ls) / 2
    dr = D(ls, 1) / 2
    phi = math.atan2(u[1], u[0]) - cumulative_trapezoid(np.sqrt(1 - dr**2) / (ri + r), ls, initial=0)
    rho = ri + r
    pts = c + rho[:, None] * np.column_stack([np.cos(phi), np.sin(phi)])
    idx = np.linspace(0, len(ls) - 1, n).round().astype(int)
    return {"q0": q0, "qm": qm, "q1": q1, "c1": c1, "c": c, "spiral": pts[idx], "L_spiral": ls[idx],
            "spiral_fine": pts, "L_fine": ls, "ri": ri}


def build_wire(**kw) -> Wire:
    g = geometry(**kw)
    v = lambda p: Vector(float(p[0]), float(p[1]), 0)  # noqa: E731
    sp = g["spiral"]
    t0 = sp[1] - sp[0]
    t1 = sp[-1] - sp[-2]
    edges = [
        Line(v((0, 0)), v(g["q0"])),
        ThreePointArc(v(g["q0"]), v(g["qm"]), v(g["q1"])),
        Spline(*[v(p) for p in sp], tangents=(v(t0).normalized(), v(t1).normalized())),
    ]
    return Wire(edges)


def write_dxf(out: Path, **kw) -> None:
    g = geometry(**kw)
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    msp.add_line((0, 0), tuple(g["q0"]))
    c1 = g["c1"]
    a0 = math.degrees(math.atan2(g["q0"][1] - c1[1], g["q0"][0] - c1[0]))
    a1 = math.degrees(math.atan2(g["q1"][1] - c1[1], g["q1"][0] - c1[0]))
    msp.add_arc(tuple(c1), R1 if not kw else kw.get("r1", R1), a1, a0)
    sp = g["spiral"]
    t0, t1 = sp[1] - sp[0], sp[-1] - sp[-2]
    msp.add_spline_control_frame  # noqa: B018 (ezdxf の存在確認だけ)
    s = msp.add_spline(fit_points=[tuple(p) for p in sp])
    s.dxf.start_tangent = (*(t0 / np.linalg.norm(t0)), 0)
    s.dxf.end_tangent = (*(t1 / np.linalg.norm(t1)), 0)
    # 内側の円(参考)
    msp.add_circle(tuple(g["c"]), g["ri"], dxfattribs={"layer": "inner_circle"})
    doc.saveas(out)


def main(argv: list[str]) -> None:
    out = Path(argv[1]) if len(argv) > 1 else WD / "bell01-ctr.dxf"
    w = build_wire()
    g = geometry()
    write_dxf(out)
    end = w.position_at(1)
    te = w.tangent_at(1)
    bb = w.bounding_box()
    print(f"length {w.length:.3f} (target {TOTAL}) end ({end.X:.3f},{end.Y:.3f}) dir {math.degrees(math.atan2(te.Y, te.X)):.2f}")
    print(f"bbox x {bb.min.X:.1f}..{bb.max.X:.1f} y {bb.min.Y:.1f}..{bb.max.Y:.1f}")
    print(f"inner circle: centre ({g['c'][0]:.3f},{g['c'][1]:.3f}) R {RI} (D {2 * RI})")
    print(f"-> {out}")


if __name__ == "__main__":
    main(sys.argv)
