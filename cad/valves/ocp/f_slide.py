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
OUTER_LEN = 32.0  # 外管の長さ(Bb 第 2 抜差と同じ。ユーザー指示)


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


# ---- F 第 1・第 3 抜差(ストッパなし。外管・中管は Bb 第 1・第 3 と同じ 53・54)--------------------------
L_TUBE = 65.0  # 中管(Bb 第 1・第 3 と同じ)。外管は L-1 = 64
FREE_FERRULE_L = 12.0  # Bb 第 1・第 3 と同じ桂 L12(頭管側 6・中管側 6)
FER_ON_BOW = 6.0
FER_ON_TUBE = FREE_FERRULE_L - FER_ON_BOW  # d=0 で桂の中管側の端がつばに突き当たり、外管 = L-1 = 53 になる
FER_GAP = 1.0  # 桂の頭管側の端と曲がり始めの離れの下限
D_TARGET = 10.0


def bow_total(name):
    """切り詰める前の頭管の中心線の長さ(スプライン版。胃袋形は表面最近接距離 3.4)。"""
    import bow_spline as B

    cfg, v, ref, crv, wire = B.bow_curve(name, B.W_DEFAULT, S.GAPS.get(name))
    a = B.analyze(cfg, v, ref, B.W_DEFAULT)
    return cfg.l_in + cfg.l_out + a["L"], cfg


def design_free(name, need, step=0.5, drop=0.0):
    """中管 L_TUBE(外管 L_TUBE-1)で、抜き量 D_TARGET に近く、ちょうど ΔL = need になるよう、頭管の直管を切り詰める量 j を決める。
    j は 0.5 mm 単位。戻り値: (j, 切り詰め後の頭管の長さ, 抜き量 d(ちょうど)、j の厳密値)。"""
    tot, cfg = bow_total(name)
    kept = need - 2 * S.K_KNUCKLE - 2 * (S.G_GAP + D_TARGET + L_TUBE)
    j_exact = (tot - kept) / 2
    j = round(j_exact / step) * step
    j = min(j, min(cfg.l_in, cfg.l_out) - (FER_ON_BOW + FER_GAP))  # 桂が曲がり部に掛からない(短い方の直管で決まる)
    j -= drop  # 頭を下げる分、2 本の直管を長くする(音程は変えず、抜き量 d がその分減る)
    bow_len = tot - 2 * j
    d = (need - 2 * S.K_KNUCKLE - bow_len) / 2 - S.G_GAP - L_TUBE
    return j, bow_len, d, j_exact, cfg


def parts_free(x_c, bow_local, j, d):
    y_c = S.Y_STUB - S.G_GAP - L_TUBE + FER_ON_TUBE
    outer_len = (S.Y_STUB + S.S_IN) - y_c
    y_j = y_c - FER_ON_TUBE - d
    parts = {}
    for nm, dx in (("L", -S.PITCH / 2), ("R", +S.PITCH / 2)):
        x = x_c + dx
        parts[f"outer_tube_{nm}"] = Pos(x, y_c, Z_F) * Rot(-90, 0, 0) * outer_tube(outer_len)
        parts[f"inner_tube_{nm}"] = Pos(x, y_j, Z_F) * Rot(-90, 0, 0) * inner_tube(L_TUBE)
        parts[f"ferrule_{nm}"] = Pos(x, y_j - FER_ON_BOW, Z_F) * Rot(-90, 0, 0) * ferrule(FREE_FERRULE_L)
    parts["bow"] = Pos(x_c, y_j + j, Z_F) * bow_local
    return parts, dict(y_c=y_c, y_j=y_j, outer_len=outer_len)


PIPE_R = 6.4  # 枝管の外半径
PIPE_Y = 10.0  # 上側で横を向く枝管の軸の y(植込み中心から)


def extended_pipes(x_c, length=200.0):
    """植込みの上側(F 階)で横を向く 2 本の枝管(L2_45・L2_135)を、そのまま外へ延長した仮のパイプ。"""
    from build123d import Align, Cylinder

    out = []
    for sgn in (-1, +1):
        c = Cylinder(PIPE_R, length, align=(Align.CENTER, Align.CENTER, Align.MIN))  # 軸 Z、z=0 から
        x0 = x_c + sgn * 17.5  # 枝管の出口の端面
        c = Pos(x0, PIPE_Y, Z_F) * Rot(0, 90 * sgn, 0) * c  # Z → ±X(外向き)
        out.append(c)
    return out


def build_free(valve, bow_name, mirror, need, pipe_gap=None):
    """pipe_gap: d=0 まで差し込んだとき、頭管と「延長した上側の枝管」の最小距離をこの値以上にする(頭を 0.5 mm 単位で下げる)。"""
    from valve_row import VALVES

    x_c = VALVES[valve]
    drop = 0.0
    j, bow_len, d, j_exact, cfg = design_free(bow_name, need, step=0.1)
    bow, _, _ = S.trimmed_bow(bow_name, mirror, j=j)
    dist0 = None
    if pipe_gap is not None:
        pipes = extended_pipes(x_c)
        y_j0 = S.Y_STUB - S.G_GAP - L_TUBE  # d=0 の継ぎ目
        while True:
            b = Pos(x_c, y_j0 + j - drop, Z_F) * bow
            dist = min(b.distance_to(p) for p in pipes)
            if dist0 is None:
                dist0 = dist
            if dist >= pipe_gap or drop > 40:
                break
            drop = round(drop + 0.1, 3)
        if drop:
            j, bow_len, d, j_exact, cfg = design_free(bow_name, need, step=0.1, drop=drop)
            bow, _, _ = S.trimmed_bow(bow_name, mirror, j=j)
    parts, info = parts_free(x_c, bow, j, d)
    return parts, info, dict(j=j, j_exact=j_exact, bow_len=bow_len, d=d, need=need, l_in=cfg.l_in, l_out=cfg.l_out, L=L_TUBE, drop=drop, dist0=dist0, pipe_gap=pipe_gap)
