"""主管抜差(main-slide)の設計。まず、モデル済みの部品(ベル・1番管・2番管・bb34・主管補助管 aux1/aux2・Bb 抜差・Bb 戻り)を全部出し、
主管抜差の中管を 1 本置く: 長さ INNER1_LEN(最初は Bb 第 2 の中管と同じ 33)、補助管 2 の右側の口(終端、向き +X)の先へ GAP mm 離して同軸に。
中管の先に主管頭(ピッチ BOW_PITCH の U 字管、主管頭平面の上、もう一方の直線は -Y 側)をつなぎ、
もう一方の直線にもう 1 つの中管(長さ INNER2_LEN)をはめる。

    uv run python cad/model202611/body_assy/main_slide/ocp/main_slide.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(next(p for p in HERE.parents if p.name == "model202611")))
import model_paths  # noqa: E402

ROOT = model_paths.add()

GAP = 1.0  # 補助管 2 の口から中管の桂の側の端まで
BOW_PITCH = 40.0  # 主管頭(U 字管)のピッチ。35 → 50 → 40(2026-11-24)
INNER1_LEN = 28.0  # 補助管 2 の口の先の中管の長さ。33 → 23(2026-11-24、全長を減らす)→ 28(2026-11-25、+5)
INNER2_LEN = 43.0  # 主管頭のもう一方の直線にはめる中管の長さ。48 → 38(2026-11-24、同)→ 43(2026-11-25、+5)


def hook(M, branch, others):
    import bb_return as BR
    import branch2_l as B2
    import slide_u as SU
    from build123d import Pos, Rot

    branch, p0, n0, c0 = BR.hook(M, branch, others)
    others = others + list(zip(n0, p0))
    d = dict(zip(n0, p0))
    if "main_aux2_wall" not in d:  # 主管補助管 2 はやり直し中(2026-11-24)。中管は置かない
        print("main-slide inner tube: skipped (no main_aux2)")
        return branch, p0, n0, c0
    ref = d["main_aux2_wall"]
    # 補助管 2 の口 = 補助管 2 の芯線の終点(向き +X)
    q = d["main_aux2_centerline"].position_at(1.0)
    P = np.array([q.X, q.Y, q.Z])
    length = float(sys.argv[sys.argv.index("--len1") + 1]) if "--len1" in sys.argv else INNER1_LEN
    # inner_tube_part は軸 Y(先端 y = 0、桂側へ -Y)。Z まわり +90° で軸 +X(先端 x = 0、桂側へ +X)
    part = Pos(*(P + np.array([GAP, 0.0, 0.0]))) * (Rot(0, 0, 90) * SU.inner_tube_part(length))
    bb = part.bounding_box(optimal=False)
    print(f"main-slide inner tube (length {length:g}): aux2 opening {P.round(3).tolist()}, x {bb.min.X:.3f}..{bb.max.X:.3f}, y {bb.min.Y:.3f}..{bb.max.Y:.3f}, z {bb.min.Z:.3f}..{bb.max.Z:.3f}; "
          + (f"distance to aux2 {part.distance_to(ref):.3f}" if B2.checks_enabled() else ""))
    B2.report_clearance(part, others)
    p0, n0, c0 = p0 + [part], n0 + ["main_slide_inner_tube"], c0 + ["#e0a020"]

    # 主管頭(2026-11-24): ピッチ BOW_PITCH の U 字管を中管の先(+X 側の端、軸 +X)につなぐ。U の面は主管頭平面
    # (z = MB_A·y + MB_B、X 方向を含む)。もう一方の直線は -Y 側。
    import aux2_u as A2
    import bell_place as BP
    import branch2_u as U

    pitch = float(sys.argv[sys.argv.index("--bow-pitch") + 1]) if "--bow-pitch" in sys.argv else BOW_PITCH
    P0 = np.array([bb.max.X, P[1], P[2]])  # 中管の先の端面の中心
    a = np.array([1.0, 0.0, 0.0])
    n = -np.array([0.0, 1.0, A2.MB_A]) / np.hypot(1.0, A2.MB_A)  # 主管頭平面の中で軸に垂直、-Y 側
    R = np.column_stack([n, a, np.cross(n, a)])
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = P0 - R @ np.array([-pitch / 2, 0.0, 0.0])
    w, info = U.u_wire_local(pitch)
    ww = BP.apply(w, T)
    q1, t1 = ww.position_at(1.0), ww.tangent_at(1.0)
    on_plane = lambda q: q.Z - (A2.MB_A * q.Y + A2.MB_B)  # noqa: E731
    print(f"main bow (U pitch {pitch:g}): start {P0.round(3).tolist()} (vs main-bow plane {on_plane(ww.position_at(0.0)):+.4f}), to the other leg {n.round(4).tolist()}; "
          f"curve {info['curve_len']:.3f} + legs 2 x 5 = {w.length:.3f}, min bend R {info['rmin']:.2f}, height {info['h']:.2f}")
    print(f"main bow other leg end ({q1.X:.3f}, {q1.Y:.3f}, {q1.Z:.3f}) (vs main-bow plane {on_plane(q1):+.4f}), direction ({t1.X:.3f}, {t1.Y:.3f}, {t1.Z:.3f})")
    bow = BP.apply(U.const_d_tube(w, SU.INNER_TUBE_ID, BP.WALL), T)
    print(f"main bow tube D {SU.INNER_TUBE_ID:g} wall {BP.WALL:g}: valid {bow.is_valid}, volume {sum(x.volume for x in bow.solids()):.2f}")
    print("clearance (main bow):")
    B2.report_clearance(bow, others)
    p0, n0, c0 = p0 + [bow, ww], n0 + ["main_bow_wall", "main_bow_centerline"], c0 + ["#e0a020", "#ff2020"]

    # もう 1 つの中管(2026-11-24): 主管頭のもう一方の直線の端に、同軸で -X へ長さ INNER2_LEN。桂の側を主管頭へ、先端は -X 側
    len2 = float(sys.argv[sys.argv.index("--len2") + 1]) if "--len2" in sys.argv else INNER2_LEN
    Q1 = np.array([q1.X, q1.Y, q1.Z])
    tip = Q1 - len2 * a
    part2 = Pos(*tip) * (Rot(0, 0, 90) * SU.inner_tube_part(len2))
    b2 = part2.bounding_box(optimal=False)
    print(f"main-slide inner tube 2 (length {len2:g}): tip {tip.round(3).tolist()}, x {b2.min.X:.3f}..{b2.max.X:.3f}, y {b2.min.Y:.3f}..{b2.max.Y:.3f}, z {b2.min.Z:.3f}..{b2.max.Z:.3f}")
    print("clearance (inner tube 2):")
    B2.report_clearance(part2, others)
    return branch, p0 + [part2], n0 + ["main_slide_inner_tube2"], c0 + ["#e0a020"]


def main() -> None:
    import assy_with_valves as AW

    AW.main(hook=hook)
    __import__("shape_cache").phase("show done")


if __name__ == "__main__":
    main()
