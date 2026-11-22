"""第 2 植込の B 階(2 階、z=34)に、Bb 第 2 抜差を配置する。

迂回の長さと中管の長さの決め方(経路は各管の中心線で数える):
  ・ポートは通常 x 方向につながる(開いた状態: 上の 135° と 45° の枝管)。ローターが 90° 回ると、上の枝管が下の枝管
    (225° と 315°、2 本目が -Y、x=±10、ピッチ 20)につながり、抜差側へ迂回する。
  ・増加分 ΔL = (回した状態の主経路)−(開いた状態の主経路) = 枝管 2 本分 + 抜差の輪
      枝管 1 本の中心線 K = 14.142(ローターの中心 → 角)+ 7.5(角 → 出口)= 21.642
      抜差の輪 = 2 ×(離れ G + 抜き量 d + 中管の長さ L)+ 頭管(f2bow: 5 + π·10 + 5)
      G: 桂が外管のつばに接触する状態(d=0)で、中管の端面と枝管の出口の端面の離れ(1 mm。空気の経路には入る)
    ローターの中を通る経路は、どちらの状態でも枝管の始点(ローターの中心)を通るので打ち消し合う。
  ・100 セント(半音)に必要な増加分 ΔL = 全長 × (2^(1/12) - 1)。全長は、最新の設計(bell03)の Bb 管の全長 2743.4 mm。
  ・d = 5 mm で ΔL を満たす L を、0.5 mm 単位に丸める。そのうえで、ちょうど 100 セントになる d(端数になってよい)を求める。
抜差の構造(仮定): 外管(つば付き)は、枝管の出口に外から被せる(差し込み深さ S_IN)。中管は、外管のつば側から入る。
  中管と頭管の継ぎ目に、桂(L12)を外から被せる: 頭管側に 4 mm、中管側に 8 mm。
  d = 0(桂の中管側の端が外管のつばの面に突き当たる状態)で、中管の端面は枝管の出口の端面から G=1 mm 離れている。
  d だけ抜くと、桂の端は、つばの面から d だけ離れ、中管の端面は枝管の出口から G + d 離れる。
  外管のつばの面は、y = Y_STUB − G − L + 8(桂の中管側 8)。
  経路の長さ(枝管の出口の端面から頭管の直管の端面まで = G + d + L)は桂で変わらない。
座標: 第 2 植込は x=0(valve_row)。枝管の出口の端面は y=-17.5、x=±10、z=34。
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
from inner_tube import inner_tube  # noqa: E402
from outer_tube import outer_tube  # noqa: E402
from ferrule import ferrule  # noqa: E402

import bows  # noqa: E402

BB_LENGTH = 2743.4  # Bb 管の全長(bell03、impedance/bell03/README.md)
CENTS = 100.0
K_KNUCKLE = 10 * math.sqrt(2) + 7.5  # 枝管 1 本の中心線(ローターの中心 → 出口)
BOW_LEN = 5 + math.pi * 10 + 5  # f2bow の中心線(直管 5 + 半円 R10 + 直管 5)
PITCH = 20.0
Z_B = 34.0  # B 階
Y_STUB = -17.5  # 枝管の出口の端面(下の枝管)
FERRULE_L = 12.0  # 桂の長さ
FERRULE_ON_BOW = 4.0  # 桂を頭管側に被せる長さ(頭管の直管は 5 mm)
FERRULE_ON_TUBE = FERRULE_L - FERRULE_ON_BOW  # 中管側に被せる長さ(8)
S_IN = 4.0  # 外管が枝管の出口に被さる深さ(仮)。5 だとスリーブの端がケースに 0.045 mm³ 食い込むので 4
D_NOMINAL = 5.0  # 抜く量の目安(全長が 10 増える)
G_GAP = 1.0  # d=0(桂が外管のつばに接触)での、中管の端面と枝管の出口の端面の離れ


def required_extra(length=BB_LENGTH, cents=CENTS):
    return length * (2 ** (cents / 1200.0) - 1.0)


def solve(length=BB_LENGTH, cents=CENTS, d_nominal=D_NOMINAL, step=0.5):
    """戻り値: (ΔL、d_nominal で ΔL を満たす L(丸める前)、丸めた L、ちょうど ΔL になる d)。"""
    dl = required_extra(length, cents)
    l_exact = (dl - 2 * K_KNUCKLE - BOW_LEN) / 2 - G_GAP - d_nominal
    l_round = round(l_exact / step) * step
    d = (dl - 2 * K_KNUCKLE - BOW_LEN) / 2 - G_GAP - l_round
    return dl, l_exact, l_round, d


def extra(L, d):
    return 2 * K_KNUCKLE + 2 * (G_GAP + d + L) + BOW_LEN


def cents_of(L, d, length=BB_LENGTH):
    return 1200.0 * math.log2(1.0 + extra(L, d) / length)


def build(L=None, d=None, s_in=S_IN, bead_on="bow"):
    """第 2 抜差(外管 2 本、桂 2 個、頭管、中管 2 本)。戻り値: (dict(名前 → ソリッド)、L、d)。
    bead_on: 桂の飾り線(端から 3 mm)を、頭管側("bow")か中管側("tube")の端に置く。"""
    if L is None:
        _, _, L, d_exact = solve()
        d = d_exact if d is None else d
    y_c = Y_STUB - G_GAP - L + FERRULE_ON_TUBE  # 外管のつばの面(桂の中管側の端が d=0 で突き当たる。このとき中管の端面は枝管の出口から G 離れる)
    outer_len = (Y_STUB + s_in) - y_c  # つば側の端 y_c から、枝管の出口に被さる端(Y_STUB + s_in)まで
    y_b = y_c - FERRULE_ON_TUBE - d  # 頭管の直管の端面(= 頭管と中管の継ぎ目)
    parts = {}
    # 外管: 局所 Z(つば側が z=0)を +Y へ(Rot(-90,0,0): Z → +Y)。
    for nm, x in (("L", -PITCH / 2), ("R", +PITCH / 2)):
        parts[f"outer_tube_{nm}"] = Pos(x, y_c, Z_B) * Rot(-90, 0, 0) * outer_tube(outer_len)
    # 頭管 + 中管: bb2_head_assy の座標(頭管の直管の端面が y=0、中管は -Y へ)を、Z まわり 180° 回して、
    # 中管が +Y(バルブ側)、頭管が -Y になるようにし、直管の端面(継ぎ目)を y_b に置く。
    import bb2_head_assy as H

    bow, left, right, _ = H.build(PITCH, L)
    T = Pos(0, y_b, Z_B) * Rot(0, 0, 180)
    parts["bow_f2bow"] = T * bow
    parts["inner_tube_L"] = T * right  # 180° 回すので、元の右が左(x=-10)に来る
    parts["inner_tube_R"] = T * left
    # 桂: 継ぎ目 y_b を中心に、頭管側(-Y)へ 4、中管側(+Y)へ 8。局所 Z(0〜12)を +Y へ。飾り線は局所 z=3(端から 3)。
    y0 = y_b - FERRULE_ON_BOW  # 桂の頭管側の端
    for nm, x in (("L", -PITCH / 2), ("R", +PITCH / 2)):
        f = ferrule(FERRULE_L)
        if bead_on == "tube":  # 飾り線を中管側の端に: 局所 Z を反転
            f = Pos(0, 0, FERRULE_L) * Rot(180, 0, 0) * f
        parts[f"ferrule_{nm}"] = Pos(x, y0, Z_B) * Rot(-90, 0, 0) * f
    return parts, L, d


def main():
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show
    from valve_row import build_row

    dl, l_exact, L, d = solve()
    print(f"全長 {BB_LENGTH} mm の {CENTS:g} セント: ΔL = {dl:.3f} mm")
    print(f"枝管 1 本の中心線 {K_KNUCKLE:.3f}、頭管 {BOW_LEN:.3f}、離れ G={G_GAP:g}。d={D_NOMINAL:g} で ΔL を満たす L = {l_exact:.3f} → 0.5 mm 単位で L = {L:.1f}")
    print(f"L = {L:.1f} で、ちょうど {CENTS:g} セントになる抜き量 d = {d:.3f} mm(d = 5 のときは {cents_of(L, 5.0):.2f} セント)")
    print(f"  迂回で増える長さ = 2·{K_KNUCKLE:.3f} + 2·({G_GAP:g} + {d:.3f} + {L:.1f}) + {BOW_LEN:.3f} = {extra(L, d):.3f} (= ΔL)")

    parts, L, d = build(L, d)
    row = build_row()
    case, ks, names = row["valve2"]
    show(case, *ks, *parts.values(), names=["valve2_case"] + names + list(parts), reset_camera=Camera.KEEP)

    def vol(x):
        pr = GProp_GProps()
        BRepGProp.VolumeProperties_s(x.wrapped, pr, 1e-9)
        return pr.Mass()

    def overlap(a, b):
        try:
            return sum(vol(z) for z in a.intersect(b).solids())
        except Exception:
            return float("nan")

    # B 階(z=34)の下の枝管(2 本目が -Y)。名前(225° / 315°)は元の座標系なので、実際の位置(x)で左右を決める。
    stubs = [k for k, n in zip(ks, names) if n.endswith("L1_225") or n.endswith("L1_315")]
    stub_L = min(stubs, key=lambda k: k.center().X)  # x=-10 側
    stub_R = max(stubs, key=lambda k: k.center().X)  # x=+10 側
    print("--- 配置の確認")
    for nm, x in (("L", stub_L), ("R", stub_R)):
        bb = x.bounding_box()
        print(f"枝管 {nm}(B 階の下): x=[{bb.min.X:.2f},{bb.max.X:.2f}] y 最小 {bb.min.Y:.2f}(出口の端面 {Y_STUB}) z=[{bb.min.Z:.2f},{bb.max.Z:.2f}]")
    for nm, p in parts.items():
        bb = p.bounding_box()
        print(f"{nm}: valid={p.is_valid} x=[{bb.min.X:.2f},{bb.max.X:.2f}] y=[{bb.min.Y:.2f},{bb.max.Y:.2f}] z=[{bb.min.Z:.2f},{bb.max.Z:.2f}]")
    print("--- 干渉(重なり体積 / 最小距離)")
    pairs = [("外管 L", parts["outer_tube_L"], "枝管 L", stub_L), ("外管 R", parts["outer_tube_R"], "枝管 R", stub_R),
             ("外管 L", parts["outer_tube_L"], "中管 L", parts["inner_tube_L"]), ("外管 R", parts["outer_tube_R"], "中管 R", parts["inner_tube_R"]),
             ("外管 L", parts["outer_tube_L"], "valve2 ケース", case), ("外管 R", parts["outer_tube_R"], "valve2 ケース", case),
             ("頭管", parts["bow_f2bow"], "中管 L", parts["inner_tube_L"]), ("頭管", parts["bow_f2bow"], "中管 R", parts["inner_tube_R"]),
             ("頭管", parts["bow_f2bow"], "外管 L", parts["outer_tube_L"]), ("頭管", parts["bow_f2bow"], "外管 R", parts["outer_tube_R"]),
             ("桂 L", parts["ferrule_L"], "頭管", parts["bow_f2bow"]), ("桂 L", parts["ferrule_L"], "中管 L", parts["inner_tube_L"]),
             ("桂 R", parts["ferrule_R"], "頭管", parts["bow_f2bow"]), ("桂 R", parts["ferrule_R"], "中管 R", parts["inner_tube_R"]),
             ("桂 L", parts["ferrule_L"], "外管 L", parts["outer_tube_L"]), ("桂 R", parts["ferrule_R"], "外管 R", parts["outer_tube_R"]),
             ("桂 L", parts["ferrule_L"], "桂 R", parts["ferrule_R"])]
    for an, a, bn, b in pairs:
        print(f"{an} ↔ {bn}: 距離 {a.distance_to(b):.4f} 重なり {overlap(a, b):.6f}")
    near = [(min(p.distance_to(x) for p in parts.values()), n) for n, x in zip(names, ks) if not (n.endswith("L1_225") or n.endswith("L1_315"))]
    print("valve2 の他の枝管との最小距離(スリーブなど): %.3f(%s)" % min(near))
    for v in ("valve1", "valve3"):
        c, kk, nn = row[v]
        d_min = min(min(p.distance_to(x) for x in [c] + list(kk)) for p in parts.values())
        print(f"{v} との最小距離 {d_min:.3f}")
    # 経路の長さ(CAD の寸法から再計算)
    inner_len = parts["inner_tube_L"].bounding_box().size.Y
    y_c = Y_STUB - G_GAP - L + FERRULE_ON_TUBE
    fb = parts["ferrule_L"].bounding_box()
    ib = parts["inner_tube_L"].bounding_box()
    print(f"中管の端面 y={ib.max.Y:.3f} と枝管の出口の端面 y={Y_STUB} の離れ = {ib.max.Y - Y_STUB:.3f} の逆 → {Y_STUB - ib.max.Y:.3f}(= G + d = {G_GAP + d:.3f})、d=0(桂がつばに接触)のとき {Y_STUB - ib.max.Y - d:.3f}(= G = {G_GAP:g})")
    print(f"中管の長さ(CAD)= {inner_len:.3f} / 外管のつば面 y={y_c:.3f} / 継ぎ目(頭管の直管の端面)y={y_c - FERRULE_ON_TUBE - d:.3f}")
    print(f"桂: y=[{fb.min.Y:.3f},{fb.max.Y:.3f}](長さ {fb.size.Y:.3f})、頭管側 {FERRULE_ON_BOW:g} + 中管側 {FERRULE_ON_TUBE:g}、桂の中管側の端とつばの面の隙間 = {y_c - fb.max.Y:.3f}(= d)")
    print(f"外管の長さ {(Y_STUB + S_IN) - y_c:g}(つばから枝管の出口に被さる端まで)")


if __name__ == "__main__":
    main()
