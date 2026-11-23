"""Bb 管の抜差(外管 2 本、頭管、中管 2 本、桂 2 個)を、植込みの B 階(z=34)の下の枝管に配置する共通のモジュール。
第 2 抜差(valve2_bb2_slide.py)と第 1 抜差(valve1_bb1_slide.py)が使う。

迂回の長さと中管の長さの決め方(経路は各管の中心線で数える):
  ・ポートは通常 x 方向につながる(開いた状態: 上の 135° と 45° の枝管)。ローターが 90° 回ると、上の枝管が下の枝管
    (225° と 315°、2 本目が -Y、x = 植込みの x ± 10、ピッチ 20)につながり、抜差側へ迂回する。
  ・増加分 ΔL = (回した状態の主経路)−(開いた状態の主経路) = 枝管 2 本分 + 抜差の輪
      枝管 1 本の中心線 K = 14.142(ローターの中心 → 角)+ 7.5(角 → 出口)= 21.642
      抜差の輪 = 2 ×(離れ G + 抜き量 d + 中管の長さ L)+ 頭管の中心線の長さ
    G: 桂が外管のつばに接触する状態(d=0)で、中管の端面と枝管の出口の端面の離れ(1 mm。空気の経路には入る)。
    ローターの中を通る経路は、どちらの状態でも枝管の始点(ローターの中心)を通るので打ち消し合う。
  ・音程 cents を下げるのに必要な増加分 ΔL = 全長 × (2^(cents/1200) − 1)。全長は、最新の設計(bell03)の Bb 管の全長 2743.4 mm。
  ・d = d_nominal で ΔL を満たす L を、0.5 mm 単位に丸める。そのうえで、ちょうど cents になる d(端数になってよい)を求める。
抜差の構造(仮定): 外管(つば付き)は、枝管の出口に外から被せる(差し込み深さ S_IN)。中管は、外管のつば側から入る。
  中管と頭管の継ぎ目に、桂(L12)を外から被せる: 頭管側に 4 mm、中管側に 8 mm。
  d = 0(桂の中管側の端が外管のつばの面に突き当たる状態)で、中管の端面は枝管の出口の端面から G 離れる。
  d だけ抜くと、桂の端は、つばの面から d だけ離れ、中管の端面は枝管の出口から G + d 離れる。
  外管のつばの面は、y = Y_STUB − G − L + 8。経路の長さ(枝管の出口の端面から頭管の直管の端面まで = G + d + L)は桂で変わらない。
頭管は「スライド座標」で渡す: 直管の端面(継ぎ目)が y=0、頭管の本体が -Y 側、2 本の直管の軸が x = ±10。
"""

import math
import sys
from pathlib import Path

from build123d import Pos, Rot

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "cad" / "tubes" / "ocp"))
sys.path.insert(0, str(ROOT / "cad" / "bows" / "ocp"))
from ferrule import ferrule  # noqa: E402
from inner_tube import inner_tube  # noqa: E402
from outer_tube import outer_tube  # noqa: E402

BB_LENGTH = 2743.4  # Bb 管の全長(bell03、impedance/bell03/README.md)
K_KNUCKLE = 10 * math.sqrt(2) + 7.5  # 枝管 1 本の中心線(ローターの中心 → 出口)
PITCH = 20.0
Z_B = 34.0  # B 階
Y_STUB = -17.5  # 枝管の出口の端面(下の枝管)
FERRULE_L = 12.0  # 桂の長さ
FERRULE_ON_BOW = 4.0  # 桂を頭管側に被せる長さ(頭管の直管は 5 mm 以上)
FERRULE_ON_TUBE = FERRULE_L - FERRULE_ON_BOW  # 中管側に被せる長さ(8)
S_IN = 4.0  # 外管が枝管の出口に被さる深さ(仮)。5 だと第 2 抜差でスリーブの端がケースに 0.045 mm³ 食い込む
G_GAP = 1.0  # d=0(桂が外管のつばに接触)での、中管の端面と枝管の出口の端面の離れ


def required_extra(cents, length=BB_LENGTH):
    return length * (2 ** (cents / 1200.0) - 1.0)


def solve(cents, d_nominal, bow_len, length=BB_LENGTH, step=0.5):
    """戻り値: (ΔL、d_nominal で ΔL を満たす L(丸める前)、丸めた L、ちょうど ΔL になる d)。"""
    dl = required_extra(cents, length)
    half = (dl - 2 * K_KNUCKLE - bow_len) / 2
    l_exact = half - G_GAP - d_nominal
    l_round = round(l_exact / step) * step
    return dl, l_exact, l_round, half - G_GAP - l_round


def extra(L, d, bow_len):
    return 2 * K_KNUCKLE + 2 * (G_GAP + d + L) + bow_len


def cents_of(L, d, bow_len, length=BB_LENGTH):
    return 1200.0 * math.log2(1.0 + extra(L, d, bow_len) / length)


