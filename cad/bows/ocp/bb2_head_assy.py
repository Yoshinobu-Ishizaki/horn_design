"""Bb 第 2 抜差頭の組立: 頭管(U 字)の 2 本の直管に、中管を 1 本ずつ連結する。

頭管と中管は、同じ寸法の管(外径 12.8 / 内径 12.0)。頭管の直管の端面(y=0)に、中管の端面を突き合わせて同軸に連結する。
座標は頭管(ubows.py / bows.py)と同じ: 頭管は XY 平面内で、キャップが +Y 側、2 本の直管の端が (±P/2, 0)。
中管は y=0 から -Y 方向へ長さ TUBE_L(軸は Y)。
頭管: ピッチ 20 の U 字 = f2bow(R10 の半円、直管 5 mm)。ピッチ 20 以外は ubows.u_bow(ピッチ)(ピッチ ≤ 30 は半円、それ以上は G2 のスプライン)。
中管の長さは仮(既存の inner_tube の sl-b2 = 42)。
"""

import math
import sys
from pathlib import Path

from build123d import Pos, Rot

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tubes" / "ocp"))
sys.path.insert(0, str(HERE))
from inner_tube import LENGTHS, inner_tube  # noqa: E402

import bows  # noqa: E402
import ubows  # noqa: E402

PITCH = 20.0  # 頭管のピッチ(= f2bow)
TUBE_L = LENGTHS["sl-b2"]  # 42(仮)


def build(pitch: float = PITCH, tube_l: float = TUBE_L):
    """戻り値: (頭管, 左の中管, 右の中管, 頭管の情報)。"""
    if abs(pitch - 20.0) < 1e-9:
        b, info = bows.bow("f2bow"), dict(kind="f2bow(半円 R10、直管 5)")
    else:
        b, info = ubows.u_bow(pitch)
    # 中管: 軸 Z(0〜L)を、Rot(90,0,0) で Z → -Y に(y=0 から -Y 方向へ長さ L)。左右の直管の軸 x = ±P/2。
    t = inner_tube(tube_l)
    left = Pos(-pitch / 2, 0, 0) * Rot(90, 0, 0) * t
    right = Pos(+pitch / 2, 0, 0) * Rot(90, 0, 0) * t
    return b, left, right, info


def main():
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show

    b, left, right, info = build()
    show(b, left, right, names=["bow_f2bow", "inner_tube_L", "inner_tube_R"], reset_camera=Camera.KEEP)
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    def vol(x):
        p = GProp_GProps()
        BRepGProp.VolumeProperties_s(x.wrapped, p, 1e-9)
        return p.Mass()

    def overlap(x, y):
        try:
            return sum(vol(z) for z in x.intersect(y).solids())
        except Exception:
            return 0.0

    print("頭管:", info["kind"], " valid", b.is_valid)
    for nm, t in (("左", left), ("右", right)):
        bb = t.bounding_box()
        print(f"中管 {nm}: valid={t.is_valid} x=[{bb.min.X:.2f},{bb.max.X:.2f}] y=[{bb.min.Y:.2f},{bb.max.Y:.2f}] z=[{bb.min.Z:.2f},{bb.max.Z:.2f}]")
    print("連結: 頭管 ↔ 左の中管 距離 %.6f 重なり %.6f / 頭管 ↔ 右の中管 距離 %.6f 重なり %.6f" % (b.distance_to(left), overlap(b, left), b.distance_to(right), overlap(b, right)))
    print("2 本の中管どうし: 距離 %.4f(= ピッチ 20 − 外径 12.8 = 7.2)重なり %.6f" % (left.distance_to(right), overlap(left, right)))
    bb = b.bounding_box()
    print("頭管の端面: y=%.3f(中管の端面 y=0 と一致)" % bb.min.Y)
    allb = [b, left, right]
    xs = [s.bounding_box() for s in allb]
    print("組立の外形: x[%.2f,%.2f] y[%.2f,%.2f] z[%.2f,%.2f]" % (min(q.min.X for q in xs), max(q.max.X for q in xs), min(q.min.Y for q in xs), max(q.max.Y for q in xs), min(q.min.Z for q in xs), max(q.max.Z for q in xs)))
    print("体積(高精度): 頭管 %.2f + 中管 %.2f × 2 = %.2f" % (vol(b), vol(left), vol(b) + vol(left) + vol(right)))


if __name__ == "__main__":
    main()
