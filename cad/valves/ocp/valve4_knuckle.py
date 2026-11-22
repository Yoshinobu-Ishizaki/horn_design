"""第 4 植込の 1 階・第 1 側(-x 側)の孔(225° の孔)に差し込む、捻じった枝管。

折れ角は切りよく θ=52°(捻じり角 ψ は端数)。2 条件(下)は θ=52° では同時には満たせないので、keep で優先を選ぶ。
条件: 枝管を孔軸まわりに ψ 回し、折れ角 θ で曲がった先の出口側の軸が
  ・XY 平面への投影が (0, -1)(= -Y 方向)
  ・YZ 平面への投影で、-Y から +Z 方向へ TILT = 30° 傾く
となる θ と ψ。

局所: 1 本目 +X(孔軸)、折れ面は局所 XY(2 本目 u2 = (cosθ, sinθ, 0))、ψ は局所 X(孔軸)まわりの回転(+Y → +Z 側)。
  u2' = (cosθ, sinθ cosψ, sinθ sinψ)
ワールドへ: 局所 X → d1 = (cos(HOLE_ANGLE), sin(HOLE_ANGLE), 0)、局所 Y → (-sin, cos) = (s, -s, 0)(225° のとき)、局所 Z → Z。
  x = s(-cosθ + sinθ cosψ), y = s(-cosθ - sinθ cosψ), z = sinθ sinψ   (s = 1/√2)
x = 0 → tanθ cosψ = 1。z/(-y) = tan(TILT) → tan²θ = 1 + 2 tan²(TILT)(TILT=30° で 5/3)。
"""

import math

from build123d import Pos, Rot

from knuckle import knuckle

HOLE_ANGLE = 225.0  # ワールドの角度。第 4 の 1 階で、第 1 側に残っている孔
Z_F1 = 17.0  # 1 階(F 階)の孔軸の高さ(ワールド)
from valve_row import VALVE4_X as X_VALVE4  # 第 4 植込の中心 x(70)
TILT = 30.0  # YZ 投影で +Z に傾ける角度


EXIT_X_OFFSET = 11.0  # 出口側の軸の x を、第 4 中心から -11 にする(切りのよい値)。曲げ内側の境界線がケース外面 R13 に触れる位置は 10.9703(抜き量 1.3722)なので、そのわずかに外側
PULL_OUT = EXIT_X_OFFSET * math.sqrt(2) - 10 * math.sqrt(2)  # = √2 ≈ 1.4142。出口側の軸(XY 投影 (0,-1) の方向)の x が、第 4 中心から -EXIT_X_OFFSET になるように、孔軸に沿って抜く量
THETA = 52.0  # 折れ角(切りのよい値にする。捻じり角 ψ は端数でよい)
KEEP = "xy"  # 条件が 2 つ(XY 投影 (0,-1) と YZ 傾き 30°)で ψ しか自由がないので、どちらを厳密に守るか: "xy" / "tilt"


def solve_for_tilt(tilt_deg: float = TILT):
    """θ と ψ の両方を解く(2 条件を同時に満たす)。tan²θ = 1 + 2 tan²(tilt)。TILT=30° で θ=52.2388°、ψ=39.2315°。"""
    t2 = math.tan(math.radians(tilt_deg)) ** 2
    theta = math.atan(math.sqrt(1 + 2 * t2))
    psi = math.acos(1 / math.tan(theta))
    return math.degrees(theta), math.degrees(psi)


