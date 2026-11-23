"""第 1 植込の F 階(z=17)に F 第 1 抜差。頭管 f1bow(y 軸反転)、Open F に対して 200 セント。外管 53・中管 54(Bb 第 1 と同じ)、ストッパなし。
継ぎ目の桂 L8(両側飾り、頭管側 2・中管側 6)。抜き量 10 mm に近づくよう、頭管の直管を 0.5 mm 単位で切り詰める。
  python3 cad/valves/ocp/warm.py run cad/valves/ocp/valve1_f1_slide.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import f_slide as F  # noqa: E402

CENTS = 200.0
VALVE = "valve1"
BOW = "f1bow"
MIRROR = True


def build():
    return F.build_free(VALVE, BOW, MIRROR, F.required_extra(CENTS))


if __name__ == "__main__":
    import all_slides

    all_slides.main("F1", build)
