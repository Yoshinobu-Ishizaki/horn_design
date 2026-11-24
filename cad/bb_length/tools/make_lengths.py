"""Bb 管の部品ごとの芯線長を CSV に書く。uv run python cad/bb_length/tools/make_lengths.py"""
import sys, math
import numpy as np
from pathlib import Path
R = str(Path(__file__).resolve().parents[3]) + "/"
for p in ["cad/valves/ocp", "cad/bows/ocp", "cad/branch2/ocp", "cad/bell03/tools", "cad/bb34/ocp", "cad/bb_return/ocp", "cad/main_aux_tube/ocp", "src"]:
    sys.path.insert(0, R + p)
import make_centerline as MC
import valve4_knuckle as V
import ubows
import knuckle as KN

# 1. bell + 1番管
w = MC.build_wire(); wb = MC.build_branch_wire()
bell, br1 = w.length, wb.length
print("bell", bell, "branch1", br1)
# 2. U (pitch 50)
_, info = ubows.u_bow(50.0, None, None)
U50 = info["curve_len"] + 2 * ubows.LEG
print("U50 curve", info["curve_len"], "legs", ubows.LEG, "min R", info["rmin"], "total", U50)
K = KN.D1 + KN.L2
Kt = V.PULL_OUT_2F + KN.D1 + KN.L2
print("K", K, "Kt(2F)", Kt, "Kt(1F)", V.PULL_OUT + KN.D1 + KN.L2)
# exit of twisted 2f
k2 = V.twisted_knuckle_2f()
a_ring = math.pi/4*(12.8**2-12.0**2)
f = max((f for f in k2.faces() if f.geom_type.name=="PLANE" and abs(f.area-a_ring)<0.5), key=lambda f:-f.normal_at().Y)
F, uo = np.array(list(f.center())), np.array(list(f.normal_at()))
print("F2_225 exit", F, uo)
# bb34
P0y = 10.0
Q = F + (49.0 - F[2]) / uo[2] * uo
pitch = 46.0  # bb34_u.PITCH(RISE 15 は変えない)
_, i2 = ubows.u_bow(pitch, None, None)
Ub = i2["curve_len"] + 2*ubows.LEG
pst = np.array([25.0, Q[1], 49.0])
rmax = min(np.linalg.norm(Q-pst), np.linalg.norm(F-Q))
def Llen(r):
    return np.linalg.norm(Q-pst) - r + np.linalg.norm(F-Q) - r + math.pi/2*r
print("bb34 pitch", pitch, "U", Ub, "straight", 77.5, "L(R=rmax %.3f)"%rmax, Llen(rmax))
bb34 = Ub + 77.5 + Llen(rmax)
# 3-1 valves pass
vp = 2*K + 2*K + (K + 17.5)
# bb_return route: arc_path
import bb_return as BR
ps = np.array([127.021, -17.5, 34.0]); ts = np.array([0,1.0,0])
pe = np.array([47.374, 12.374, 34.0]); te = np.array([-math.sqrt(.5), -math.sqrt(.5), 0])
# exact numbers: U end x = 80 + 50 cos(phi)
phi = math.asin((34-17)/50); ps[0] = 80 + 50*math.cos(phi)
pe[0] = 35 + 17.5*math.cos(math.radians(45)); pe[1] = 17.5*math.sin(math.radians(45))
wr, inf = BR.arc_path(ps, ts, pe, te, 20.0)
route = wr.length
print("route", route, "x start", ps[0])
slide = 1 + 33 + U50 + 33 + 1
bbr = slide + route
# main aux
import main_aux_split as MS
E = np.array([59.0, -17.53, 20.689]);
import main_aux as MA
E, u = MA.f1_225_exit()
print("E", E, u)
S_end = np.array([95.0, -40.0, 80.348])
Pm = np.array(MS.PRESET[:3]); tS = np.array([1.0,0,0])
tm = MS.tm_of(Pm, E, u, S_end, tS)
w1, n1, k1, c1 = MS.g2_piece(E, u, Pm, tm, MS.G2_PRESET["aux1"])
w2, n2, k2_, c2 = MS.g2_piece(Pm, tm, S_end, tS, MS.G2_PRESET["aux2"])
aux = w1.length + w2.length
print("aux1", w1.length, "aux2", w2.length)


import csv, re
v4_2f = K + Kt
v4_1f = K + V.PULL_OUT + KN.D1 + KN.L2
OUT = Path(__file__).resolve().parent.parent
parts = [
 ("bell", "ベル(リム→曲げ終わり)", bell, "cad/bell03 make_centerline.build_wire"),
 ("branch1", "1番管(2番管との接続点まで)", br1, "make_centerline.build_branch_wire"),
 ("branch2_U", "2番管 U(ピッチ50、直管5x2込み)", U50, "ubows.u_bow(50)"),
 ("v4_2f", "第4 2階: 315°枝管 K + 225°ねじり枝管(中心→端面、ローター中心経由)", v4_2f, "K=21.642, Kt=PULL+D1+L2=23.056"),
 ("bb34_U", "bb34 U(ピッチ46、直管5x2込み)", Ub, "ubows.u_bow"),
 ("bb34_straight", "bb34 直管(x -52.5→25)", 77.5, ""),
 ("valves321", "第3→第2→第1 ローター通過(2K+2K+K+17.5)", vp, "第1右上は直管17.5"),
 ("bb_slide", "Bb抜差(隙間1+中管33+U(50)+中管33+隙間1、抜き量0)", slide, "slide_u.py"),
 ("bb_return", "bb_return 経路(直線20+円弧+直線)", route, "bb_return.arc_path"),
 ("v4_1f", "第4 1階: 315°枝管 K + 225°ねじり枝管", v4_1f, ""),
 ("main_aux", "主管補助管 aux1+aux2(G2)", aux, "main_aux_split.g2_piece"),
 ("main_slide_gap", "主管抜差: 補助管2の口から中管までの隙間", 1.0, "main_slide.py GAP"),
 ("main_slide_inner", "主管抜差: 中管1本(Bb第2と同じ長さ)", 33.0, "main_slide.py"),
]
t = 0
with open(OUT / "bb_lengths.csv", "w", newline="", encoding="utf-8") as f:
    wr_ = csv.writer(f); wr_.writerow(["id", "name", "length_mm", "cumulative_mm", "note"])
    for i_, n, v, note in parts:
        t += v; wr_.writerow([i_, n, f"{v:.3f}", f"{t:.3f}", note])
print("total", t)
# mensur sections (bell03_Bb.men, consecutive same-label rows merged)
men = Path(R) / "impedance/bell03/bell03_Bb.men"
secs = []
for line in men.read_text(encoding="utf-8").splitlines()[1:]:
    c = line.split(",")
    if len(c) >= 4 and re.match(r"^-?[0-9.]", c[0]):
        if secs and secs[-1][0] == c[3]: secs[-1][1] += float(c[2])
        else: secs.append([c[3], float(c[2])])
c_ = 0
with open(OUT / "bb_mensur_sections.csv", "w", newline="", encoding="utf-8") as f:
    wr_ = csv.writer(f); wr_.writerow(["section", "length_mm", "cumulative_mm"])
    for n, v in secs:
        c_ += v; wr_.writerow([n, f"{v:.3f}", f"{c_:.3f}"])
print("mensur total", c_, "diff", c_ - t)
