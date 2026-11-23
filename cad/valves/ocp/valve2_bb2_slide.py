"""第 2 植込の B 階に、Bb 第 2 抜差を配置する(共通モジュール bb_slide.py を使う)。
頭管: ピッチ 20 の f2bow(R10 の半円、直管 5 mm)。抜き量 d の目安 5 mm、100 セント(半音)下げる。
中管の長さ L は 0.5 mm 単位、ちょうど 100 セントになる d は端数。
"""

import sys
from pathlib import Path

from build123d import Rot

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bb_slide as S  # noqa: E402
import bows  # noqa: E402

CENTS = 100.0
D_NOMINAL = 5.0
VALVE = "valve2"
FERRULE_L = 10.0  # 桂 L10(飾り 1 本)。頭管側 4・中管側 6
BOW_LEN = sum(s[1] if s[0] == "L" else s[1] * abs(s[2]) * 3.141592653589793 / 180.0 for s in bows.BOWS["f2bow"]["segs"])  # f2bow の中心線(5 + π·10 + 5)


def design():
    return S.solve(CENTS, D_NOMINAL, BOW_LEN)


def bow_slide():
    """スライド座標の頭管(継ぎ目 y=0、本体 -Y、直管の軸 x=±10): f2bow(キャップ +Y)を Z まわり 180° 回す。"""
    return Rot(0, 0, 180) * bows.bow("f2bow")


def build(L=None, d=None):
    if L is None:
        _, _, L, d_exact = design()
        d = d_exact if d is None else d
    from valve_row import VALVES

    parts, info = S.slide_parts(VALVES[VALVE], bow_slide(), L, d, ferrule_l=FERRULE_L)
    return parts, info, L, d


def main():
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show
    from valve_row import build_row

    dl, l_exact, L, d = design()
    print(f"全長 {S.BB_LENGTH} mm の {CENTS:g} セント: ΔL = {dl:.3f} mm")
    print(f"枝管 1 本の中心線 {S.K_KNUCKLE:.3f}、頭管 {BOW_LEN:.3f}、離れ G={S.G_GAP:g}。d={D_NOMINAL:g} で ΔL を満たす L = {l_exact:.3f} → 0.5 mm 単位で L = {L:.1f}")
    print(f"L = {L:.1f} で、ちょうど {CENTS:g} セントになる抜き量 d = {d:.3f} mm(d = {D_NOMINAL:g} のときは {S.cents_of(L, D_NOMINAL, BOW_LEN):.2f} セント)")
    print(f"  迂回で増える長さ = 2·{S.K_KNUCKLE:.3f} + 2·({S.G_GAP:g} + {d:.3f} + {L:.1f}) + {BOW_LEN:.3f} = {S.extra(L, d, BOW_LEN):.3f} (= ΔL)")
    parts, info, L, d = build(L, d)
    row = build_row()
    case, ks, names = row[VALVE]
    show(case, *ks, *parts.values(), names=[f"{VALVE}_case"] + names + [f"slide2_{k}" for k in parts], reset_camera=Camera.KEEP)
    if "--check" in sys.argv:  # 干渉・距離の確認は遅い(2 分以上)ので、指定したときだけ
        S.check(parts, info, row, VALVE, L, d)


if __name__ == "__main__":
    main()
