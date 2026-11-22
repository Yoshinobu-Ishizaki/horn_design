# /// script
# requires-python = ">=3.10"
# dependencies = ["build123d>=0.13", "ocp_vscode>=4", "numpy"]
# ///
"""検査治具を build123d で設計するときに繰り返し使う関数集。

作業フォルダの show スクリプトから `import jig_toolkit as jt`(このファイルを作業フォルダにコピーするか、
sys.path に追加)して使う。単位は mm。

構成:
  1. 形状の調べ方: 円筒・円錐のパラメータ、断面の円、エッジと平面の交点
  2. 形を作る部品: 軸方向の円柱(穴あけ・ボルト・受け)、円錐台の切り出し、平面での切り落とし
  3. 文字: 大文字の高さで指定する左揃えの複数行テキスト
  4. 検証: 重なり、当たり面の被覆、下向きの面(アンダーカット)
  5. ビューアーと出力: カメラを変えない表示、画面の PNG 保存、名前つきアセンブリの STEP

どの関数も、今回(bb106_mpbrc)の設計で使って数値を確かめたもの。使い方の例は
references/example_bb106_show_jig.py を参照。
"""

from __future__ import annotations

import math
import time
from pathlib import Path

import numpy as np
from build123d import (
    Align,
    Color,
    Compound,
    Cone,
    Cylinder,
    Keep,
    Location,
    Plane,
    Pos,
    Text,
    Vector,
    export_step,
    split,
)
from OCP.BRepAdaptor import BRepAdaptor_Surface

# ---------------------------------------------------------------- 1. 形状の調べ方


def cylinder_params(face) -> dict:
    """円筒面の半径、軸の向き(単位ベクトル)、軸上の1点。"""
    c = BRepAdaptor_Surface(face.wrapped).Cylinder()
    a, p = c.Axis().Direction(), c.Location()
    return {
        "radius": c.Radius(),
        "axis": Vector(a.X(), a.Y(), a.Z()),
        "point": Vector(p.X(), p.Y(), p.Z()),
    }


def cone_params(face) -> dict:
    """円錐面の頂点、軸の向き、半頂角[rad]、基準半径。半径は頂点から軸方向に s だけ進むと s*tan(半頂角)。"""
    c = BRepAdaptor_Surface(face.wrapped).Cone()
    a, apex = c.Axis().Direction(), c.Apex()
    return {
        "apex": Vector(apex.X(), apex.Y(), apex.Z()),
        "axis": Vector(a.X(), a.Y(), a.Z()),
        "semi_angle": c.SemiAngle(),
        "ref_radius": c.RefRadius(),
    }


def fit_circle(points_2d: np.ndarray) -> tuple[float, float, float, float]:
    """最小二乗円。戻り値は (中心 a, 中心 b, 半径, 最大残差)。残差が 0.01 以下なら円とみなしてよい。"""
    p = np.asarray(points_2d, dtype=float)
    m = np.c_[2 * p[:, 0], 2 * p[:, 1], np.ones(len(p))]
    a, b, c = np.linalg.lstsq(m, (p**2).sum(1), rcond=None)[0]
    r = math.sqrt(c + a * a + b * b)
    return a, b, r, float(np.abs(np.hypot(p[:, 0] - a, p[:, 1] - b) - r).max())


def section_circle_xz(face, n: int = 80) -> tuple[float, float, float, float]:
    """面を XZ 平面(Y=0)で切った交線に円を当てはめる。曲げ面の中心を原点にするときに使う。"""
    sec = face.intersect(Plane.XZ)
    pts = [(v.X, v.Z) for e in sec.edges() for v in (e @ t for t in np.linspace(0, 1, n))]
    return fit_circle(np.array(pts))


def edge_plane_points(edge, plane: Plane = Plane.XZ) -> list[Vector]:
    """エッジと平面の交点(頂点)のリスト。例: 羽先端のエッジと XZ 平面の交点。"""
    inter = edge.intersect(plane)
    return [] if inter is None else [Vector(v.X, v.Y, v.Z) for v in inter.vertices()]


def rotate_about_y(shape, deg_in_xz: float):
    """XZ 平面内で +X から +Z 向きを正として deg_in_xz 回す(Y 軸まわりの -deg)。"""
    from build123d import Axis

    return shape.rotate(Axis.Y, -deg_in_xz)


