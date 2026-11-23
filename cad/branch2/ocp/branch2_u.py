"""新しい 2番管(U 字、今は芯線だけ): 第 4 植込の 2 階・右下の枝管(valve4_knuckle.knuckle_2f_right、出口は +X)に、
U 字の片方の直線をつなぐ。曲がりは基本の U 字管(cad/bows/ocp/ubows.py、直管 LEG = 5)と同じで、ピッチ PITCH。

- 第 4 の枝管側の直線の軸(出口の軸、+X)まわりに U を回して、もう一方の直線の軸が、ベル・1番管の芯線の平面
  (設計の z = 0 の平面を組立の変換 M で動かした平面)に乗るようにする。解は 2 つあるので、1番管の横の直線に近い側。
- 内径は、後でメンズールをマップしてテーパーにする(今は芯線だけ)。
- 座標は管体組立のワールド。

    uv run python cad/branch2/ocp/branch2_u.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(ROOT / "cad/bellscrew/ocp"), str(ROOT / "cad/valves/ocp"), str(ROOT / "cad/bows/ocp"),
                str(ROOT / "cad/bell03/ocp"), str(ROOT / "cad/bell03/tools")]

PITCH = 50.0  # 50 → 40 → 60 → 50(ユーザー指示)


def valve4_exit():
    """第 4 の 2 階・右下の枝管の出口の端面の中心と、外向きの軸。"""
    import valve4_knuckle as V

    k = V.knuckle_2f_right()
    f = max((f for f in k.faces() if f.geom_type.name == "PLANE"), key=lambda f: f.center().X)
    c, n = f.center(), f.normal_at()
    return np.array([c.X, c.Y, c.Z]), np.array([n.X, n.Y, n.Z])


def u_wire_local(pitch):
    """基本の U 字管の芯線(ubows の座標: 左の直線の始端 (-P/2, 0) から +Y、右の直線の終端 (P/2, 0))。"""
    from build123d import Edge, Wire
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge

    import ubows

    _, info = ubows.u_bow(pitch)
    p, leg = pitch, ubows.LEG
    e2 = Edge(BRepBuilderAPI_MakeEdge(info["crv"]).Edge())
    return Wire([Edge.make_line((-p / 2, 0, 0), (-p / 2, leg, 0)), e2, Edge.make_line((p / 2, leg, 0), (p / 2, 0, 0))]), info


def placement(M, pitch=PITCH):
    """U の置き方: 左の直線の始端を第 4 の出口に、局所 +Y を出口の軸に、局所 +X(もう一方の直線への向き)を n に。
    n は出口の軸に垂直で、もう一方の直線(出口 + pitch·n を通り、出口の軸に平行)がベルの芯線の平面に乗る向き。"""
    import branch2_l as B2

    P0, a = valve4_exit()
    E, t = B2.branch1_end(M)
    N = M[:3, :3] @ np.array([0.0, 0.0, 1.0])  # ベルの芯線の平面の法線
    # n = cosφ·e1 + sinφ·e2(e1, e2 は a に垂直)。条件 (P0 + pitch·n - E)·N = 0
    e1 = np.cross(a, [0.0, 0.0, 1.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(a, e1)
    d0 = float((P0 - E) @ N)
    A, B = pitch * (e1 @ N), pitch * (e2 @ N)
    rr = math.hypot(A, B)
    if abs(d0) > rr:
        raise ValueError(f"ピッチ {pitch} では届かない(平面までの距離 {d0:.3f}、届く範囲 {rr:.3f})")
    base = math.atan2(B, A)
    dphi = math.acos(-d0 / rr)
    to_line = (E + ((P0 - E) @ t) * t) - P0  # 出口から 1番管の横の直線への垂線
    sols = []
    for phi in (base + dphi, base - dphi):
        n = math.cos(phi) * e1 + math.sin(phi) * e2
        sols.append((float(n @ to_line), n, phi))
    _, n, phi = max(sols, key=lambda x: x[0])
    R = np.column_stack([n, a, np.cross(n, a)])  # 局所 x → n、y → a、z → n × a
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = P0 - R @ np.array([-pitch / 2, 0.0, 0.0])
    return T, dict(P0=P0, a=a, n=n, phi=math.degrees(phi), N=N, E=E, t=t, d0=d0, to_line=to_line)


def main() -> None:
    import assy_with_valves as AW
    import bell_place as BP

    def hook(M, branch, others):
        w, info = u_wire_local(PITCH)
        T, pl = placement(M)
        ww = BP.apply(w, T)
        q1 = ww.position_at(1.0)
        t1 = ww.tangent_at(1.0)
        q1 = np.array([q1.X, q1.Y, q1.Z])
        print(f"valve 4 floor-2 lower-right exit {pl['P0'].round(3).tolist()}, axis {pl['a'].round(4).tolist()}")
        print(f"U pitch {PITCH:g}: curve {info['curve_len']:.3f} + legs 2 x 5, total {w.length:.3f}; min bend R {info['rmin']:.2f}, "
              f"height {info['h']:.2f}")
        print(f"rotation about the exit axis: n = {pl['n'].round(4).tolist()} (phi {pl['phi']:.2f} deg)")
        print(f"other leg end {q1.round(3).tolist()}, direction {np.round([t1.X, t1.Y, t1.Z], 4).tolist()}; "
              f"distance to the bell plane {float((q1 - pl['E']) @ pl['N']):+.4f}")
        off = q1 - pl["E"]
        perp = off - (off @ pl["t"]) * pl["t"]
        print(f"other leg axis vs branch1 cross straight: offset in the bell plane {np.linalg.norm(perp):.3f} "
              f"({perp.round(3).tolist()}), along {float(off @ pl['t']):+.3f}")
        # 長さ: リム → 1番管(U の直線の端まで)→ U → 第 4 の出口。1番管の末端は今 L = X_END(⌀12)
        import bell03_surface as BS
        from make_centerline import build_branch_wire
        from make_mensur import X_END

        l_bell = BS.centerline().length
        l_b1 = build_branch_wire().length
        along = float(off @ pl["t"])  # 1番管の末端から U の直線の端まで(負なら手前)
        l_b1_to_u = l_b1 + along
        total = l_bell + l_b1_to_u + w.length
        print(f"branch1 end -> U leg end along the straight: {along:+.3f} (branch1 up to the joint {l_b1_to_u:.3f})")
        print(f"rim -> valve 4 exit: bell {l_bell:.3f} + branch1 {l_b1_to_u:.3f} + U {w.length:.3f} = {total:.3f} "
              f"(D 12 at L {X_END:g}: {total - X_END:+.3f})")
        return branch, [ww], ["branch2_U_centerline"], ["#ff2020"]

    AW.main(hook=hook)


if __name__ == "__main__":
    main()
