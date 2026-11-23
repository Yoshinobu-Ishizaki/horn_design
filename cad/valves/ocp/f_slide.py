"""F 側の抜差(1 階、z=17)の共通モジュール。頭管と外管は Bb 側と共通(bb_slide.py)。

Bb 側との違い:
  ・全長: Open F = Bb 管の全長 2743.4 + F 管の延長管 Fx 930.9 = 3674.3 mm(impedance/bell03/README.md)。ΔL = 全長 × (2^(cents/1200) − 1)。
  ・頭と中管をつなぐ桂は L8(頭管側 4・中管側 4)で、飾りが両側(2 本)。
  ・外管のつばは、枝管の出口から外管の長さの所(Bb 第 2 と同じ外管)。差し込み切ったとき(d=0)に中管の先端が枝管の出口から G=1 mm になる位置で
    止まるよう、中管の途中にストッパの桂 L10 を被せる(桂の枝管側の端面が、外管のつばの面に突き当たる)。
経路の増加は Bb 側と同じ式: ΔL = 2K + 2(G + d + L) + 頭管の中心線(L: 中管の長さ。先端から継ぎ目まで)。
"""

import math
import sys
from pathlib import Path

from build123d import Pos, Rot

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bb_slide as S  # noqa: E402
from ferrule import ferrule  # noqa: E402
from inner_tube import inner_tube  # noqa: E402
from outer_tube import outer_tube  # noqa: E402

F_LENGTH = S.BB_LENGTH + 930.9
Z_F = 17.0  # 1 階
JOINT_FERRULE_L = 8.0  # 頭と中管をつなぐ桂(両側飾り)
STOPPER_L = 10.0  # 中管の途中のストッパの桂
OUTER_LEN = 32.0  # 外管の長さ(Bb 第 2 抜差と同じ)


def required_extra(cents):
    return S.required_extra(cents, F_LENGTH)


def solve(cents, d_nominal, bow_len, step=0.5):
    """(ΔL、d_nominal で ΔL を満たす L(丸める前)、丸めた L、ちょうど ΔL になる d)。"""
    dl = required_extra(cents)
    half = (dl - 2 * S.K_KNUCKLE - bow_len) / 2
    l_exact = half - S.G_GAP - d_nominal
    l_round = round(l_exact / step) * step
    return dl, l_exact, l_round, half - S.G_GAP - l_round


def slide_parts(x_c, bow_slide, L, d):
    """x_c: 植込みの x。bow_slide: スライド座標の頭管(継ぎ目 y=0、本体 -Y、直管の軸 x=±10)。"""
    y_tip = S.Y_STUB - S.G_GAP  # d=0 での中管の先端
    y_c = S.Y_STUB + S.S_IN - OUTER_LEN  # 外管のつばの面
    y_j = y_tip - L - d  # 継ぎ目
    half = JOINT_FERRULE_L / 2
    parts = {}
    for nm, dx in (("L", -S.PITCH / 2), ("R", +S.PITCH / 2)):
        x = x_c + dx
        parts[f"outer_tube_{nm}"] = Pos(x, y_c, Z_F) * Rot(-90, 0, 0) * outer_tube(OUTER_LEN)
        parts[f"inner_tube_{nm}"] = Pos(x, y_j, Z_F) * Rot(-90, 0, 0) * inner_tube(L)
        parts[f"ferrule_{nm}"] = Pos(x, y_j - half, Z_F) * Rot(-90, 0, 0) * ferrule(JOINT_FERRULE_L)
        # ストッパ: 枝管側の端面が、d だけ抜いた分だけ、つばの面から離れる(d=0 でつばに突き当たる)
        parts[f"stopper_{nm}"] = Pos(x, y_c - STOPPER_L - d, Z_F) * Rot(-90, 0, 0) * ferrule(STOPPER_L)
    parts["bow"] = Pos(x_c, y_j, Z_F) * bow_slide
    return parts, dict(y_c=y_c, y_j=y_j, y_tip=y_tip)
