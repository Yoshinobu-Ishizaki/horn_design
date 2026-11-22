"""Sample: RefBell bell (inner bore) from DXF centerline + L-D table, via bope_claude_cad.vss.

Usage: uv run python skills/claude_cad_vss/scripts/bell_from_dxf.py DXF [--ds 4] [--csv out.csv]
Centerline = vertical line from the rim centre + Layer0 arcs R305,R160,R151,R147,R130 (in this order).
"""

import argparse
import math
import sys
import time

import ezdxf
import numpy as np
from build123d import Edge, Line, ThreePointArc, Vector, Wire

from bope_claude_cad.vss import check_variable_pipe, variable_pipe

# The centerline starts at the bottom of the rim wire (phi3 circle, centre y 99.86, bottom 98.36), on the
# vertical axis x = R305 arc end. The vertical part is 240 long (drawing dimension "240"), so
# start y = (R305 centre y) - 240. This makes the total 851.1635 = table end 851.163 (a misread start
# y=98.86 from the spline start gave 850.67, 0.5 short).
RIM_VERTICAL = 240.0
ARC_ORDER = [305.0, 160.0, 151.0, 147.0, 130.0]


def read_table(msp):
    """Pair L/D numeric texts of the 3 column pairs by band and y."""
    bands = [("L", -226, -214, 0), ("D", -189, -182, 0),
             ("L", -152, -147, 1), ("D", -114, -112, 1),
             ("L", -82, -80, 2), ("D", -44, -42, 2)]
    txt = [(e.dxf.insert[0], round(e.dxf.insert[1], 1), e.dxf.text.strip())
           for e in msp if e.dxftype() == "TEXT" and e.dxf.layer == "Layer30"]
    out = {}
    for kind, x0, x1, grp in bands:
        for x, y, s in txt:
            if x0 <= x <= x1 and y > 100 and s.replace(".", "").isdigit() and "." in s:
                out.setdefault((grp, y), {})[kind] = float(s)
    rows = [(v["L"], v["D"]) for v in out.values() if "L" in v and "D" in v]
    rows.sort()
    return np.array([r[0] for r in rows]), np.array([r[1] for r in rows])


def build_centerline(msp):
    arcs = {round(e.dxf.radius, 1): e for e in msp
            if e.dxftype() == "ARC" and e.dxf.layer == "Layer0" and e.dxf.radius > 100}
    # shift so the rim centre (L = 0) is the origin
    first_arc = arcs[ARC_ORDER[0]]
    ox = first_arc.dxf.center[0] - first_arc.dxf.radius  # x of the vertical axis (R305 arc end)
    oy = first_arc.dxf.center[1] - RIM_VERTICAL
    edges = []
    cur = Vector(0, 0)
    top = Vector(first_arc.dxf.center[0] - first_arc.dxf.radius - ox, first_arc.dxf.center[1] - oy)
    edges.append(Line(cur, top))
    for r in ARC_ORDER:
        e = arcs[r]
        cx, cy = e.dxf.center[0] - ox, e.dxf.center[1] - oy
        a0, a1 = e.dxf.start_angle, e.dxf.end_angle
        if a1 < a0:
            a1 += 360.0
        # direction: the end of the previous piece must coincide with the start
        def pt(a):
            return Vector(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
        p0, p1 = pt(a0), pt(a1)
        if (p0 - top).length > (p1 - top).length:
            a0, a1 = a1, a0
            p0, p1 = p1, p0
        am = (a0 + a1) / 2
        edges.append(ThreePointArc(top, pt(am), p1))  # start snapped to previous end (DXF has ~1e-3 gaps)
        top = p1
    return Wire([e if isinstance(e, Edge) else e.edges()[0] for e in edges])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dxf")
    ap.add_argument("--ds", type=float, default=4.0)
    ap.add_argument("--csv")
    a = ap.parse_args()
    msp = ezdxf.readfile(a.dxf).modelspace()
    L, D = read_table(msp)
    print("table rows", len(L), "L", L[0], L[-1], "D", D[0], D[-1])
    if a.csv:
        with open(a.csv, "w", encoding="utf-8") as f:
            f.write("L,D\n")
            f.writelines(f"{l},{d}\n" for l, d in zip(L, D))
    cl = build_centerline(msp)
    print("centerline length", round(cl.length, 4), "table end", L[-1], "diff", round(cl.length - L[-1], 4))
    t = time.time()
    solid, prof, ls = variable_pipe(cl, L, D, ds=a.ds)
    print("stations", len(ls), "loft sec", round(time.time() - t, 1))
    r = check_variable_pipe(solid, cl, prof)
    print({k: v for k, v in r.items() if k != "samples"})
    worst = sorted(r["samples"], key=lambda x: -abs(x[1]))[:5]
    print("worst", [(round(s, 1), round(e, 4)) for s, e in worst])
    return solid, cl


if __name__ == "__main__":
    sys.exit(main() and 0)
