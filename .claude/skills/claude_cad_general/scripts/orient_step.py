# /// script
# requires-python = ">=3.10"
# dependencies = ["build123d>=0.13", "numpy"]
# ///
"""製品の STEP を、検査治具の座標系(上=Z+、右=X+、Y は紙面の奥)に回転・平行移動して書き出す。

回転は XZ 平面内で +X から +Z 向きを正とした角度 deg(Y 軸まわりの -deg)。
原点は次のどちらかで決める。
  --origin-circle-face N   面 N を回転後に XZ 平面(Y=0)で切った交線の最小二乗円の中心(曲げ面の中心など)
  --origin X Y Z           回転後の座標で指定した点
いずれも指定しなければ、回転後の外形の最小値を原点にする(仮置き)。

使い方:
  uv run orient_step.py <step> <deg> <out.step> <out.json> [--origin-circle-face N | --origin X Y Z]
                        [--axis-face N ...]   円筒面 N の軸を回転後の座標で out.json に記録する(複数可)

置き方向の候補は、まず deg をいくつか試して probe_step.py や OCP Viewer で見比べて決める。
out.json は、ほかのスクリプト(受けの設計)が読む。回転後の座標をその場で測るので、手計算の座標変換は不要。
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np
from build123d import Axis, Plane, Pos, export_step, import_step

sys.path.insert(0, __import__("pathlib").Path(__file__).parent.as_posix())
import jig_toolkit as jt  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step")
    ap.add_argument("deg", type=float)
    ap.add_argument("out_step")
    ap.add_argument("out_json")
    ap.add_argument("--origin-circle-face", type=int, default=None)
    ap.add_argument("--origin", type=float, nargs=3, default=None)
    ap.add_argument("--axis-face", type=int, action="append", default=[])
    a = ap.parse_args()

    shape = import_step(a.step)
    rotated = shape.rotate(Axis.Y, -a.deg)
    info: dict = {"rotate_deg_in_XZ": a.deg}

    if a.origin_circle_face is not None:
        xc, zc, rad, res = jt.section_circle_xz(rotated.faces()[a.origin_circle_face])
        shift = (-float(xc), 0.0, -float(zc))
        info["origin_note"] = f"面 F{a.origin_circle_face:02d} の Y=0 断面の円の中心(XZ)、Y=0"
        info["origin_circle_radius"] = round(rad, 3)
        info["origin_circle_residual"] = round(res, 4)
        if res > 0.05:
            print(f"警告: 断面が円とみなせない(残差 {res:.3f})。原点の決め方を見直すこと", file=sys.stderr)
    elif a.origin is not None:
        shift = (-a.origin[0], -a.origin[1], -a.origin[2])
        info["origin_note"] = f"回転後の座標 {a.origin} を原点にした"
    else:
        bb = rotated.bounding_box()
        shift = (-bb.min.X, -bb.min.Y, -bb.min.Z)
        info["origin_note"] = "仮置き: 回転後の外形の最小値を原点にした"
    info["shift"] = [float(v) for v in shift]

    oriented = Pos(*shift) * rotated
    export_step(oriented, a.out_step)
    bb = oriented.bounding_box()
    info["bbox_min"] = [round(v, 3) for v in bb.min]
    info["bbox_max"] = [round(v, 3) for v in bb.max]
    faces = oriented.faces()
    axes = {}
    for n in a.axis_face:
        p = jt.cylinder_params(faces[n])
        axes[f"F{n:02d}"] = {
            "radius": round(p["radius"], 3),
            "direction": [round(v, 4) for v in p["axis"]],
            "point": [round(v, 3) for v in p["point"]],
        }
    if axes:
        info["axes"] = axes
    json.dump(info, open(a.out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
