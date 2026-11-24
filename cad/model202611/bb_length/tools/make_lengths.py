"""Bb 管の部品ごとの芯線長を CSV に書く。uv run python cad/model202611/bb_length/tools/make_lengths.py
管の部品は、いまビューアに出している形(output/viewer_registry の芯線)で測る。先に main_slide.py を表示しておく。"""
import sys, math
import numpy as np
from pathlib import Path
sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if p.name == "model202611")))
import model_paths  # noqa: E402

ROOT = model_paths.add()
R = str(ROOT) + "/"
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
# 管の部品は、いまビューアに出している形の芯線(output/viewer_registry)から測る(2026-11-24。手で写した値が古くなるため)
from build123d import import_brep
REG = Path(R) / "output/viewer_registry"
def reg_len(nm):
    return import_brep(str(REG / f"{nm}.brep")).length
def reg_x_extent(nm):
    b = import_brep(str(REG / f"{nm}.brep")).bounding_box()
    return b.max.X - b.min.X
Ub, bbL = reg_len("bb34_U_centerline"), reg_len("bb34_L_centerline")
b1L = reg_len("branch1_L_centerline")  # 1番管の細い端の L 字管(2026-11-24)
bb34_st = reg_x_extent("bb34_straight_wall")
# 3-1 valves pass
vp = 2*K + 2*K + (K + 17.5)
chev, u315 = reg_len("bb_return_centerline"), reg_len("v4_f1_315_U_centerline")
aux1, aux2 = reg_len("main_aux1_centerline"), reg_len("main_aux2_centerline")
bow = reg_len("main_bow_centerline")
import main_slide as MSL
import slide_u as SU
import mouthpipe as MP
mp = reg_len("mouthpipe_centerline")
MOUTHPIECE_OUT = 46.0  # マウスピースは 18 mm 差し込み、46 mm 飛び出る(2026-11-24。メンズールのマウスピース 64 = 46 + 18)
print("mouthpipe", mp, "gap", MP.GAP, "mouthpiece out", MOUTHPIECE_OUT)
print("bb34 U", Ub, "L", bbL, "straight", bb34_st, "chevron", chev, "U315", u315, "aux1", aux1, "aux2", aux2, "bow", bow)


import csv, re
Kt1 = V.PULL_OUT + KN.D1 + KN.L2  # v4-f1-225 と同じねじった枝管(抜き量 √2)
v4_2f = Kt1 + Kt  # 2 階右下 = v4-f1-225 と同じ枝管の鏡像 Kt1、2 階左下 Kt(2026-11-24)
v4_1f = K + V.PULL_OUT + KN.D1 + KN.L2
OUT = Path(__file__).resolve().parent.parent
parts = [
 ("bell", "ベル(リム→曲げ終わり)", bell, "cad/bell03 make_centerline.build_wire"),
 ("branch1", "1番管(L 字管との接続点まで)", br1, "make_centerline.build_branch_wire"),
 ("branch1_L", "1番管の細い端の L 字管(第 4 の 2 階右下の枝管まで)", b1L, "viewer_registry branch1_L_centerline"),
 ("v4_2f", "第4 2階: 315°ねじり枝管(v4-f1-225 と同じ形の鏡像)Kt1 + 225°ねじり枝管 Kt(中心→端面、ローター中心経由)", v4_2f, f"Kt1=PULL_OUT+D1+L2={Kt1:.3f}, Kt=PULL_2F+D1+L2={Kt:.3f}"),
 ("bb34_U", "bb34 U(直管5x2込み)", Ub, "viewer_registry bb34_U_centerline"),
 ("bb34_straight", "bb34 直管", bb34_st, "viewer_registry bb34_straight_wall の X 幅"),
 ("bb34_L", "bb34 L 字管(G2)", bbL, "viewer_registry bb34_L_centerline"),
 ("valves321", "第3→第2→第1 ローター通過(2K+2K+K+17.5)", vp, "第1右上は直管17.5"),
 ("bb_return", "bb_return 山形管(第1 F2-45 → U の端、G2)", chev, "viewer_registry bb_return_centerline"),
 ("v4_f1_315_U", "第4 1階 315°枝管の U(ピッチ 40、直管5x2込み)", u315, "viewer_registry v4_f1_315_U_centerline"),
 ("v4_1f", "第4 1階: 315°枝管 K + 225°ねじり枝管", v4_1f, ""),
 ("main_aux1", "主管補助管 1(直線+G2+直線)", aux1, "viewer_registry main_aux1_centerline"),
 ("main_aux2", "主管補助管 2(直線+G2+直線)", aux2, "viewer_registry main_aux2_centerline"),
 ("main_slide_gap", "主管抜差: 補助管2の口から中管までの隙間", MSL.GAP, "main_slide.py GAP"),
 ("main_slide_inner", "主管抜差: 中管 1", MSL.INNER1_LEN, "main_slide.py INNER1_LEN"),
 ("main_bow", "主管頭 U(直管5x2込み)", bow, "viewer_registry main_bow_centerline"),
 ("main_slide_inner2", "主管抜差: 中管 2(末端まで)", MSL.INNER2_LEN, "main_slide.py INNER2_LEN"),
 ("mouthpipe_gap", "吹込管: 中管 2 の末端から吹込管の太い端までの隙間", MP.GAP, "mouthpipe.py GAP"),
 ("mouthpipe", "吹込管(太い端 → 入口の端面)", mp, "viewer_registry mouthpipe_centerline(mouthpipe_try.py の作図)"),
 ("mouthpiece_out", "マウスピースの飛び出し(入口の端面 → リム。差し込み 18 は吹込管に含む)", MOUTHPIECE_OUT, "make_lengths.py MOUTHPIECE_OUT"),
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
