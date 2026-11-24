"""1番管の細い端を L 字に曲げて、第 4 の 2 階右下の枝管(2 階左下の鏡像、valve4_knuckle.mirrored_twisted_knuckle_2f)につなぐ(2026-11-24)。

- 角 Q: 枝管の出口の軸とベル平面(ベルの芯線の平面)の交点。1番管の末端の直線の軸は Q を通る(make_centerline.BRANCH_END_DY)。
- 1番管は Q の手前 LEG_B1(= 出口から Q までと同じ長さ)で終わる(make_centerline.BRANCH_END_S)。
- そこから枝管の出口までを、bb34 の L 字管(cad/model202611/valve_assy/bb34/ocp/g2_l.py)と同じ形でつなぐ: 直線 + 5 次ベジェ(両端の曲率 0 = 直線と G2)+ 直線。
  平面は 1番管の末端の直線と出口の軸を含む平面。曲がりは Q から両側へ CORNER_LEG の所で始まり・終わる(左右同じ。小さいほど R が小さく、
  曲がりが Q へ寄る。2026-11-24: 主管補助管 1 と桂に当たったので小さくした)。枝管側の直線 = 出口〜Q − CORNER_LEG ≥ EN_MIN(5 mm)。
  その脚の中で最小曲げ半径が最大になる制御点にする。
- 管は 1番管の一部として、内径は 1番管のメンズール(make_mensur.diameter、L はリムから。⌀12 になる X_END の先は ⌀12)を末端まで当てはめる。板厚はベルと同じ。

    python3 cad/valves/ocp/warm.py run cad/model202611/body_assy/branch2/ocp/branch1_l.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(next(p for p in HERE.parents if p.name == "model202611")))
import model_paths  # noqa: E402

ROOT = model_paths.add()

EN_MIN = 5.0  # 枝管側の直線の最小長さ(ユーザー指示: 枝管の接続部に 5 mm 以上の直線)
CORNER_LEG = 33.5  # Q から曲がりの始まり・終わりまで(両側同じ)。--corner-leg。最大は 出口〜Q − EN_MIN。主管補助管 1 との表面距離 1 mm 以上(33.75 で 1.028、35 で 0.542)


def knuckle_exit():
    """第 4 の 2 階右下の枝管の出口の端面の中心と、外向きの軸(ワールド)。"""
    import valve4_knuckle as V

    a_ring = math.pi / 4 * (12.8**2 - 12.0**2)
    k = V.mirrored_twisted_knuckle_2f()
    f = max((f for f in k.faces() if f.geom_type.name == "PLANE" and abs(f.area - a_ring) < 0.5), key=lambda f: -f.normal_at().Y)
    return np.array(list(f.center())), np.array(list(f.normal_at()))


def corner(M):
    """角 Q(出口の軸とベル平面の交点)と、出口から Q までの長さ。"""
    P, a = knuckle_exit()
    N, org = M[:3, :3] @ np.array([0.0, 0.0, 1.0]), M[:3, 3]
    t = -float((P - org) @ N) / float(a @ N)
    return P + t * a, t


def solve_shape(E, ex, P, d2, st, en):
    """脚(st・en)を決めたときの 5 次ベジェの制御点の距離 (a, b, e, f)。最小曲げ半径が最大(差分進化、結果は覚える)。"""
    import g2_l as GL
    from shape_cache import memo_value

    def run():
        from scipy.optimize import differential_evolution

        ey, _ = GL.frame(E, ex, P, d2)
        hi = 1.2 * float(np.linalg.norm(P - E) - st - en) / 2  # 制御点は脚の長さ程度まで(広いと輪を描く解に落ちる)

        def cost(x):
            _, P2, _, _ = GL.ctrl(E, ex, ey, P, d2, (st, en, *x))
            kap, _ = GL.curvature(P2, 300)
            return float(np.abs(kap).max())

        return differential_evolution(cost, [(0.2, hi)] * 4, seed=0, maxiter=300, popsize=30, tol=1e-10, polish=True).x

    key = [round(float(x), 9) for x in [*E, *ex, *P, *d2, st, en]]
    return memo_value("branch1_l_shape", key, Path(__file__), run)


def mensur_tube(w, l_start, wall, plane_normal):
    """芯線 w(直線・ベジェ・直線)に沿って、内径 = 1番管のメンズール(L = l_start から)の管。辺ごとにコンパウンド。
    外側(内径 + 2·板厚)と内側(内径)の中実の管を掃引して引く(variable_pipe_wall の "sweep" は、曲線で内径が変わると
    内外の円の継ぎ目がずれて端のふたがねじれた。2026-11-24。板厚 0.4 で内径の変化はゆるいので、法線方向の厚みとの差は小さい)。"""
    from build123d import Compound, Wire

    from bope_claude_cad.vss import variable_pipe_law
    from make_mensur import X_END, diameter

    walls, l0 = [], l_start
    for e in w.edges():
        ss = np.linspace(0, e.length, 101)
        dd = diameter(np.minimum(l0 + ss, X_END))
        kw = {} if e.geom_type.name == "LINE" else {"binormal": tuple(float(x) for x in plane_normal)}
        outer, _ = variable_pipe_law(Wire([e]), ss, dd + 2 * wall, solid=True, **kw)
        inner, _ = variable_pipe_law(Wire([e]), ss, dd, solid=True, **kw)
        walls.append(outer - inner)
        l0 += e.length
    return Compound(walls)


def build(M, corner_leg=CORNER_LEG):
    """L 字の芯線と管。戻り値: (wire, tube, info)。"""
    import bell03_surface as BS
    import bell_place as BP
    import branch2_l as B2
    import g2_l as GL
    from make_centerline import build_branch_wire
    from make_mensur import X_END, diameter

    P, a = knuckle_exit()
    Q, leg = corner(M)
    E, ex = B2.branch1_end(M)  # 1番管の末端(ワールド)と向き
    ex = ex / np.linalg.norm(ex)
    d2 = -a  # 枝管へ入る向き
    _, nrm0 = GL.frame(E, ex, P, d2)
    P = P - float((P - E) @ nrm0) * nrm0  # 出口を L の平面へ射影(ずれは 1e-7 程度。そのままだとベジェの終点と直線が OCC の許容差を超えて離れる)
    leg_b1 = float((Q - E) @ ex)
    st, en = leg_b1 - corner_leg, leg - corner_leg
    if en < EN_MIN - 1e-9 or st < 0:
        raise ValueError(f"CORNER_LEG {corner_leg} は大きすぎる(枝管側の直線 {en:.3f} < {EN_MIN}、または 1番管側 {st:.3f} < 0)")
    v = (st, en, *solve_shape(E, ex, P, d2, st, en))
    lw, nrm, kap, clen = GL.wire(E, ex, P, d2, v)
    l_start = BS.centerline().length + build_branch_wire().length  # リムから 1番管の末端まで
    tube = mensur_tube(lw, l_start, BP.WALL, nrm)
    d_ends = diameter(np.minimum([l_start, l_start + lw.length], X_END))
    info = dict(P=P, a=a, Q=Q, leg=leg, E=E, ex=ex, st=st, en=en, clen=clen, rmin=1 / np.abs(kap).max(), kap=kap, nrm=nrm, l_start=l_start, d_ends=d_ends)
    return lw, tube, info


def hook(M, branch, others):
    import branch2_l as B2

    cl = float(sys.argv[sys.argv.index("--corner-leg") + 1]) if "--corner-leg" in sys.argv else CORNER_LEG
    lw, tube, i = build(M, cl)
    off = i["Q"] - i["E"]
    print(f"valve 4 floor-2 lower-right (mirror) exit {i['P'].round(3).tolist()}, axis {i['a'].round(4).tolist()}; corner Q (exit axis x bell plane) {i['Q'].round(3).tolist()}, exit -> Q {i['leg']:.3f}")
    print(f"branch1 end {i['E'].round(3).tolist()}, direction {i['ex'].round(5).tolist()}; Q - end: along {float(off @ i['ex']):.3f}, off the axis {np.linalg.norm(off - (off @ i['ex']) * i['ex']):.2e}")
    print(f"branch1 L (G2, corner legs {cl:g}): straight {i['st']:.3f} + quintic Bezier {i['clen']:.3f} + straight {i['en']:.3f} (knuckle side, >= {EN_MIN:g}) = {lw.length:.3f}; "
          f"min bend R {i['rmin']:.2f}, curvature ends {i['kap'][0]:.1e} / {i['kap'][-1]:.1e}; plane normal {i['nrm'].round(4).tolist()}")
    print(f"branch1 L tube: bore = branch1 mensur from L {i['l_start']:.3f}: D {i['d_ends'][0]:.3f} -> {i['d_ends'][1]:.3f} (knuckle bore 12.0); "
          f"valid {tube.is_valid}, volume {sum(x.volume for x in tube.solids()):.2f}")
    print("clearance (branch1 L):")
    B2.report_clearance(tube, others)
    return branch, [tube, lw], ["branch1_L_wall", "branch1_L_centerline"], ["#20c0a0", "#ff2020"]


def main() -> None:
    import assy_with_valves as AW

    AW.main(hook=hook)


if __name__ == "__main__":
    main()
