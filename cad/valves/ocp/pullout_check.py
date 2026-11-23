"""抜差を抜いたとき、頭管(とその先に動く部品)が、ベル・1番管に干渉しないかを調べる。
  python3 cad/valves/ocp/warm.py run cad/valves/ocp/pullout_check.py [スライド名 既定 Bb3] [--tip 10(負なら外へ出る。-10 で完全に抜けて 10 mm 出る)] [--no-check] [--step 5] [--no-show]
抜く量は、中管の先端が、外管の開いた端(つばの端)から --tip mm の所まで(外管の中に --tip mm だけ残る)。
動かす部品: 中管・桂・頭管(外管は動かさない)。-Y 方向へ平行移動する。
"""

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _points(shape, tol):
    """形の表面を三角形分割した頂点(距離の概算用)。"""
    import numpy as np

    v, _ = shape.tessellate(tol, 0.3)
    return np.array([[q.X, q.Y, q.Z] for q in v])


def main():
    import numpy as np
    from build123d import Pos
    import all_slides as A
    import bb_slide as S
    import bell_place as BP

    name = next((a for a in sys.argv[1:] if a in ("Bb1", "Bb2", "Bb3", "F1", "F2", "F3")), "Bb3")
    arg = lambda k, d: float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d  # noqa: E731
    tip, step = arg("--tip", 10.0), arg("--step", 5.0)
    slides = A.collect()
    p = slides[name]
    outer_end = p["outer_tube_L"].bounding_box().min.Y  # 外管の開いた端(つば側)
    inner_tip = p["inner_tube_L"].bounding_box().max.Y  # 中管の先端
    pull = (inner_tip - outer_end) - tip
    print(f"{name}: 外管の開いた端 y={outer_end:.3f}、中管の先端 y={inner_tip:.3f}(外管の中に {inner_tip - outer_end:.2f} mm)→ あと {pull:.2f} mm 抜くと、先端が外管の開いた端から {abs(tip):g} mm {"出る" if tip < 0 else "内側"}")
    bell, branch, M, ctr = BP.placed_manual()
    M2, pv, tw = BP.tilt_about_top_tangent(M, BP.TILT_DEG)
    from shape_cache import cached

    info = cached("bell03_walls", BP.WALL, BP.ROOT / "cad" / "bell03" / "ocp" / "bell03_surface.py", BP.build_bell)
    bell, branch = BP.apply(info["bell"], M2), BP.apply(info["branch"], M2)
    moving = [k for k in p if not k.startswith("outer_tube")]
    n = int(np.ceil(pull / step)) if "--no-check" not in sys.argv else -1
    res = []
    from scipy.spatial import cKDTree

    exact = "--exact" in sys.argv
    t0 = time.time()
    tol = 0.25  # 表面の分割の許容(概算の誤差は数 0.1 mm)。ベル・1番管は 1 回だけ分割して KD 木にする
    tree = cKDTree(np.vstack([_points(bell, tol), _points(branch, tol)]))
    mov_pts = np.vstack([_points(p[k], 0.1) for k in moving])
    print(f"表面の点: 動かす部品 {len(mov_pts)} 点、ベル側の KD 木を作った({time.time() - t0:.1f} 秒)")
    for i in range(n + 1):
        d = min(pull, i * step)
        t0 = time.time()
        if exact:
            sh = [Pos(0, -d, 0) * p[k] for k in moving]
            dmin = min(min(s.distance_to(b) for b in (bell, branch)) for s in sh)
        else:
            dmin = float(tree.query(mov_pts - np.array([0.0, d, 0.0]))[0].min())
        res.append((d, dmin))
        print(f"追加で {d:5.1f} mm 抜く: 頭管・中管・桂とベル/1番管の最小距離 {dmin:.3f} mm({time.time() - t0:.0f} 秒)", flush=True)
    if "--no-show" not in sys.argv:
        from ocp_vscode import Camera

        from bope_claude_cad.viewer import show
        from valve_row import build_row_cached

        slides[name] = {k: (Pos(0, -pull, 0) * v if k in moving else v) for k, v in p.items()}
        row = build_row_cached()
        parts, names = [], []
        for v, (case, ks, nms) in row.items():
            parts += [case] + ks
            names += [f"{v}_case"] + nms
        parts += A.valve4_knuckles()
        names += A.V4_NAMES
        for tag, pp in slides.items():
            parts += list(pp.values())
            names += [f"{tag}_{k}" for k in pp]
        parts += [bell, branch]
        names += ["bell03_bell_wall", "bell03_branch1_wall"]
        show(*parts, names=names, reset_camera=Camera.KEEP)
    return slides, res, pull


if __name__ == "__main__":
    main()
