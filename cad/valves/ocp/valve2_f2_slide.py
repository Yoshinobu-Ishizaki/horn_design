"""第 2 植込の F 階(z=17)に、F 第 2 抜差を配置する。頭管(f2bow)と外管は Bb 第 2 抜差と同じ。抜き量の目安 10 mm、Open F に対して 100 セント下げる。
頭と中管をつなぐ桂 L8(両側飾り)、中管の途中にストッパの桂 L10(d=0 で中管の先端と枝管の出口が 1 mm)。
  python3 cad/valves/ocp/warm.py run cad/valves/ocp/valve2_f2_slide.py [--check]
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import f_slide as F  # noqa: E402
import bb_slide as S  # noqa: E402
import valve2_bb2_slide as V2  # noqa: E402

CENTS = 100.0
D_NOMINAL = 10.0
VALVE = "valve2"


def build():
    from valve_row import VALVES

    dl, l_exact, L, d = F.solve(CENTS, D_NOMINAL, V2.BOW_LEN)
    parts, info = F.slide_parts(VALVES[VALVE], V2.bow_slide(), L, d)
    return parts, info, (dl, l_exact, L, d)


def main():
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show
    from valve_row import build_row_cached

    parts, info, (dl, l_exact, L, d) = build()
    print(f"Open F 全長 {F.F_LENGTH:g} mm の {CENTS:g} セント: ΔL = {dl:.3f} mm、頭管 {V2.BOW_LEN:.3f}")
    print(f"d={D_NOMINAL:g} で満たす L = {l_exact:.3f} → 0.5 mm 単位で L = {L:.1f}、ちょうどの抜き量 d = {d:.3f} mm(d={D_NOMINAL:g} のときは {S.cents_of(L, D_NOMINAL, V2.BOW_LEN) and 1200 * __import__('math').log2(1 + S.extra(L, D_NOMINAL, V2.BOW_LEN) / F.F_LENGTH):.2f} セント)")
    print(f"外管 {F.OUTER_LEN:g}(つば y={info['y_c']:.2f})、中管 {L:g}、継ぎ目 y={info['y_j']:.3f}、ストッパ y=[{info['y_c'] - F.STOPPER_L - d:.2f},{info['y_c'] - d:.2f}]")
    row = build_row_cached()
    case, ks, names = row[VALVE]
    bb2 = V2.build()[0]
    show(case, *ks, *parts.values(), *bb2.values(),
         names=[f"{VALVE}_case"] + names + [f"fslide2_{k}" for k in parts] + [f"slide2_{k}" for k in bb2], reset_camera=Camera.KEEP)
    if "--check" in sys.argv:
        check(parts, info, row, bb2, d)


def check(parts, info, row, bb2, d):
    case, ks, names = row[VALVE]
    stubs = {"L": next(k for k, n in zip(ks, names) if n.endswith("L2_315")), "R": next(k for k, n in zip(ks, names) if n.endswith("L2_225"))}
    print("--- 確認")
    for nm in "LR":
        pairs = [("外管", parts[f"outer_tube_{nm}"], "枝管", stubs[nm]), ("外管", parts[f"outer_tube_{nm}"], "中管", parts[f"inner_tube_{nm}"]),
                 ("外管", parts[f"outer_tube_{nm}"], "ケース", case), ("桂", parts[f"ferrule_{nm}"], "頭管", parts["bow"]),
                 ("桂", parts[f"ferrule_{nm}"], "中管", parts[f"inner_tube_{nm}"]), ("ストッパ", parts[f"stopper_{nm}"], "中管", parts[f"inner_tube_{nm}"]),
                 ("ストッパ", parts[f"stopper_{nm}"], "外管", parts[f"outer_tube_{nm}"]), ("桂", parts[f"ferrule_{nm}"], "ストッパ", parts[f"stopper_{nm}"])]
        for an, a, bn, b in pairs:
            print(f"{an}{nm} ↔ {bn}: 距離 {a.distance_to(b):.4f} 重なり {S.overlap(a, b):.6f}")
    ib = parts["inner_tube_L"].bounding_box()
    print(f"中管の先端 y={ib.max.Y:.3f} と枝管の出口 y={S.Y_STUB}: 離れ {S.Y_STUB - ib.max.Y:.3f}(d=0 なら 1、今 G+d = {S.G_GAP + d:.3f})")
    allp = list(parts.values())
    print("Bb 第 2 抜差との最小距離: %.3f" % min(a.distance_to(b) for a in allp for b in bb2.values()))
    print("ケースとの最小距離: %.3f" % min(a.distance_to(case) for a in allp))
    print("他の枝管との最小距離: %.3f(%s)" % min((min(a.distance_to(k) for a in allp), n) for k, n in zip(ks, names) if not n.endswith(("L2_225", "L2_315"))))


if __name__ == "__main__":
    main()
