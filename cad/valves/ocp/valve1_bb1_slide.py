"""第 1 植込(x=35)の B 階に、Bb 第 1 抜差を配置する(共通モジュール bb_slide.py の桂 6+6 方式)。
頭管: b1bow(スプライン版、y 軸まわりに反転して張り出しが +x 側)。直管を、桂(頭管側 6・中管側 6)の端面が曲がり始めから 1 mm の位置まで切り詰める。
中管 54・外管 53(第 3 抜差と同じ。ユーザー指示)。b1bow は全長を約 4 mm 短くした形(bows.py)。抜き量 d は端数。
  uv run python cad/valves/ocp/valve1_bb1_slide.py [--no-mirror]
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bb_slide as S  # noqa: E402

CENTS = 200.0
L_TUBE = 54.0  # 中管(外管は L-1 = 53)
VALVE = "valve1"


def build(mirror=True):
    from valve_row import VALVES

    bow, bow_len, j = S.trimmed_bow("b1bow", mirror)
    need = S.required_extra(CENTS)
    d = S.solve_eq(need, bow_len, L_TUBE)
    parts, info = S.parts6(VALVES[VALVE], bow, j, L_TUBE, d)
    return parts, info, bow_len, j, d, need


def main(mirror=True):
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show
    from valve_row import build_row
    import valve2_bb2_slide as V2

    parts, info, bow_len, j, d, need = build(mirror)
    print(f"第 1 抜差: {CENTS:g} セント ΔL = {need:.3f}。頭管 b1bow を継ぎ目 {j:g} mm だけ切り詰め、中心線 {bow_len:.3f}")
    print(f"中管 {L_TUBE:g}、外管 {info['outer_len']:g}、ちょうどの抜き量 d = {d:.3f} mm、継ぎ目 y={info['y_b']:.3f}")
    parts2, info2, L2, d2 = V2.build()
    row = build_row()
    case, ks, names = row[VALVE]
    case2, ks2, names2 = row["valve2"]
    show(case, *ks, case2, *ks2, *parts.values(), *parts2.values(),
         names=[f"{VALVE}_case"] + names + ["valve2_case"] + names2 + [f"slide1_{k}" for k in parts] + [f"slide2_{k}" for k in parts2],
         reset_camera=Camera.KEEP)
    S.check(parts, info, row, VALVE, L_TUBE, d, others=parts2)
    bb = parts["bow"].bounding_box()
    print(f"頭管 x=[{bb.min.X:.2f},{bb.max.X:.2f}] y=[{bb.min.Y:.2f},{bb.max.Y:.2f}]")


if __name__ == "__main__":
    main(mirror="--no-mirror" not in sys.argv)