# ---------------------------------------------------------------- 2. 形を作る部品


def axial_cyl(origin: Vector, axis: Vector, s0: float, s1: float, dia: float):
    """origin から axis 方向に s0〜s1 の範囲の円柱。穴あけ、座ぐり、ボルト、受けの円柱に使う。"""
    mid = origin + axis * ((s0 + s1) / 2)
    return Location(Plane(origin=mid, z_dir=axis)) * Cylinder(dia / 2, s1 - s0)


def embed_start_s(point_on_axis: Vector, axis: Vector, radius: float, surface_z: float, embed: float) -> float:
    """傾いた円柱の下端の軸方向位置 s(point_on_axis からの距離)。

    下端の円板は傾くので、円板のいちばん浅い点(最高点)が surface_z から embed 以上深くなる位置にする。
    axis は +Z 向きに上がるもの。"""
    tilt_sin = math.sqrt(1 - axis.Z**2)
    return (surface_z - embed - radius * tilt_sin - point_on_axis.Z) / axis.Z


def cone_frustum(cone: dict, s0: float, s1: float):
    """円錐面と同軸・同じ半頂角の円錐台。頂点から軸方向に s0〜s1(s は頂点からの距離)。軸側が実体。"""
    t = math.tan(cone["semi_angle"])
    origin = cone["apex"] + cone["axis"] * s0
    return Location(Plane(origin=origin, z_dir=cone["axis"])) * Cone(
        s0 * t, s1 * t, s1 - s0, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )


def keep_side(shape, point: Vector, normal: Vector):
    """point を通り normal を法線とする平面で切って、normal 側を残す。"""
    return split(shape, Plane(origin=point, z_dir=normal), keep=Keep.TOP)


def cone_tangent(cone: dict, point: Vector, toward: Vector) -> Vector:
    """円錐面上の point での円周方向の接線(単位ベクトル)。toward の側を向ける。

    point を通り円錐面に直交する平面は、法線と軸方向を含む平面、つまりこの接線を法線とする平面。"""
    ax = cone["axis"].normalized()
    r = point - cone["apex"]
    radial = (r - ax * r.dot(ax)).normalized()
    tangent = ax.cross(radial).normalized()
    return tangent if (toward - point).dot(tangent) >= 0 else -tangent


# ---------------------------------------------------------------- 3. 文字


def cap_ratio(font: str) -> float:
    """font_size に対する大文字の高さの比(フォントごとに違うので実測する)。"""
    return Text("B", 10, font=font).bounding_box().size.Y / 10


def left_aligned_text(text: str, cap_height: float, font: str, center_xy: tuple[float, float], z: float = 0.0):
    """大文字の高さで指定する複数行の文字(厚さ0の面の Compound)。2行目以降を1行目の左端に揃える。

    build123d の Text は行ごとに中央揃えで並ぶので、各行を1行目の左端に合わせて動かす。
    z は文字を置く面の高さ。上から読める向き。"""
    size = cap_height / cap_ratio(font)
    faces = list((Pos(center_xy[0], center_xy[1], 0) * Text(text, size, font=font)).faces())
    ys = sorted({round(f.center().Y, 1) for f in faces}, reverse=True)
    # 行の分け目: 面の中心の Y を大きくクラスタに分ける(行間 > 文字の高さの半分)
    centers = sorted((f.center().Y for f in faces), reverse=True)
    cuts = [(a + b) / 2 for a, b in zip(centers, centers[1:]) if a - b > cap_height * 0.5]
    lines: list[list] = [[] for _ in range(len(cuts) + 1)]
    for f in faces:
        lines[sum(f.center().Y < c for c in cuts)].append(f)
    left0 = min(f.bounding_box().min.X for f in lines[0])
    out = list(lines[0])
    for ln in lines[1:]:
        dx = left0 - min(f.bounding_box().min.X for f in ln)
        out += [Pos(dx, 0, 0) * f for f in ln]
    return Plane.XY.offset(z) * Compound(out)


# ---------------------------------------------------------------- 4. 検証


def overlap_volume(a, b) -> float:
    """2つのソリッドの重なりの体積。0 に近ければ干渉なし(接するだけ)。"""
    inter = a & b
    return float(inter.volume) if inter is not None else 0.0


