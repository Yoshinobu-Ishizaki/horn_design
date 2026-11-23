"""第 1 植込(x=35)の B 階に、Bb 第 1 抜差を配置する(共通モジュール bb_slide.py を使う)。
頭管: 第 1 抜差頭の長靴形 b1bow(ピッチ 20、直管は入口側 8・出口側 30)。方針に沿った、曲率連続のスプライン版(bow_spline)。
抜き量 d の目安 10 mm、抜いた状態で全長を 200 セント(全音)下げる。中管の長さ L は 0.5 mm 単位、ちょうど 200 セントになる d は端数。
頭管の向き: mirror=True(既定)は b1bow の x を反転して置く(本体の張り出しが +x 側)。--no-mirror で元の向き(張り出しが -x 側)。
"""

import sys
from pathlib import Path

from build123d import Plane, Pos
from build123d import mirror as b3d_mirror

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bb_slide as S  # noqa: E402
import bow_spline as B  # noqa: E402

CENTS = 200.0
D_NOMINAL = 10.0
VALVE = "valve1"


def bow_data(mirror=True):
    """スライド座標の b1bow(継ぎ目 y=0、本体 -Y、直管の軸 x=±10)と、頭管の中心線の長さ。"""
    solid, cfg, v, ref, crv, wire = B.bow_spline("b1bow", B.W_DEFAULT)
    a = B.analyze(cfg, v, ref, B.W_DEFAULT)
    bow_len = cfg.l_in + cfg.l_out + a["L"]
    sol = Pos(-PITCH_HALF, 0, 0) * solid  # 直管の軸 x=0, 20 → -10, +10
    if mirror:
        sol = b3d_mirror(sol, Plane.YZ)  # x を反転(直管の軸は ±10 のまま)
    return sol, bow_len, (cfg, a)


PITCH_HALF = S.PITCH / 2


def main(mirror=True):
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show
    from valve_row import VALVES, build_row
    import valve2_bb2_slide as V2

    bow, bow_len, (cfg, a) = bow_data(mirror)
    dl, l_exact, L, d = S.solve(CENTS, D_NOMINAL, bow_len)
    print(f"全長 {S.BB_LENGTH} mm の {CENTS:g} セント: ΔL = {dl:.3f} mm")
    print(f"頭管 b1bow(スプライン)の中心線 = 直管 {cfg.l_in:g} + {a['L']:.3f} + 直管 {cfg.l_out:g} = {bow_len:.3f}(今の形からの距離 最大 {a['dmax']:.2f}、曲率 最小 R{1 / abs(a['kmin']):.1f})")
    print(f"枝管 1 本の中心線 {S.K_KNUCKLE:.3f}、離れ G={S.G_GAP:g}。d={D_NOMINAL:g} で ΔL を満たす L = {l_exact:.3f} → 0.5 mm 単位で L = {L:.1f}")
    print(f"L = {L:.1f} で、ちょうど {CENTS:g} セントになる抜き量 d = {d:.3f} mm(d = {D_NOMINAL:g} のときは {S.cents_of(L, D_NOMINAL, bow_len):.2f} セント)")
    print(f"  迂回で増える長さ = 2·{S.K_KNUCKLE:.3f} + 2·({S.G_GAP:g} + {d:.3f} + {L:.1f}) + {bow_len:.3f} = {S.extra(L, d, bow_len):.3f} (= ΔL)")
    parts, info = S.slide_parts(VALVES[VALVE], bow, L, d)
    parts2, info2, L2, d2 = V2.build()
    row = build_row()
    case, ks, names = row[VALVE]
    case2, ks2, names2 = row["valve2"]
    show(case, *ks, case2, *ks2, *parts.values(), *parts2.values(),
         names=[f"{VALVE}_case"] + names + ["valve2_case"] + names2 + [f"slide1_{k}" for k in parts] + [f"slide2_{k}" for k in parts2],
         reset_camera=Camera.KEEP)
    S.check(parts, info, row, VALVE, L, d, others=parts2)
    bb = parts["bow"].bounding_box()
    print(f"頭管 x=[{bb.min.X:.2f},{bb.max.X:.2f}] y=[{bb.min.Y:.2f},{bb.max.Y:.2f}]")


if __name__ == "__main__":
    main(mirror="--no-mirror" not in sys.argv)