def slide_parts(x_c, bow_slide, L, d, s_in=S_IN, bead_on="bow"):
    """抜差の部品(dict)。x_c: 植込みの x。bow_slide: スライド座標の頭管(継ぎ目 y=0、本体 -Y、直管の軸 x=±10)。"""
    y_c = Y_STUB - G_GAP - L + FERRULE_ON_TUBE  # 外管のつばの面
    outer_len = (Y_STUB + s_in) - y_c
    y_b = y_c - FERRULE_ON_TUBE - d  # 頭管の直管の端面(継ぎ目)
    parts = {}
    for nm, dx in (("L", -PITCH / 2), ("R", +PITCH / 2)):
        x = x_c + dx
        parts[f"outer_tube_{nm}"] = Pos(x, y_c, Z_B) * Rot(-90, 0, 0) * outer_tube(outer_len)  # Z → +Y(つばが y_c)
        parts[f"inner_tube_{nm}"] = Pos(x, y_b, Z_B) * Rot(-90, 0, 0) * inner_tube(L)  # y_b → y_b + L
        f = ferrule(FERRULE_L)
        if bead_on == "tube":  # 飾り線を中管側の端に: 局所 Z を反転
            f = Pos(0, 0, FERRULE_L) * Rot(180, 0, 0) * f
        parts[f"ferrule_{nm}"] = Pos(x, y_b - FERRULE_ON_BOW, Z_B) * Rot(-90, 0, 0) * f
    parts["bow"] = Pos(x_c, y_b, Z_B) * bow_slide
    return parts, dict(y_c=y_c, y_b=y_b, outer_len=outer_len)


def vol(x):
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    pr = GProp_GProps()
    BRepGProp.VolumeProperties_s(x.wrapped, pr, 1e-9)
    return pr.Mass()


def overlap(a, b):
    try:
        return sum(vol(z) for z in a.intersect(b).solids())
    except Exception:
        return float("nan")  # 同寸の管が同軸で接する(同一円筒面)と OCC が交差を計算できない


def check(parts, info, row, valve, L, d, others=None):
    """配置の確認を表示する。row: valve_row.build_row()、valve: "valve1" / "valve2"、others: 別の抜差の parts(あれば距離を測る)。"""
    case, ks, names = row[valve]
    stubs = [k for k, n in zip(ks, names) if n.endswith("L1_225") or n.endswith("L1_315")]  # B 階の下の枝管
    stub = {"L": min(stubs, key=lambda k: k.center().X), "R": max(stubs, key=lambda k: k.center().X)}
    print("--- 配置の確認")
    for nm, p in parts.items():
        bb = p.bounding_box()
        print(f"{nm}: valid={p.is_valid} x=[{bb.min.X:.2f},{bb.max.X:.2f}] y=[{bb.min.Y:.2f},{bb.max.Y:.2f}] z=[{bb.min.Z:.2f},{bb.max.Z:.2f}]")
    print("--- 接触・距離(重なり nan は同寸の管の同軸の接触)")
    pairs = []
    for nm in ("L", "R"):
        pairs += [(f"外管 {nm}", parts[f"outer_tube_{nm}"], f"枝管 {nm}", stub[nm]), (f"外管 {nm}", parts[f"outer_tube_{nm}"], f"中管 {nm}", parts[f"inner_tube_{nm}"]),
                  (f"外管 {nm}", parts[f"outer_tube_{nm}"], "ケース", case), (f"桂 {nm}", parts[f"ferrule_{nm}"], "頭管", parts["bow"]),
                  (f"桂 {nm}", parts[f"ferrule_{nm}"], f"中管 {nm}", parts[f"inner_tube_{nm}"]), (f"桂 {nm}", parts[f"ferrule_{nm}"], f"外管 {nm}", parts[f"outer_tube_{nm}"]),
                  ("頭管", parts["bow"], f"中管 {nm}", parts[f"inner_tube_{nm}"]), ("頭管", parts["bow"], f"外管 {nm}", parts[f"outer_tube_{nm}"])]
    pairs += [("桂 L", parts["ferrule_L"], "桂 R", parts["ferrule_R"]), ("頭管", parts["bow"], "ケース", case)]
    for an, a, bn, b in pairs:
        print(f"{an} ↔ {bn}: 距離 {a.distance_to(b):.4f} 重なり {overlap(a, b):.6f}")
    ib = parts["inner_tube_L"].bounding_box()
    print(f"中管の端面 y={ib.max.Y:.3f} と枝管の出口の端面 y={Y_STUB} の離れ: {Y_STUB - ib.max.Y:.3f}(= G + d = {G_GAP + d:.3f})、d=0(桂がつばに接触)のとき {Y_STUB - ib.max.Y - d:.3f}(= G)")
    fb = parts["ferrule_L"].bounding_box()
    print(f"桂 y=[{fb.min.Y:.3f},{fb.max.Y:.3f}]、桂の中管側の端とつばの面の隙間 = {info['y_c'] - fb.max.Y:.3f}(= d = {d:.3f})、外管の長さ {info['outer_len']:g}、継ぎ目 y={info['y_b']:.3f}")
    allp = list(parts.values())
    near = [(min(p.distance_to(x) for p in allp), n) for n, x in zip(names, ks) if not (n.endswith("L1_225") or n.endswith("L1_315"))]
    print("同じ植込みの他の枝管との最小距離: %.3f(%s)" % min(near))
    for v in ("valve1", "valve2", "valve3", "valve4"):
        if v == valve:
            continue
        c, kk, nn = row[v]
        print(f"{v} との最小距離 {min(min(p.distance_to(x) for x in [c] + list(kk)) for p in allp):.3f}")
    if others:
        print("別の抜差との最小距離: %.3f" % min(a.distance_to(b) for a in allp for b in others.values()))