def solve(theta_deg: float = THETA, keep: str = KEEP):
    """折れ角 θ を決めて、捻じり角 ψ を求める。戻り値 (θ, ψ, YZ 傾き, XY 投影の -Y からのずれ) [deg]。
    keep="xy": XY 投影を (0,-1) に厳密に合わせる(cosψ = cotθ)。YZ 傾きは 30° からずれる(θ=52° で 29.46°)。
    keep="tilt": YZ 傾きを TILT に厳密に合わせる。XY 投影が -Y からずれる(θ=52° で 0.31°)。"""
    th = math.radians(theta_deg)
    if keep == "xy":
        psi = math.degrees(math.acos(1 / math.tan(th)))
    else:
        lo, hi = 0.0, 90.0
        for _ in range(80):
            m = (lo + hi) / 2
            u = exit_axis_world(theta_deg, m)
            if math.degrees(math.atan2(u[2], -u[1])) < TILT:
                lo = m
            else:
                hi = m
        psi = lo
    u = exit_axis_world(theta_deg, psi)
    return theta_deg, psi, math.degrees(math.atan2(u[2], -u[1])), math.degrees(math.atan2(u[1], u[0])) + 90.0


def exit_axis_world(theta_deg: float, psi_deg: float, hole_angle: float = HOLE_ANGLE):
    """出口側の軸の向き(ワールドの単位ベクトル)。"""
    th, ps, a = (math.radians(v) for v in (theta_deg, psi_deg, hole_angle))
    d1 = (math.cos(a), math.sin(a))
    d2 = (-math.sin(a), math.cos(a))  # 局所 Y
    lx, ly, lz = math.cos(th), math.sin(th) * math.cos(ps), math.sin(th) * math.sin(ps)
    return (lx * d1[0] + ly * d2[0], lx * d1[1] + ly * d2[1], lz)


def twisted_knuckle(theta=None, psi=None, pull=PULL_OUT):
    """pull: 孔軸に沿って外へ抜く量(0 なら FreeCAD の枝管と同じ差し込み位置。ケースと干渉する)。"""
    th, ps = solve()[:2] if theta is None else (theta, psi)
    return Pos(X_VALVE4, 0, Z_F1) * Rot(0, 0, HOLE_ANGLE) * Pos(pull, 0, 0) * Rot(ps, 0, 0) * knuckle(th)


# 第 4 の 2 階(B 階、z=34)の左側(第 1 側)の孔 135° に、45° の枝管を差し込み、第 1 の枝管とつなぐ。
Z_F2 = 34.0
CONNECT_ANGLE = 135.0  # 1 本目の方向。折れは反時計回りに 45° → 2 本目は -X 向き(135° + 45° = 180°)
CONNECT_PULL = 0.0  # FreeCAD の枝管と同じ差し込み位置。2 本目の端面が x = 70 - 17.5 = 52.5 で、第 1 の枝管の端面(35 + 17.5)と突き合う


def connect_knuckle(pull: float = CONNECT_PULL):
    """第 4 の 2 階・135° の孔の 45° 枝管。"""
    return Pos(X_VALVE4, 0, Z_F2) * Rot(0, 0, CONNECT_ANGLE) * Pos(pull, 0, 0) * knuckle(45.0)


def main():
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show
    from valve_row import build_row

    th, ps, tilt, xy_dev = solve()
    u = exit_axis_world(th, ps)
    print(f"θ = {th:.4f}°, ψ = {ps:.4f}°(keep={KEEP})  YZ 傾き {tilt:.4f}°  XY 投影の -Y からのずれ {xy_dev:+.4f}°")
    print(f"出口側の軸 = ({u[0]:+.6f}, {u[1]:+.6f}, {u[2]:+.6f})  XY 投影の方向 = ({u[0]:+.6f}, {u[1]:+.6f})")
    print(f"YZ 投影の傾き(-Y から +Z)= {math.degrees(math.atan2(u[2], -u[1])):.4f}°")
    row = build_row()
    parts, names = [], []
    for vname, (case, ks, nms) in row.items():
        parts += [case] + ks
        names += [f"{vname}_case"] + nms
    parts += [twisted_knuckle(th, ps), connect_knuckle()]
    names += ["valve4_knuckle_F1_225_twisted", "valve4_knuckle_F2_135_45deg"]
    show(*parts, names=names, reset_camera=Camera.KEEP)


if __name__ == "__main__":
    main()
