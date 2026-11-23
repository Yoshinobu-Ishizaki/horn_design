"""頭管の曲線部(スプライン版)の長さが目標値になるよう、reshape_bow で円弧の形を調整する(反復)。
  uv run python cad/bows/ocp/fit_head_length.py b1bow 104.68 [gap]
スプライン化(bow_spline)で、基準の円弧の長さと少し違う長さになる(特に胃袋形の gap 3.4 で長くなる)ので、その差を補正して繰り返す。
結果の segs を表示する(bows.py に反映するのは人が行う)。
"""

import sys

import bow_spline as B
import bows
import reshape_bow as R


def spline_curve_len(name, gap):
    cfg, v, ref, crv, wire = B.bow_curve(name, B.W_DEFAULT, gap)
    a = B.analyze(cfg, v, ref, B.W_DEFAULT)
    return a["L"], a, cfg


if __name__ == "__main__":
    name, target = sys.argv[1], float(sys.argv[2])
    gap = float(sys.argv[3]) if len(sys.argv) > 3 else None
    orig = bows.BOWS[name]["segs"]
    want_arc = target
    for it in range(6):
        sg, c0, c1, pe, end0, ok = R.reshape(name, want_arc)
        bows.BOWS[name]["segs"] = sg
        L, a, cfg = spline_curve_len(name, gap)
        print(f"反復 {it}: 基準の曲線部 {c1:.3f}、スプライン {L:.3f}(目標 {target:.3f})最小R {1 / abs(a['kmin']):.1f} 間隔 {a['sep']:.3f} 元の形から最大 {a['dmax']:.2f}", flush=True)
        if abs(L - target) < 0.05:
            break
        want_arc += target - L
        bows.BOWS[name]["segs"] = orig
    print("segs=[" + ", ".join(f'("L", {s[1]:.4f})' if s[0] == "L" else f'("A", {s[1]:.4f}, {s[2]:.4f})' for s in sg) + "]")
