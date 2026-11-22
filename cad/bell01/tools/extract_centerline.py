"""bell_01.FCStd のスケッチ CenterPath(ベルの芯線)を DXF に書き出す。

FCStd は zip なので、FreeCAD を使わずに中の `Sketch.Shape.brp` を build123d で読む。
直線と円弧は DXF の LINE・ARC のまま出す(折れ線にしない)。

    uv run python cad/bell01/tools/extract_centerline.py
    uv run python cad/bell01/tools/extract_centerline.py <in.FCStd> <out.dxf>
"""

from __future__ import annotations

import math
import re
import sys
import tempfile
import zipfile
from pathlib import Path

import ezdxf
from build123d import GeomType, import_brep

HERE = Path(__file__).resolve().parent.parent
LABEL = "CenterPath"


def sketch_name(doc_xml: str, label: str) -> str:
    """Label からオブジェクト名(brp のファイル名)を引く。"""
    for m in re.finditer(r'<Object name="([^"]+)"[^>]*>(.*?)</Object>', doc_xml, re.S):
        if re.search(rf'<Property name="Label"[^>]*>\s*<String value="{re.escape(label)}"', m.group(2)):
            return m.group(1)
    raise KeyError(f"label {label!r} not found")


def load_centerline(fcstd: Path):
    with zipfile.ZipFile(fcstd) as z, tempfile.TemporaryDirectory() as td:
        name = sketch_name(z.read("Document.xml").decode("utf-8"), LABEL)
        brp = Path(td) / f"{name}.Shape.brp"
        brp.write_bytes(z.read(f"{name}.Shape.brp"))
        return import_brep(str(brp))


def write_dxf(shape, out: Path) -> None:
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    wire = shape.wires()[0]
    for e in wire.order_edges():
        p0, p1 = e.start_point(), e.end_point()
        if abs(p0.Z) > 1e-9 or abs(p1.Z) > 1e-9:
            raise ValueError("centerline is not in the XY plane")
        if e.geom_type == GeomType.LINE:
            msp.add_line((p0.X, p0.Y), (p1.X, p1.Y))
        elif e.geom_type == GeomType.CIRCLE:
            c, r = e.arc_center, e.radius
            a0 = math.degrees(math.atan2(p0.Y - c.Y, p0.X - c.X))
            a1 = math.degrees(math.atan2(p1.Y - c.Y, p1.X - c.X))
            pm = e.position_at(0.5)
            ccw = (p0 - c).cross(pm - c).Z > 0
            # DXF の ARC は反時計回りなので、時計回りの円弧は始点と終点を入れ替える
            msp.add_arc((c.X, c.Y), r, a0, a1) if ccw else msp.add_arc((c.X, c.Y), r, a1, a0)
        else:
            raise ValueError(f"unsupported edge type {e.geom_type}")
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out)


def main(argv: list[str]) -> None:
    src = Path(argv[1]) if len(argv) > 1 else HERE / "bell_01.FCStd"
    out = Path(argv[2]) if len(argv) > 2 else HERE / "bell01-ctr.dxf"
    shape = load_centerline(src)
    write_dxf(shape, out)
    print(f"{out}: {len(shape.edges())} edges, length {sum(e.length for e in shape.edges()):.3f} mm")


if __name__ == "__main__":
    main(sys.argv)
