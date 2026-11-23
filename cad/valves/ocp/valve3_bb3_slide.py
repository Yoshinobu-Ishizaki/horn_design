"""第 3 植込(x=-35)の B 階に、Bb 第 3 抜差を配置する(共通モジュール bb_slide.py の桂 6+6 方式)。
頭管: b3bow(スプライン版、y 軸まわりに反転して張り出しが -x 側)。直管を、桂(頭管側 6・中管側 6)の端面が曲がり始めから 1 mm の位置まで切り詰める(短い方の直管 18 で決まる)。
第 2 抜差と合わせて Open Bb から 400 セント下げる(第 3 の増加分 = ΔL(400) - ΔL(100))。中管 65・外管 64(第 1 抜差と同じ。ユーザー指示)。抜き量 d は端数。
  uv run python cad/valves/ocp/valve3_bb3_slide.py [--no-mirror]
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bb_slide as S  # noqa: E402

CENTS_TOTAL = 400.0
CENTS_SLIDE2 = 100.0
L_TUBE = 65.0  # 中管(外管 64)
VALVE = "valve3"


def build(mirror=True):
    from valve_row import VALVES

    bow, bow_len, j = S.trimmed_bow("b3bow", mirror)
    need = S.required_extra(CENTS_TOTAL) - S.required_extra(CENTS_SLIDE2)
    d = S.solve_eq(need, bow_len, L_TUBE)
    parts, info = S.parts6(VALVES[VALVE], bow, j, L_TUBE, d)
    return parts, info, bow_len, j, d, need


def main(mirror=True):
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show
    from valve_row import build_row_cached
    import valve1_bb1_slide as V1
    import valve2_bb2_slide as V2

    parts, info, bow_len, j, d, need = build(mirror)
    print(f"第 3 抜差: ΔL = ΔL({CENTS_TOTAL:g}) - ΔL({CENTS_SLIDE2:g}) = {need:.3f}。頭管 b3bow を継ぎ目 {j:g} mm だけ切り詰め、中心線 {bow_len:.3f}")
    print(f"中管 {L_TUBE:g}、外管 {info['outer_len']:g}、ちょうどの抜き量 d = {d:.3f} mm、継ぎ目 y={info['y_b']:.3f}、はめ合い長さ {L_TUBE - S.FER6 - d:.3f}")
    parts1 = V1.build(mirror)[0]
    parts2, info2, L2, d2 = V2.build()
    row = build_row_cached()
    case, ks, names = row[VALVE]
    c1, k1, n1 = row["valve1"]
    c2, k2, n2 = row["valve2"]
    show(case, *ks, c2, *k2, c1, *k1, *parts.values(), *parts2.values(), *parts1.values(),
         names=[f"{VALVE}_case"] + names + ["valve2_case"] + n2 + ["valve1_case"] + n1
         + [f"slide3_{k}" for k in parts] + [f"slide2_{k}" for k in parts2] + [f"slide1_{k}" for k in parts1],
         reset_camera=Camera.KEEP)
    if "--check" in sys.argv:  # 干渉・距離の確認は遅い(2 分以上)ので、指定したときだけ
        S.check(parts, info, row, VALVE, L_TUBE, d, others={**parts2, **{f"1{k}": v for k, v in parts1.items()}})
    bb = parts["bow"].bounding_box()
    print(f"頭管 x=[{bb.min.X:.2f},{bb.max.X:.2f}] y=[{bb.min.Y:.2f},{bb.max.Y:.2f}]")


if __name__ == "__main__":
    main(mirror="--no-mirror" not in sys.argv)
