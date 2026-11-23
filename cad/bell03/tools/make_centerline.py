"""bell01 と 1番管の芯線を寸法から作り、DXF に書き出す。

構成: 始点 (0,0)(リム側)から +Y へ直線 STRAIGHT → (時計回りの円弧 (R1, TH1)。TH1=0 なら無し)→ 渦巻き。
- ベルは、半径 RI の円板に当てて曲げる想定。直管部が円板に接する所から先は、管の内側が円板に沿う。
- ベルの渦巻き: 芯線と中心 C の距離を RI + D(L)/2 に保つ。管の各断面が半径 RI の円に接するので、
  曲げの内側のシルエットが円になる(直径 2·RI)。始点で接線が連続になるように C を置く。
  STRAIGHT を長くすると、円板が上に上がる(全体の高さが上がる)。
  ベルは L = TOTAL で終わる(メンズールの終点を変えないため)。
- 1番管: ベルの渦巻きをそのまま延ばし、内側の円の半径を RI から少しずつ減らして内側へ曲げる
  (減らし方は BRANCH_DRI·s^2、s は 1番管の中の 0〜1。始点で接線も曲率も連続)。
  渦巻きは途中でやめ、時計回りの円弧(半径 BRANCH_ARC_R)1つで、組立の基本姿勢(リム中心まわりに
  Z 軸で ASSEMBLY_ROT_Z 回した姿勢)で +X を向く直線につなぎ、直線で終わる。直線の高さは、組立姿勢で
  円板の中心より BRANCH_END_DY 上(暫定。valve section と組み立てるときに直す)。
  長さは、メンズール関数が D_BRANCH_END(12.00)になる L まで(bell03-ld.csv の最後の行)。

    uv run python cad/bell03/tools/make_centerline.py [out.dxf]
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
from scipy.optimize import brentq

WD = Path(__file__).resolve().parent.parent
LD_CSV = WD / "bell03-ld.csv"
TOTAL = 840.635  # ベルの芯線の全長 (mm)
STRAIGHT = 250.0  # 直線 (mm)。円板に接するまで
R1, TH1 = 100.0, 0.0  # 直線と渦巻きの間の円弧 (mm, deg)。0 なら円弧なし(直線から円板に巻き付ける)
RI = 137.5  # 曲げに使う円板の半径 (mm)。直径 275
BRANCH_DRI = 57.28  # 1番管で内側の円の半径を減らす量 (mm)。大きいほど内側へ曲がる
BRANCH_ARC_R = 40.0  # 1番管の渦巻きから末端の直線へつなぐ円弧の半径 (mm)。U ピッチ 50 で 40(ユーザー指示)。以前: 50 → 57(BRANCH_END_DY を上げたとき、隙間 1.4 の
# 最近接の所で渦巻きをやめる)→ 45(ユーザー指示: ベルと 1.4 ぐらいで並走する区間を増やし、1番管を長くする。
# 渦巻きは 1番管の中の 338.7 まで、隙間 1.397、1番管 576.568 で R57 より 9.1 長い)
BRANCH_EXIT_MIN = 150.0  # 渦巻きをやめる点を探し始める、1番管の中の長さ (mm)。手前の解はベルを横切る
BRANCH_END_DY = 7.569936  # 末端の直線の高さ: 組立姿勢で、円板の中心より上へ (mm)。2番管(U 字、cad/branch2/ocp/branch2_u.py)の
# 浮いている直線の軸に、まっすぐつながる高さ(2026-11-23。最初は 10、暫定。U のピッチ 40 で 19.385790、50 で 7.569936、60 で -3.531515)
BRANCH_END_S = 82.500070  # 末端の位置: 末端の直線の上で、基準点(円板の中心から組立姿勢で BRANCH_END_DY 上)から +X(組立姿勢)へ (mm)。
# 2番管(U 字、cad/branch2/ocp/branch2_u.py)との接続点(2026-11-23)。円弧の R を変えても末端はここ。
# 渦巻きの減らし方(BRANCH_DRI·s²)の s は、メンズールが ⌀12 になる L(l_branch_end)のまま
ASSEMBLY_ROT_Z = 15.0  # 管体組立の基本姿勢: リム中心まわりに Z 軸で回す角度 (deg、+Z から見て反時計回り)
N_SPIRAL = 161  # ベルの渦巻きのスプラインの通過点の数
N_BRANCH = 161  # 1番管のスプラインの通過点の数


def _profile():
    """D(L) と、1番管の終わりの L を返す。表(bell03-ld.csv)は ⌀12 になる L まで。その先の D12_EXTRA は ⌀12 の直線。"""
    from make_mensur import D12_EXTRA

    a = np.loadtxt(LD_CSV, delimiter=",", skiprows=1)
    sp = CubicSpline(a[:, 0], a[:, 1])
    xe = float(a[-1, 0])

    def D(ls, nu=0):
        ls = np.asarray(ls, dtype=float)
        v = sp(np.minimum(ls, xe), nu)
        return np.where(ls > xe, 0.0, v) if nu else v

    return D, xe + D12_EXTRA


def ri_of(ls, ri=RI, dri=BRANCH_DRI, l_branch_end=None):
    """L ごとの内側の円の半径。ベルでは一定、1番管で (s^2) で減る。"""
    ls = np.asarray(ls, dtype=float)
    s = np.clip((ls - TOTAL) / (l_branch_end - TOTAL), 0, 1)
    return ri - dri * s**2


def geometry(straight=STRAIGHT, r1=R1, th1=TH1, ri=RI, dri=BRANCH_DRI, n=N_SPIRAL, nb=N_BRANCH,
             arc_r=BRANCH_ARC_R, end_dy=BRANCH_END_DY, rot_z=ASSEMBLY_ROT_Z):
    """直線・円弧の端点と、渦巻き(ベル・1番管)の点列、1番管の円弧と直線を返す(設計の座標)。"""
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
    # 1番管: 渦巻きを L_exit でやめ、時計回りの円弧 arc_r で、組立姿勢の +X(設計の座標では -rot_z)を向く
    # 直線(円板の中心から組立姿勢で end_dy 上)へつなぐ。L_exit は、円弧の終点が直線に乗る L。
    h_end = math.radians(-rot_z)
    u_line = np.array([math.cos(h_end), math.sin(h_end)])
    n_line = np.array([-u_line[1], u_line[0]])  # 組立姿勢の +Y
    base = c + end_dy * n_line
    lb, pb, tb = ls[ib:], pts[ib:], tan[ib:]
    hb = np.unwrap(np.arctan2(tb[:, 1], tb[:, 0]))

    def right(q):
        return np.array([math.sin(q), -math.cos(q)])

    def arc_of(le):
        p = np.array([np.interp(le, lb, pb[:, 0]), np.interp(le, lb, pb[:, 1])])
        h = float(np.interp(le, lb, hb))
        h = h_end + (h - h_end) % (2 * math.pi)  # 時計回りに h_end まで回す角度を 0〜2π に
        ca = p + arc_r * right(h)
        pe = ca - arc_r * right(h_end)
        return p, h, ca, pe, h - h_end

    def miss(le):
        return float((arc_of(le)[3] - base) @ n_line)

    grid = np.linspace(TOTAL + BRANCH_EXIT_MIN, l_end - 1.0, 3000)  # 渦巻きをやめるのは 1番管の中の BRANCH_EXIT_MIN 以降
    f = np.array([miss(x) for x in grid])
    l_exit = None
    for k in range(len(grid) - 1):
        if f[k] * f[k + 1] < 0 and abs(f[k]) < 50:
            le = brentq(miss, grid[k], grid[k + 1], xtol=1e-9)
            if l_end - le - arc_r * arc_of(le)[4] >= 0:
                l_exit = le
                break
    if l_exit is None:
        raise ValueError("1番管の渦巻きから直線へつなぐ円弧が見つからない(BRANCH_ARC_R・BRANCH_END_DY を見直す)")
    p_ex, h_ex, ca, pe, sweep = arc_of(l_exit)
    a0 = math.atan2(p_ex[1] - ca[1], p_ex[0] - ca[0])
    pm = ca + arc_r * np.array([math.cos(a0 - sweep / 2), math.sin(a0 - sweep / 2)])
    straight_len = l_end - l_exit - arc_r * sweep
    p_end = pe + straight_len * u_line
    # 渦巻き部分の通過点は、L = TOTAL〜l_exit の等間隔で取り直す(細かい点列の添字で取って終点を足すと、
    # 終点の直前の点が近すぎることがあり、スプラインが壊れて MakePipeShell が落ちた)
    lq = np.linspace(TOTAL, l_exit, nb)
    branch = np.column_stack([np.interp(lq, lb, pb[:, 0]), np.interp(lq, lb, pb[:, 1])])
    branch[-1] = p_ex
    return {"q0": q0, "qm": qm, "q1": q1, "c1": c1, "c": c, "ri": ri,
            "spiral": pts[bell_idx], "spiral_tan": tan[bell_idx[[0, -1]]],
            "branch": branch, "branch_tan": np.array([tan[ib], [math.cos(h_ex), math.sin(h_ex)]]),
            "arc": (p_ex, pm, pe), "arc_centre": ca, "arc_sweep": sweep, "line": (pe, p_end),
            "l_exit": l_exit, "straight_len": straight_len,
            "L_fine": ls, "fine": pts, "tan_fine": tan, "l_branch_end": l_end}


def _v(p) -> Vector:
    return Vector(float(p[0]), float(p[1]), 0)


def build_wire(**kw) -> Wire:
    """ベルの芯線(L = 0〜TOTAL)。渦巻きはスプライン。"""
    g = geometry(**kw)
    t0, t1 = g["spiral_tan"]
    edges = [Line(_v((0, 0)), _v(g["q0"]))]
    if np.linalg.norm(g["q1"] - g["q0"]) > 1e-9:  # TH1 = 0 なら円弧なし(直線から直接渦巻き)
        edges.append(ThreePointArc(_v(g["q0"]), _v(g["qm"]), _v(g["q1"])))
    # tangent_scalars を省くと build123d が接線を拡大し、点の間隔と合わずに端にフックができる
    edges.append(Spline(*[_v(p) for p in g["spiral"]], tangents=(_v(t0), _v(t1)), tangent_scalars=(1.0, 1.0)))
    return Wire(edges)


def build_branch_wire(**kw) -> Wire:
    """1番管の芯線(ベルの終点から D=12 の L まで)。渦巻き(スプライン)→ 円弧 BRANCH_ARC_R → 直線。"""
    g = geometry(**kw)
    t0, t1 = g["branch_tan"]
    a0, am, a1 = g["arc"]
    edges = [
        Spline(*[_v(p) for p in g["branch"]], tangents=(_v(t0), _v(t1)), tangent_scalars=(1.0, 1.0)),
        ThreePointArc(_v(a0), _v(am), _v(a1)),
    ]
    # 末端の直線は、基準点から BRANCH_END_S の所(2番管との接続点)まで。
    # 1番管のメンズールは、ベルの実際の長さから始める(bell03_surface.py)。
    l0, l1 = g["line"]
    u = (l1 - l0) / np.linalg.norm(l1 - l0)
    base = g["c"] + kw.get("end_dy", BRANCH_END_DY) * np.array([-u[1], u[0]])
    rest = BRANCH_END_S - float((l0 - base) @ u)
    edges.append(Line(_v(l0), _v(l0 + rest * u)))
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
    if abs(a0 - a1) > 1e-9:
        msp.add_arc(tuple(c1), float(np.linalg.norm(g["q0"] - c1)), a1, a0)
    for key, layer in [("spiral", "0"), ("branch", "branch1")]:
        tt = g[f"{key}_tan"]
        s = msp.add_spline(fit_points=[tuple(p) for p in g[key]], dxfattribs={"layer": layer})
        s.dxf.start_tangent = (*tt[0], 0)
        s.dxf.end_tangent = (*tt[1], 0)
    ca, (a0p, _, a1p) = g["arc_centre"], g["arc"]
    s0 = math.degrees(math.atan2(a0p[1] - ca[1], a0p[0] - ca[0]))
    s1 = math.degrees(math.atan2(a1p[1] - ca[1], a1p[0] - ca[0]))
    msp.add_arc(tuple(ca), BRANCH_ARC_R, s1, s0, dxfattribs={"layer": "branch1"})  # 時計回りなので終点側から
    msp.add_line(tuple(g["line"][0]), tuple(g["line"][1]), dxfattribs={"layer": "branch1"})
    msp.add_circle(tuple(g["c"]), g["ri"], dxfattribs={"layer": "inner_circle"})  # 参考
    doc.saveas(out)


def main(argv: list[str]) -> None:
    out = Path(argv[1]) if len(argv) > 1 else WD / "bell03-ctr.dxf"
    g = geometry()
    w, wb = build_wire(), build_branch_wire()
    write_dxf(out)
    for name, x in [("bell", w), ("branch1", wb)]:
        e, te = x.position_at(1), x.tangent_at(1)
        print(f"{name}: length {x.length:.3f} end ({e.X:.3f},{e.Y:.3f}) dir {math.degrees(math.atan2(te.Y, te.X)):.2f}")
    print(f"bell length target {TOTAL}, branch1 ends at the joint (BRANCH_END_S {BRANCH_END_S}); "
          f"D 12 at branch1 {g['l_branch_end'] - TOTAL:.3f}")
    print(f"joint tangent gap {(w.tangent_at(1) - wb.tangent_at(0)).length:.2e}, position gap {(w.position_at(1) - wb.position_at(0)).length:.2e}")
    print(f"inner circle: centre ({g['c'][0]:.3f},{g['c'][1]:.3f}) R {RI} (D {2 * RI}); branch RI -> {RI - BRANCH_DRI}")
    print(f"branch1: spiral to L {g['l_exit'] - TOTAL:.3f}, arc R{BRANCH_ARC_R} {math.degrees(g['arc_sweep']):.2f} deg, "
          f"straight {g['straight_len']:.3f}")
    print(f"-> {out}")


if __name__ == "__main__":
    main(sys.argv)
