"""bell01 の芯線(直線 + 時計回りの円弧)を寸法から作り、DXF に書き出す。

始点 (0,0)(リム側)から +Y へ直線 STRAIGHT、続けて ARCS の円弧を時計回りにつなぐ。
最後の円弧の角度は、全長が TOTAL になるように決める(メンズールの終点 D=16.125 を変えないため)。
寸法は、RefBell ベルの全体の比率(高さ・幅・終点の位置と向き)に近づくように当てはめ、丸めた値。

    uv run python cad/bell01/tools/make_centerline.py [out.dxf]
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import ezdxf

WD = Path(__file__).resolve().parent.parent
TOTAL = 840.635  # 芯線の全長 (mm)。FreeCAD の bell_01 と同じ
STRAIGHT = 240.0
ARCS = [(215.0, 15.0), (145.0, 49.0), (150.0, 114.0), (130.0, None)]  # (R, 角度 deg)。None は全長から決める


def arcs_resolved() -> list[tuple[float, float]]:
    used = STRAIGHT + sum(r * math.radians(a) for r, a in ARCS if a is not None)
    out = []
    for r, a in ARCS:
        out.append((r, a if a is not None else math.degrees((TOTAL - used) / r)))
    return out


def write_dxf(out: Path) -> None:
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    x, y, h = 0.0, STRAIGHT, 90.0  # 現在の点と進む向き (deg)
    msp.add_line((0, 0), (x, y))
    for r, sweep in arcs_resolved():
        hr = math.radians(h)
        cx, cy = x + r * math.sin(hr), y - r * math.cos(hr)  # 時計回り: 中心は進む向きの右
        a0 = math.degrees(math.atan2(y - cy, x - cx))
        a1 = a0 - sweep
        msp.add_arc((cx, cy), r, a1, a0)  # DXF の ARC は反時計回りなので、終点側から始点側へ
        x, y = cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1))
        h -= sweep
        print(f"R{r:.0f} sweep {sweep:.3f} deg -> ({x:.3f}, {y:.3f}) dir {h:.2f}")
    doc.saveas(out)
    print(f"{out}: total {TOTAL}")


if __name__ == "__main__":
    write_dxf(Path(sys.argv[1]) if len(sys.argv) > 1 else WD / "bell01-ctr.dxf")
