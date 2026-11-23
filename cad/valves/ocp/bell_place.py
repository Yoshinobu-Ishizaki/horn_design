"""bell03(ベル + 1番管)を配置する。

【今の配置(ユーザー指示 2026-11-23)】ベルと 1番管は一緒に、組立の基本姿勢(リム中心まわりに Z 軸で +15°)で置く。
曲げ内側の円(ベルの曲げに使う円板、直径 275)の中心が (X, B, C) に来るようにする。X = 5、B = -60、C = 50(暫定。あとで微調整)。
ベルと第 4 植込みは、まだつながない。  python3 cad/valves/ocp/warm.py run cad/valves/ocp/bell_place.py [--X 5] [--B -60] [--C 50]

【つなぐ配置(参考。`--connect`)】

1番管の末端(組立姿勢で +X を向く直線の端)の端面を、第 4 の 1 階左下の枝管の出口の端面(valve4_knuckle.twisted_knuckle)に突き合わせる。
  ・出口の軸(外向き)u = (0, -0.8707, +0.4919)(YZ で 29.46° 上向き)。1番管の末端の接線(ベルから離れる向き)を -u に合わせる。
  ・ベルの面(平面)は、-u と X 軸を含む面にする(最小の傾き 29.46°)。ベル本体は、出口から見て +x 側(他の植込みと反対側)に置く。
    反対側(-x 側)は `--side minus`。
壁の板厚 0.4。作ったソリッドは shape_cache に覚える。
  python3 cad/valves/ocp/warm.py run cad/valves/ocp/bell_place.py [--side minus]
"""

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "cad" / "bell03" / "tools"))
sys.path.insert(0, str(ROOT / "cad" / "bell03" / "ocp"))

WALL = 0.4


def build_bell():
    """設計の座標(リム中心 (0,0)、直管部は +Y)の、ベルと 1番管の壁(ソリッド)と、1番管の末端の位置・接線。"""
    import bell03_surface as BS
    from bope_claude_cad.vss import variable_pipe_wall
    from make_centerline import build_branch_wire, geometry
    from make_mensur import X_END, diameter

    cl = BS.centerline()
    L, D = BS.read_ld(BS.LD_CSV)
    wall, _ = variable_pipe_wall(cl, L, D, WALL, method="sweep")
    bcl = build_branch_wire()
    g = geometry()
    l0b = cl.length
    Lb = np.linspace(l0b, g["l_branch_end"], 401)
    Db = diameter(np.minimum(Lb, X_END))
    bwall, _ = variable_pipe_wall(bcl, Lb - l0b, Db, WALL, method="sweep")
    e = bcl.position_at(1.0)
    t = bcl.tangent_at(1.0)
    return dict(bell=wall, branch=bwall, end=[e.X, e.Y, e.Z], tangent=[t.X, t.Y, t.Z], cl_len=cl.length, rim=[0.0, 0.0, 0.0])


def transform(info, side="plus"):
    from build123d import Location

    import valve4_knuckle as V

    u = np.array(V.exit_axis_world(*V.solve()[:2]), float)
    k = V.twisted_knuckle()
    face = next(f for f in k.faces() if f.geom_type.name == "PLANE" and abs(f.normal_at().X * u[0] + f.normal_at().Y * u[1] + f.normal_at().Z * u[2] - 1.0) < 1e-6)
    c = face.center()
    p_exit = np.array([c.X, c.Y, c.Z])
    e = np.array(info["end"])
    t = np.array(info["tangent"])
    t /= np.linalg.norm(t)
    # ベルの面は設計の座標で z=0(法線 Z)。本体側(面内で t に垂直、リム中心の側)
    to_rim = np.array(info["rim"]) - e
    s = to_rim - np.dot(to_rim, t) * t
    s[2] = 0.0
    s /= np.linalg.norm(s)
    n = np.cross(t, s)
    w = -u  # 目標の接線(ベルから離れる向き)
    sx = np.array([1.0, 0.0, 0.0] if side == "plus" else [-1.0, 0.0, 0.0])
    s2 = sx - np.dot(sx, w) * w
    s2 /= np.linalg.norm(s2)
    n2 = np.cross(w, s2)
    R = np.column_stack([w, s2, n2]) @ np.column_stack([t, s, n]).T
    shift = p_exit - R @ e
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = shift
    return M, p_exit, u


