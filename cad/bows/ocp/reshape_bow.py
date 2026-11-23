"""頭管の中心線(直線・円弧の並び)を、直線の入口・出口と終点の位置を保ったまま、曲線部の長さだけ目標値に縮める(または伸ばす)。
今の形からの変化が最小になるよう、円弧の半径・角度と中間の直線の長さを決める(最小曲げ半径は今の最小値を下回らない)。
  uv run python cad/bows/ocp/reshape_bow.py b1bow 104.7
曲線部の長さ = 入口と出口の直線を除いた、円弧と中間の直線の合計。
"""

import math
import sys

import numpy as np
from scipy.optimize import minimize

import bows


def path(start, heading, segs, n=30):
    h = heading
    p = np.array(start, float)
    pts = [p.copy()]
    for s in segs:
        if s[0] == "L":
            d = np.array([math.cos(math.radians(h)), math.sin(math.radians(h))])
            pts += [p + s[1] * t * d for t in np.linspace(0, 1, n)[1:]]
            p = p + s[1] * d
        else:
            R, a = s[1], s[2]
            sg = 1 if a > 0 else -1
            hr = math.radians(h)
            c = p + sg * R * np.array([-math.sin(hr), math.cos(hr)])
            a0 = math.atan2(p[1] - c[1], p[0] - c[0])
            pts += [c + R * np.array([math.cos(a0 + math.radians(a) * t), math.sin(a0 + math.radians(a) * t)]) for t in np.linspace(0, 1, 3 * n)[1:]]
            p = pts[-1].copy()
            h += a
    return np.array(pts), p, h


def reshape(name, target_curve):
    d = bows.BOWS[name]
    segs = d["segs"]
    mid = segs[1:-1]
    first, last = segs[0], segs[-1]
    arcs = [i for i, s in enumerate(mid) if s[0] == "A"]
    last_arc = arcs[-1]
    turn_total = sum(s[2] for s in mid if s[0] == "A")
    rmin = min(s[1] for s in mid if s[0] == "A")
    # 変数: 各円弧の R、(最後以外の)円弧の角度、中間の直線の長さ
    x0, kinds = [], []
    for i, s in enumerate(mid):
        if s[0] == "A":
            x0.append(s[1]); kinds.append(("R", i))
            if i != last_arc:
                x0.append(abs(s[2])); kinds.append(("a", i))
        else:
            x0.append(s[1]); kinds.append(("L", i))
    x0 = np.array(x0)

    def build(x):
        vals = {}
        for (k, i), v in zip(kinds, x):
            vals[(k, i)] = v
        out = [first]
        acc = 0.0
        for i, s in enumerate(mid):
            if s[0] == "L":
                out.append(("L", vals[("L", i)]))
            else:
                sgn = 1 if s[2] > 0 else -1
                if i == last_arc:
                    a = turn_total - acc
                else:
                    a = sgn * vals[("a", i)]
                    acc += a
                out.append(("A", vals[("R", i)], a))
        out.append(last)
        return out

    def curve_len(x):
        sg = build(x)[1:-1]
        return sum(s[1] if s[0] == "L" else s[1] * abs(math.radians(s[2])) for s in sg)

    end0 = path(d["start"], d["heading"], segs)[1]
    cons = [{"type": "eq", "fun": lambda x: path(d["start"], d["heading"], build(x))[1][0] - end0[0]},
            {"type": "eq", "fun": lambda x: path(d["start"], d["heading"], build(x))[1][1] - end0[1]},
            {"type": "eq", "fun": lambda x: curve_len(x) - target_curve}]
    lo = [rmin if k == "R" else (1.0 if k == "a" else 0.0) for k, _ in kinds]
    sc = np.array([10.0 if k == "R" else (30.0 if k == "a" else 10.0) for k, _ in kinds])
    r = minimize(lambda x: np.sum(((x - x0) / sc) ** 2), x0, constraints=cons, bounds=[(l, None) for l in lo], method="SLSQP", options=dict(ftol=1e-14, maxiter=2000))
    sg = build(r.x)
    pe = path(d["start"], d["heading"], sg)[1]
    return sg, curve_len(x0), curve_len(r.x), pe, end0, r.success


if __name__ == "__main__":
    name, target = sys.argv[1], float(sys.argv[2])
    sg, c0, c1, pe, end0, ok = reshape(name, target)
    print("success", ok, "曲線部", round(c0, 3), "→", round(c1, 3), "終点", np.round(pe, 4), "元", np.round(end0, 4))
    print("segs=[" + ", ".join(f'("L", {s[1]:.4f})' if s[0] == "L" else f'("A", {s[1]:.4f}, {s[2]:.4f})' for s in sg) + "]")