def bbox_overhang(part, holder, tol: float = 1e-6) -> dict[str, float]:
    """part の外接箱が holder の外接箱から出ている量(mm)。出ている側だけを {"+Z": 3.0, ...} で返す(空なら収まっている)。

    干渉の確認(overlap_volume)は、板から飛び出した部品には反応しない(重なりが 0 でも出ている)。
    ボルト・ピン・市販のセットが、相手の板の厚さの範囲に収まるかは、これで別に確かめる。
    意図して出す部分(ボルトの頭、ポストの先端など)は、呼び出し側で除いて判断する。"""
    bp, bh = part.bounding_box(), holder.bounding_box()
    sides = {
        "-X": bh.min.X - bp.min.X, "+X": bp.max.X - bh.max.X,
        "-Y": bh.min.Y - bp.min.Y, "+Y": bp.max.Y - bh.max.Y,
        "-Z": bh.min.Z - bp.min.Z, "+Z": bp.max.Z - bh.max.Z,
    }
    return {k: v for k, v in sides.items() if v > tol}


def uncovered_points(support, face, depth: float = 0.05, tol: float = 0.2) -> tuple[int, int]:
    """製品の面(face)の点が、受け(support)の中に入っているか。(入っていない点の数, 全点数)。

    face の法線の側に受けの実体がある向き(面が軸の側へへこんでいる受け)で、面から法線方向へ depth だけ
    入った点を調べる。受けの当たり面が面取りや穴で欠けていないかの確認。"""
    verts, _ = face.tessellate(tol)
    bad = 0
    for q in verts:
        p = Vector(q.X, q.Y, q.Z)
        n = face.normal_at(p)
        if not support.is_inside(p + n * depth):
            bad += 1
    return bad, len(verts)


def downward_area(face, tol: float = 0.02, min_nz: float = -1e-6) -> float:
    """面のうち、外向き法線の Z 成分が min_nz より小さい(下を向く)部分の面積。

    真上から見て影になる部分(アンダーカット)の確認。底面は当然下向きなので、底以外の面で見る。"""
    verts, tris = face.tessellate(tol, 0.1)
    p = np.array([(q.X, q.Y, q.Z) for q in verts])
    area = 0.0
    for t in tris:
        a, b, c = p[list(t)]
        m = (a + b + c) / 3
        if face.normal_at(Vector(*m)).Z < min_nz:
            area += np.linalg.norm(np.cross(b - a, c - a)) / 2
    return area


def is_single_valid_solid(shape) -> bool:
    return shape.is_valid and len(shape.solids()) == 1


# ---------------------------------------------------------------- 5. ビューアーと出力


def show_parts(parts: list[tuple], keep_camera: bool = True, transparent: bool = True) -> None:
    """ビューアーに部品を表示する。parts は (shape, 名前, 色, alpha) のリスト。

    カメラは既定で変えない(更新のたびにユーザーが回した視点が ISO に戻るのを防ぐ)。"""
    from ocp_vscode import Camera, set_defaults

    # ocp_vscode.show と同じ。表示した形を記録し、ID から引けるようにする
    from bope_claude_cad.viewer import show

    set_defaults(
        reset_camera=Camera.KEEP if keep_camera else Camera.ISO,
        axes=True,
        axes0=True,
        transparent=transparent,
    )
    show(
        *(p[0] for p in parts),
        names=[p[1] for p in parts],
        colors=[p[2] for p in parts],
        alphas=[p[3] for p in parts],
    )


def save_view_png(path: str | Path, wait: float = 4.0) -> Path:
    """ビューアーの今の画面を PNG に保存する(向きは今のまま)。事前にビューアーを開いておくこと。"""
    from ocp_vscode import save_screenshot

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    time.sleep(wait)  # 描画待ち
    save_screenshot(str(path))
    return path


def export_assembly_step(parts: list[tuple], path: str | Path, label: str = "ASSY") -> Path:
    """名前・色つきのアセンブリを STEP に出す。parts は (shape, 名前, 色)。

    子として持たせる(children=)ので、読み直しても名前と色が残る。"""
    kids = []
    for shape, name, color in parts:
        shape.label = name
        shape.color = Color(color)
        kids.append(shape)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    export_step(Compound(label=label, children=kids), str(path))
    return path