def apply(shape, M):
    from build123d import Location
    from OCP.gp import gp_Trsf

    tr = gp_Trsf()
    tr.SetValues(*[float(M[i, j]) for i in range(3) for j in range(4)])
    return shape.moved(Location(tr))


def placed_manual(B=-60.0, C=50.0, x=5.0):
    """組立姿勢(Z 軸まわり +15°)で、曲げ内側の円の中心を (x, B, C) に置く。"""
    from shape_cache import cached
    from make_centerline import ASSEMBLY_ROT_Z, geometry

    info = cached("bell03_walls", WALL, ROOT / "cad" / "bell03" / "ocp" / "bell03_surface.py", build_bell)
    a = math.radians(ASSEMBLY_ROT_Z)
    c = geometry()["c"]
    cx, cy = c[0] * math.cos(a) - c[1] * math.sin(a), c[0] * math.sin(a) + c[1] * math.cos(a)
    M = np.array([[math.cos(a), -math.sin(a), 0, x - cx], [math.sin(a), math.cos(a), 0, B - cy], [0, 0, 1, C], [0, 0, 0, 1]])
    return apply(info["bell"], M), apply(info["branch"], M), M, np.array([x, B, C])


def placed(side="plus"):
    from shape_cache import cached

    info = cached("bell03_walls", WALL, ROOT / "cad" / "bell03" / "ocp" / "bell03_surface.py", build_bell)
    M, p_exit, u = transform(info, side)
    return apply(info["bell"], M), apply(info["branch"], M), M, p_exit, u


def main():
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show
    import all_slides as A
    from valve_row import build_row_cached

    arg = lambda k, d: float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d  # noqa: E731
    if "--connect" in sys.argv:
        side = "minus" if "--side" in sys.argv and sys.argv[sys.argv.index("--side") + 1] == "minus" else "plus"
        bell, branch, M, p_exit, u = placed(side)
        print(f"出口の端面の中心 {np.round(p_exit, 3)}、外向きの軸 {np.round(u, 4)}、ベル本体は {'+x' if side == 'plus' else '-x'} 側")
    else:
        X, B, C = arg("--X", 5.0), arg("--B", -60.0), arg("--C", 50.0)
        bell, branch, M, ctr = placed_manual(B, C, X)
        print(f"曲げ内側の円の中心 = {np.round(ctr, 3)}(姿勢: Z 軸まわり +15°)")
    bb = bell.bounding_box()
    b2 = branch.bounding_box()
    print(f"ベル x[{bb.min.X:.1f},{bb.max.X:.1f}] y[{bb.min.Y:.1f},{bb.max.Y:.1f}] z[{bb.min.Z:.1f},{bb.max.Z:.1f}]  1番管 x[{b2.min.X:.1f},{b2.max.X:.1f}] y[{b2.min.Y:.1f},{b2.max.Y:.1f}] z[{b2.min.Z:.1f},{b2.max.Z:.1f}]")
    slides = A.collect()
    row = build_row_cached()
    parts, names = [], []
    for v, (case, ks, nms) in row.items():
        parts += [case] + ks
        names += [f"{v}_case"] + nms
    parts += A.valve4_knuckles()
    names += A.V4_NAMES
    for tag, p in slides.items():
        parts += list(p.values())
        names += [f"{tag}_{k}" for k in p]
    parts += [bell, branch]
    names += ["bell03_bell_wall", "bell03_branch1_wall"]
    show(*parts, names=names, reset_camera=Camera.KEEP)


if __name__ == "__main__":
    main()
