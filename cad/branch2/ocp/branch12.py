"""1番管(新しい道筋)+ 2番管を、管体組立と一緒に表示する。

- 2番管: branch2_l.py の L 字(第 4 の枝管の出口から、1番管の横の直線の点 Q へ)。ほかの部品との隙間 GAP 以上。
  内径はメンズールのつづき(⌀12 になる L = X_END より先は ⌀12)。
- 1番管: tools/branch1_route.py の道筋(ベルの曲げの内側に隙間 1.4 で沿って上へ、右下へ向きを変えて横の直線へ)。
  長さは、リムから第 4 の出口までが、今の 1番管の末端(L = X_END = 1450、⌀12.00)より MARGIN だけ長くなるように。
  内径はメンズール(L が X_END を超えた所は ⌀12)。⌀12 の直管の分は 2番管の側に来る。

    uv run python cad/branch2/ocp/branch12.py [--cut 105]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(ROOT / "cad/branch2/tools"), str(ROOT / "cad/bellscrew/ocp"),
                str(ROOT / "cad/valves/ocp"), str(ROOT / "cad/bell03/ocp"), str(ROOT / "cad/bell03/tools")]

MARGIN = 4.5  # リムから第 4 の出口までの長さを、L = X_END(⌀12 になる所)より長くする量 (mm)。この分が 2番管の出口側の
# ⌀12 の直管(ユーザー指示: 最低 4 mm。最適化の誤差のぶん 0.5 足す)
STRAIGHT_END = 30.0  # 1番管の細い端(2番管との接続点の手前)に必ず残す横の直線 (mm)。あとで調整


def branch1_wire(r):
    """branch1_route.solve_route の結果から、1番管の芯線(設計の座標、z = 0)。A+B はスプライン、C はベジエ、直線。"""
    from build123d import Edge, Line, Spline, Vector, Wire

    import branch1_route as R

    ab = r["ab"]
    pts = ab["pts"]
    s = R.arclen(pts)
    ss = np.linspace(0, s[-1], max(40, int(s[-1] / 3)))  # 約 3 mm 間隔に取り直す
    q = np.column_stack([np.interp(ss, s, pts[:, 0]), np.interp(ss, s, pts[:, 1])])
    q[-1] = pts[-1]
    g = ab["g"]
    t0 = g["branch_tan"][0]
    v = lambda p: Vector(float(p[0]), float(p[1]), 0)  # noqa: E731
    sp = Spline(*[v(p) for p in q], tangents=(v(t0), v(ab["t_end"])), tangent_scalars=(1.0, 1.0))
    c = Edge.make_bezier(*[v(p) for p in r["cp"]])
    qq = r["l0"] + r["tau_q"] * r["u"]
    return Wire([sp, c, Line(v(r["cp"][-1]), v(qq))])


def main() -> None:
    import assy_with_valves as AW
    import bell_place as BP
    import branch1_route as R
    import branch2_l as B2

    cut = float(sys.argv[sys.argv.index("--cut") + 1]) if "--cut" in sys.argv else B2.CUT

    def hook(M, branch, others):
        from build123d import Wire

        import bell03_surface as BS
        from bope_claude_cad.vss import variable_pipe_wall
        from make_centerline import build_branch_wire
        from make_mensur import X_END, diameter

        # 2番管
        tree = B2.obstacle_tree(others, M)
        def r_of_s(sl):  # 2番管の外半径(出口からの長さ)。リム→出口を X_END + MARGIN とみなす
            return diameter(np.minimum(X_END + MARGIN - sl, X_END)) / 2 + BP.WALL
        d = B2.design(M, cut, tree, r_of_s)
        edges2 = B2.centerline_edges(d)
        len2 = sum(e.length for e in edges2)
        # 1番管: 直線上の点 Q の τ(設計の座標で、今の直線の始点から)
        old = build_branch_wire()
        g = R._bell()[0]
        l0, u = R.line_frame(g)
        e_d = old.position_at(1.0)
        tau_end = float((np.array([e_d.X, e_d.Y]) - l0) @ u)
        tau_q = tau_end - cut
        need = old.length - ((old.length - cut) + len2) + MARGIN  # 今の 1番管より長くする量
        l0b = BS.centerline().length
        for _ in range(3):  # 道筋の最適化の中の長さ(点列)と、実際の芯線の長さの差を、目標から差し引いて解き直す
            r = R.solve_route(need, tau_q, straight_end=STRAIGHT_END)
            w1 = branch1_wire(r)
            err = (l0b + w1.length + len2) - (X_END + MARGIN)
            print(f"  route: rim -> exit {l0b + w1.length + len2:.3f} (target {X_END + MARGIN:.3f}, err {err:+.3f})")
            if abs(err) < 0.2:
                break
            need -= err
        Lb = np.linspace(0, w1.length, 401)
        Db = diameter(np.minimum(l0b + Lb, X_END))
        wall1, _ = variable_pipe_wall(w1, Lb, Db, BP.WALL, method="sweep")
        total = l0b + w1.length + len2
        # 2番管の内径もメンズールに沿わせる(X_END を超えた所は ⌀12)。芯線は第 4 の出口(L = total)から Q へ向かう
        # 直線(補正フレネ)とベジエ(フレネ。補正フレネは落ちる)を別に掃引してつなぐ
        tube2, s_at, D2 = None, 0.0, []
        for e in edges2:
            ss = np.linspace(0, e.length, 101)
            dd = diameter(np.minimum(total - (s_at + ss), X_END))
            kw = {} if e.geom_type.name == "LINE" else {"binormal": "frenet"}
            w, _ = variable_pipe_wall(Wire([e]), ss, dd, BP.WALL, method="sweep", **kw)
            tube2 = w if tube2 is None else tube2 + w
            s_at += e.length
            D2 += [float(dd[0]), float(dd[-1])]
        print(f"branch2: cut {cut:g}, straight {d['s0']:.2f}, length {len2:.3f}, min R {d['r_min']:.2f}, "
              f"gap est {d['gap_est']:.3f}")
        print(f"branch1 (new): turn at bell L {r['sigma_turn']:.1f}, C a {r['a']:.1f} b {r['b']:.1f}, join line at tau "
              f"{r['tau1']:.1f} (Q at {tau_q:.1f}), length {w1.length:.3f} (old {old.length:.3f}), C min R {r['r_min']:.1f}, "
              f"C gap to bell {r['gap_c']:.2f}")
        print(f"rim -> valve 4 exit: {total:.3f} (D 12 at L {X_END:g}; straight D 12 {total - X_END:.3f} on branch2 side); "
              f"branch1 D end {float(Db[-1]):.3f}, branch2 D {D2[-1]:.3f} (at Q) -> {D2[0]:.3f} (at exit)")
        print(f"branch1 wall valid {wall1.is_valid}, branch2 tube valid {tube2.is_valid}")
        wall1w = BP.apply(wall1, M)
        # 1番管とベルの隙間: bell03_surface.clearance と同じ測り方(平面の輪郭、継ぎ目の近く 60 mm は除く)
        cl = BS.centerline()
        L, Dt = BS.read_ld(BS.LD_CSV)
        from bope_claude_cad.vss import fit_profile

        prof = fit_profile(L, Dt, cl.length)
        bprof = fit_profile(Lb, Db, w1.length)
        gap, where = BS.clearance(cl, prof, w1, bprof, wall=BP.WALL)
        print(f"clearance new branch1 - bell (outer surfaces, joint 60 mm excluded): {gap:.3f} mm at "
              f"({where[0]:.1f}, {where[1]:.1f}) (design coords)")
        print(f"branch1 straight before Q: {tau_q - r['tau1']:.2f} mm")
        B2.report_clearance(tube2, others)
        return wall1w, [tube2, BP.apply(w1, M)], ["branch2_wall", "branch1_new_centerline"], ["#20c0a0", "#ff2020"]

    AW.main(hook=hook)


if __name__ == "__main__":
    main()
