"""吹込管の試し線(2026-11-24)。今の吹込管(mouthpipe.py)に、細い端(入口 M)から左へ、X 軸となす角 ANGLE_DEG の直線を x = X_END まで引いて重ねる。
直線は吹込管の芯線の平面の上(XY で角度を決め、z は平面から)。

    uv run python cad/mouthpipe/ocp/mouthpipe_try.py [--angle -20] [--x-end 0]
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import mouthpipe as MP  # noqa: E402

ANGLE_DEG = -20.0  # XY で、X 軸となす角(左へ向かう直線。y = M_y + tan(角) · (x - M_x))
X_END = 0.0
OFFSET_OUT = 6.0  # ベル内側の円の投影線を外側へずらす量(2026-11-24)


def arg(k, d):
    return float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d


def hook(M, branch, others):
    from build123d import Edge, Vector

    # 吹込管の外形(管)は作らない。平面・両端・今の芯線だけを、mouthpipe.py のキャッシュ(ψ・設計)から
    import main_slide as MSL
    import shape_cache as SC
    from build123d import Wire

    branch, p0, n0, c0 = MSL.hook(M, branch, others)
    d_ = dict(zip(n0, p0))
    b2 = d_["main_slide_inner_tube2"].bounding_box(optimal=False)
    T = np.array([b2.min.X - MP.GAP, 0.5 * (b2.min.Y + b2.max.Y), 0.5 * (b2.min.Z + b2.max.Z)])
    bd = MP.bell_data(M)
    psi = SC.memo_value("mouthpipe_psi", [round(float(v), 6) for v in (*T, *M.ravel())] + [MP.CLEAR, MP.LEFT_X, MP.LEN_XY, MP.INNER_DEG],
                        MP.__file__, lambda: MP.solve_psi(bd, T)[0])
    d = SC.memo_value("mouthpipe_design", [round(float(v), 6) for v in (*T, *M.ravel(), psi)] + [MP.LEFT_X, MP.LEN_XY, MP.INNER_DEG],
                      MP.__file__, lambda: MP.design(bd, T, psi))
    T0 = d["A"] + d["x"][0] * np.array([1.0, 0.0, 0.0])
    w = Wire([Edge.make_line(Vector(*T0), Vector(*d["A"])), Edge.make_bezier(*[Vector(*c) for c in d["cp"]]),
              Edge.make_line(Vector(*d["B"]), Vector(*d["en"]["M"]))])
    print(f"mouthpipe (fixed ends): thick end {T0.round(3).tolist()}, entry M {d['en']['M'].round(3).tolist()}, psi {psi:.3f} deg; old centerline shown for reference (no tube)")
    p0, n0, c0 = p0 + [w], n0 + ["mouthpipe_centerline_old"], c0 + ["#ff2020"]
    P = np.array([tuple(w.position_at(t)) for t in np.linspace(0, 1, 400)])
    nrm = np.cross(P[200] - P[0], P[-1] - P[0])
    nrm /= np.linalg.norm(nrm)
    Mp = P[-1]  # 入口(細い端)
    ang, x1 = arg("--angle", ANGLE_DEG), arg("--x-end", X_END)
    y1 = Mp[1] + math.tan(math.radians(ang)) * (x1 - Mp[0])
    z1 = Mp[2] - (nrm[0] * (x1 - Mp[0]) + nrm[1] * (y1 - Mp[1])) / nrm[2]  # 吹込管の芯線の平面の上
    E = np.array([x1, y1, z1])
    off = float(np.abs((P - P[0]) @ nrm).max())
    print(f"try line: from entry M {Mp.round(3).tolist()} to {E.round(3).tolist()} (XY angle to X {ang:g} deg, slope {math.tan(math.radians(ang)):.4f}), "
          f"length 3D {np.linalg.norm(E - Mp):.3f}, XY {np.linalg.norm(E[:2] - Mp[:2]):.3f}; mouthpipe plane flatness {off:.2e}")
    line = Edge.make_line(Vector(*Mp), Vector(*E))
    # ベルの曲げ内側の円(曲げに使う円板の縁、φ 2·RI、ベル設計の平面 z = 0)を、吹込管の芯線の平面へ(法線方向に)投影し、y > 0 の部分だけ
    from make_centerline import geometry

    g = geometry()
    ph = np.linspace(0, 2 * np.pi, 3601)
    Q = np.c_[g["c"][0] + g["ri"] * np.cos(ph), g["c"][1] + g["ri"] * np.sin(ph), np.zeros_like(ph)]
    Q = (M[:3, :3] @ Q.T).T + M[:3, 3]
    ctr = M[:3, :3] @ np.array([g["c"][0], g["c"][1], 0.0]) + M[:3, 3]
    Qp = Q - np.outer((Q - P[0]) @ nrm, nrm)
    i0 = int(np.argmin(Qp[:, 1]))
    Qp, Q = np.roll(Qp[:-1], -i0, axis=0), np.roll(Q[:-1], -i0, axis=0)  # y 最小から始めて、y > 0 が 1 続きになるように
    r = np.where(Qp[:, 1] > 0)[0]
    proj = [Edge.make_spline([Vector(*q) for q in Qp[r[::4]]])]
    print(f"bell inner circle (D {2 * g['ri']:g}, centre {ctr.round(3).tolist()}) projected (y > 0): {Qp[r[0]].round(2).tolist()} -> {Qp[r[-1]].round(2).tolist()}, "
          f"x {Qp[r, 0].min():.2f}..{Qp[r, 0].max():.2f}, y max {Qp[r, 1].max():.2f}, distance to the plane {np.abs((Q[r] - P[0]) @ nrm).min():.2f}..{np.abs((Q[r] - P[0]) @ nrm).max():.2f}")
    # 投影線を、吹込管平面の中で外側(投影した円の中心から離れる向き)へ OFFSET_OUT オフセット
    off_d = arg("--offset-out", OFFSET_OUT)
    Qa = Qp[r]
    tq = np.gradient(Qa, axis=0)
    tq /= np.linalg.norm(tq, axis=1)[:, None]
    nq = np.cross(nrm, tq)
    cp_ = ctr - ((ctr - P[0]) @ nrm) * nrm
    nq *= np.sign(((Qa - cp_) * nq).sum(axis=1))[:, None]  # 外向き
    Qo = Qa + off_d * nq
    keep = Qo[:, 1] > 0
    proj.append(Edge.make_spline([Vector(*q) for q in Qo[keep][::4]]))
    print(f"offset {off_d:g} outward (y > 0): x {Qo[keep, 0].min():.2f}..{Qo[keep, 0].max():.2f}, y max {Qo[keep, 1].max():.2f} at x {Qo[keep][np.argmax(Qo[keep, 1]), 0]:.2f}")
    return (branch, p0 + [line] + proj, n0 + ["mouthpipe_try_line", "bell_inner_circle_proj", "bell_inner_circle_proj_off"],
            c0 + ["#00c0ff", "#ff00ff", "#ff8000"])


def main() -> None:
    import assy_with_valves as AW

    AW.main(hook=hook)
    __import__("shape_cache").phase("show done")


if __name__ == "__main__":
    main()
