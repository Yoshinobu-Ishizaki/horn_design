"""F管抜差(仮、2026-11-26): F管抜差の中管 1 を、主管頭平面の上に置く。座標は管体組立のワールド。

- 主管抜差の中管 2(main_slide_inner_tube2、軸は X 方向)の軸から、主管頭平面の中で -Y 側へ PITCH 離した平行な軸。
- +X の端面は x = X_MAX、長さ LEN1(+Y 側の中管)。寸法は主管抜差の中管と同じ(slide_u.inner_tube_part: 外径 12.8・内径 12.0)。
- 中管 2: 中管 1 の軸から、さらに -Y 側へ PITCH2 離した平行な軸。+X の端面を中管 1 とそろえ(x = X_MAX)、長さ LEN2。
- U 字管(F管抜差の頭、2026-11-27): 中管 1 の +X の端面から、中管 1・2 の軸間距離をピッチにした U(主管頭と同じ作り方)。主管頭平面の上。
- 全体(吹込管まで)を出したうえで足す(mouthpipe_try.hook のあと)。

    uv run python cad/model202611/body_assy/f_slide/ocp/f_slide_inner.py [--pitch 17] [--x-max 61.161549] [--len1 50] [--pitch2 50] [--len2 65] [--check]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(next(p for p in HERE.parents if p.name == "model202611")))
import model_paths  # noqa: E402

ROOT = model_paths.add()

PITCH = 17.0  # 主管抜差の中管 2 の軸から -Y 側へ(主管頭平面の中で、軸に垂直に測る)
X_MAX = 61.161549  # (+5、2026-11-27 さらに) 中管 1・2 の +X の端面の x。50 → 80(2026-11-26)→ 80 - 28.851902(2026-11-27、F 迂回路の全長をインピーダンス計算の F 延長 930.918033 に合わせる)
# → +5.013451(2026-11-27、F管抜差の U と右の経路の U を、ベルの曲げ内側の円の中心 x = 5 についてほぼ対称に。右の U も同じだけ動かすので F 迂回路の全長は変わらない)
LEN1 = 50.0  # 中管 1(+Y 側)の長さ
PITCH2 = 50.0  # 中管 1 の軸から中管 2 の軸まで(-Y 側)。17(仮)→ 50(2026-11-26)
LEN2 = 65.0  # 中管 2 の長さ(+X の端面は x = X_MAX)


def arg(k, d):
    return float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d


def hook(M, branch, others):
    import aux2_u as A2
    import branch2_l as B2
    import mouthpipe_try as MT
    import slide_u as SU
    from build123d import Pos, Rot

    branch, p0, n0, c0 = MT.hook(M, branch, others)
    others = others + list(zip(n0, p0))
    d = dict(zip(n0, p0))
    # 主管抜差の中管 2 の軸 = 主管頭の芯線の終点を通る X 方向の直線
    q = d["main_bow_centerline"].position_at(1.0)
    A = np.array([q.X, q.Y, q.Z])
    pitch, x1, length = arg("--pitch", PITCH), arg("--x-max", X_MAX), arg("--len1", LEN1)
    x0 = x1 - length
    n = -np.array([0.0, 1.0, A2.MB_A]) / np.hypot(1.0, A2.MB_A)  # 主管頭平面の中で軸に垂直、-Y 側
    C = A + pitch * n  # 中管 1 の軸の上の点(x は A と同じ)
    # inner_tube_part は軸 Y(先端 y = 0、桂側へ -Y)。Z まわり +90° で軸 +X(先端 x = 0 から +X へ)
    part = Pos(x0, C[1], C[2]) * (Rot(0, 0, 90) * SU.inner_tube_part(length))
    bb = part.bounding_box(optimal=False)
    on_plane = C[2] - (A2.MB_A * C[1] + A2.MB_B)
    print(f"F-slide inner tube 1 (provisional): axis y {C[1]:.3f} z {C[2]:.3f} (vs main-bow plane {on_plane:+.4f}), "
          f"pitch {pitch:g} from main-slide inner tube 2 (axis y {A[1]:.3f} z {A[2]:.3f}), x {bb.min.X:.3f}..{bb.max.X:.3f}, length {length:g}")
    print("clearance (F-slide inner tube 1):")
    B2.report_clearance(part, others)
    others = others + [("f_slide_inner_tube1", part)]

    pitch2, len2 = arg("--pitch2", PITCH2), arg("--len2", LEN2)
    C2 = C + pitch2 * n
    part2 = Pos(x1 - len2, C2[1], C2[2]) * (Rot(0, 0, 90) * SU.inner_tube_part(len2))
    b2 = part2.bounding_box(optimal=False)
    print(f"F-slide inner tube 2 (provisional): axis y {C2[1]:.3f} z {C2[2]:.3f} (vs main-bow plane {C2[2] - (A2.MB_A * C2[1] + A2.MB_B):+.4f}), "
          f"pitch {pitch2:g} from inner tube 1, x {b2.min.X:.3f}..{b2.max.X:.3f}, length {len2:g}")
    print("clearance (F-slide inner tube 2):")
    B2.report_clearance(part2, others)
    # F管抜差の U 字管(2026-11-27): 主管頭と同じ作り方(main_slide.hook)。中管 1 の +X の端面の中心から、ピッチ = 中管 1・2 の軸間距離の U。
    # U の面は主管頭平面(2 本の中管の軸を含む)、もう一方の直線は -Y 側(中管 2 の +X の端面へ)
    import bell_place as BP
    import branch2_u as U

    others = others + [("f_slide_inner_tube2", part2)]
    pitch_u = float(np.linalg.norm(C2 - C))
    a = np.array([1.0, 0.0, 0.0])
    P0 = np.array([x1, C[1], C[2]])
    R = np.column_stack([n, a, np.cross(n, a)])
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = P0 - R @ np.array([-pitch_u / 2, 0.0, 0.0])
    w, info = U.u_wire_local(pitch_u)
    ww = BP.apply(w, T)
    q1, t1 = ww.position_at(1.0), ww.tangent_at(1.0)
    Q1 = np.array([q1.X, q1.Y, q1.Z])
    print(f"F-slide bow (U pitch {pitch_u:g}): start {P0.round(3).tolist()} (inner tube 1 +X end), other leg end {Q1.round(3).tolist()} "
          f"(vs inner tube 2 +X end {np.array([x1, C2[1], C2[2]]).round(3).tolist()}: {np.linalg.norm(Q1 - [x1, C2[1], C2[2]]):.1e}), direction ({t1.X:.3f}, {t1.Y:.3f}, {t1.Z:.3f}); "
          f"curve {info['curve_len']:.3f} + legs 2 x 5 = {w.length:.3f}, min bend R {info['rmin']:.2f}, height {info['h']:.2f}")
    bow = BP.apply(U.const_d_tube(w, SU.INNER_TUBE_ID, BP.WALL), T)
    print(f"F-slide bow tube D {SU.INNER_TUBE_ID:g} wall {BP.WALL:g}: valid {bow.is_valid}, volume {sum(x.volume for x in bow.solids()):.2f}")
    print("clearance (F-slide bow):")
    B2.report_clearance(bow, others)
    return (branch, p0 + [part, part2, bow, ww], n0 + ["f_slide_inner_tube1", "f_slide_inner_tube2", "f_slide_bow_wall", "f_slide_bow_centerline"],
            c0 + ["#40c040", "#40c040", "#40c040", "#ff2020"])


def main() -> None:
    import assy_with_valves as AW

    AW.main(hook=hook)
    __import__("shape_cache").phase("show done")


if __name__ == "__main__":
    main()
