"""第 3 植込の F 階(z=17)に F 第 3 抜差。頭管 f3bow(y 軸反転)、F 第 2 と合わせて Open F に対して 400 セント。外管 53・中管 54(Bb 第 3 と同じ)、ストッパなし。
  python3 cad/valves/ocp/warm.py run cad/valves/ocp/valve3_f3_slide.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import f_slide as F  # noqa: E402

CENTS_TOTAL = 400.0
CENTS_F2 = 100.0
VALVE = "valve3"
BOW = "f3bow"
MIRROR = True
PIPE_GAP = 1.4  # d=0 まで差し込んだとき、頭管と「上側の横向きの枝管を延長した仮のパイプ」の最小距離(他の近接と同じ 1.4 以上)


def build():
    need = F.required_extra(CENTS_TOTAL) - F.required_extra(CENTS_F2)
    return F.build_free(VALVE, BOW, MIRROR, need, pipe_gap=PIPE_GAP)


if __name__ == "__main__":
    import all_slides

    all_slides.main("F3", build)
