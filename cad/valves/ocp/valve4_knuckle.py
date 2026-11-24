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

from build123d import Plane, Pos, Rot

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


def twisted_knuckle(theta=None, psi=None, pull=PULL_OUT, z=Z_F1):
    """pull: 孔軸に沿って外へ抜く量(0 なら FreeCAD の枝管と同じ差し込み位置。ケースと干渉する)。z: 孔軸の高さ(1 階 17、2 階 34)。"""
    th, ps = solve()[:2] if theta is None else (theta, psi)
    return Pos(X_VALVE4, 0, z) * Rot(0, 0, HOLE_ANGLE) * Pos(pull, 0, 0) * Rot(ps, 0, 0) * knuckle(th)


# 第 4 の 2 階(B 階、z=34)の左側(第 1 側)の孔 135° に、45° の枝管を差し込み、第 1 の枝管とつなぐ。
Z_F2 = 34.0
CONNECT_ANGLE = 135.0  # 1 本目の方向。折れは反時計回りに 45° → 2 本目は -X 向き(135° + 45° = 180°)
CONNECT_PULL = 0.0  # FreeCAD の枝管と同じ差し込み位置。2 本目の端面が x = 70 - 17.5 = 52.5 で、第 1 の枝管の端面(35 + 17.5)と突き合う


# 第 4 の 2 階・左下の孔(225°)の枝管。1 階の真下の枝管と同じ折れ角 52°(ねじった枝管)。
# 隣接する第 1 の枝管(L1_225)との表面距離は 12.2 - 出口の x オフセット。0.8 以上にするため、出口の x を第 4 中心から 0.5 刻みの -11 にする(距離 1.2)。
# 折れの内側の境界線が R13 に触れない限界の抜き量が √2(オフセット 11)以下になる折れ角は θ ≤ 約 52.3°(53° は 1.491 で足りない)。
# なお折れ角 60°(YZ 傾き 45°)では、限界の抜き量 2.2371(オフセット 11.58)で表面距離が 0.618 にしかならなかった。
# 2026-11-24: 抜き量を 2.5 に(kp1 の位置が変わるので、θ・ψ は kp1 から bb34 の直管へ向けて解き直す = solve_2f)。
# 抜き量ごとの曲げ内側の境界線のケース軸からの最小距離(R13 以上で干渉なし)、θ、第 1 の L1_225 との表面距離(= 12.2 - 出口の x オフセット):
#   1.414: 12.30(食い込み)・58.86°・1.200 / 2.2: 13.02(限界)・59.43°・0.644 / 2.5: 13.29・59.66°・0.43 / **2.943: θ = 60.000°** / 3.0: 13.75・60.04°(60° 超)・0.079
# 限界ぎりぎりにせず、0.3 の余裕を持たせる(再計算で角度が変わっても食い込まない)。
PULL_OUT_2F = 1.95  # bb34 の U をピッチ 46 にしたので θ は約 54° に下がり、抜き量を減らせた(2026-11-24)。ケース内側の境界線の余裕 約 0.3、第 1 の L1_225 との距離 約 0.8。履歴: √2 → 2.5 → 2.942968(θ 60°)→ 1.95
EXIT_X_OFFSET_2F = (PULL_OUT_2F + 10.0 * math.sqrt(2)) / math.sqrt(2)  # kp1 の第 4 中心からの -x(= 出口の軸の x オフセット)
THETA_2F = None  # solve_2f() で決まる

# 2026-11-24 再設計: 折れ点 kp1(= 第 4 中心から 225° 方向へ PULL_OUT_2F + D1 の点、z=34)から、
# YZ に投影したとき、bb34 の直管(U の浮いている端 y = 10 - √(46² - 15²) = -33.486、z = 49)の中心へ向かう方向に、出口の軸を向ける(抜き量を変えると kp1 が動くので、θ・ψ は solve_2f() で解き直す)
# (XY 投影 (0,-1) も保つ → 折れ角 θ と捻じり角 ψ が両方決まる)。折れ角 60° までは許容。
BB34_PITCH, BB34_RISE = 46.0, 15.0  # bb34_u.PITCH / RISE と同じにする
BB34_STRAIGHT_YZ = (10.0 - math.sqrt(BB34_PITCH**2 - BB34_RISE**2), 49.0)  # bb34 の直管の中心の (y, z)


def kp1_2f():
    """2 階左下の枝管の折れ点(ワールド)。"""
    from knuckle import D1

    s = PULL_OUT_2F + D1
    a = math.radians(HOLE_ANGLE)
    return (X_VALVE4 + s * math.cos(a), s * math.sin(a), Z_F2)


def tilt_2f():
    """kp1 から bb34 の直管の中心へ向かう方向の、-Y からの YZ 傾き [deg]。"""
    _, y, z = kp1_2f()
    return math.degrees(math.atan2(BB34_STRAIGHT_YZ[1] - z, y - BB34_STRAIGHT_YZ[0]))


def solve_2f():
    """(θ, ψ) [deg]。XY 投影 (0,-1) と YZ 傾き tilt_2f() を同時に満たす。"""
    return solve_for_tilt(tilt_2f())


def twisted_knuckle_2f():
    th, ps = solve_2f()
    return twisted_knuckle(th, ps, PULL_OUT_2F, Z_F2)


def connect_knuckle(z: float = Z_F2, pull: float = CONNECT_PULL):
    """第 4 の左の孔(135°)の 45° 枝管。z=34(2 階)または z=17(1 階)。第 1 の枝管の端面と突き合う。"""
    return Pos(X_VALVE4, 0, z) * Rot(0, 0, CONNECT_ANGLE) * Pos(pull, 0, 0) * knuckle(45.0)


def knuckle_2f_right(pull: float = CONNECT_PULL):
    """第 4 の 2 階・右下の孔(315°、+x,-y)の 45° 枝管。1 本目 315°、折れは反時計回りに 45° → 2 本目は +X 向き(315° + 45° = 360°)。
    差し込み位置は FreeCAD の枝管と同じ(抜き量 0)。端面は x = 70 + 17.5 = 87.5、y = -10。"""
    return Pos(X_VALVE4, 0, Z_F2) * Rot(0, 0, 315.0) * Pos(pull, 0, 0) * knuckle(45.0)


def knuckle_2f_upper_right(pull: float = CONNECT_PULL):
    """第 4 の 2 階・右上の孔(45°、+x,+y)の 45° 枝管。1 本目 45°、折れは時計回りに 45° → 2 本目は +X 向き(45° - 45° = 0°)。
    knuckle() は反時計回り(+Y 側)に折れるので、1 本目の軸(局所 X)まわりに 180° 回して時計回りにする。"""
    return Pos(X_VALVE4, 0, Z_F2) * Rot(0, 0, 45.0) * Pos(pull, 0, 0) * Rot(180, 0, 0) * knuckle(45.0)


def knuckle_1f_lower_right(pull: float = CONNECT_PULL):
    """第 4 の 1 階・右下の孔(315°、+x,-y)の 45° 枝管。1 本目 315°、折れは反時計回りに 45° → 2 本目は +X 向き(315° + 45° = 0°)。出口の端面 (x+17.5, -10, 17)。
    (2026-11-24 ユーザー指示: 出口を +X に向ける。以前は時計回りに折れて -Y 向き(knuckle_1f_lower_right_down、2026-11-23))"""
    return Pos(X_VALVE4, 0, Z_F1) * Rot(0, 0, 315.0) * Pos(pull, 0, 0) * knuckle(45.0)


def mirrored_twisted_knuckle():
    """第 4 の 1 階・右下の孔(315°、+x,-y)の枝管。左下の孔(225°)のねじった枝管(twisted_knuckle)を、
    第 4 の中心を通る YZ 平面(x = X_VALVE4)で鏡映したもの。1 本目 315°、出口側の軸の XY 投影は同じ (0,-1)、
    YZ 傾きも同じ(+Z 側)、出口側の x は第 4 中心から +11(左下は -11)。"""
    return twisted_knuckle().mirror(Plane.YZ.offset(X_VALVE4))


def mirrored_twisted_knuckle_2f():
    """第 4 の 2 階・右下の孔(315°、+x,-y)の枝管(2026-11-24、knuckle_2f_right の 45° 枝管から置き換え。2番管も外した)。
    1 階左下(v4-f1-225)と同じねじった枝管(折れ角 THETA = 52°、ψ は solve()、抜き量 PULL_OUT = √2)を 2 階(z = Z_F2)の 225° に置き、
    第 4 の中心を通る YZ 平面(x = X_VALVE4)で鏡映したもの(2026-11-24。最初は 2 階左下 twisted_knuckle_2f の鏡像だった)。"""
    return twisted_knuckle(None, None, PULL_OUT, Z_F2).mirror(Plane.YZ.offset(X_VALVE4))


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
    parts += [twisted_knuckle(th, ps), knuckle_2f_upper_right(), connect_knuckle(Z_F1), knuckle_1f_lower_right(), twisted_knuckle_2f(), mirrored_twisted_knuckle_2f()]
    names += ["valve4_knuckle_F1_225_twisted", "valve4_knuckle_F2_45_45deg_plusx", "valve4_knuckle_F1_135_45deg", "valve4_knuckle_F1_315_45deg_plusx", "valve4_knuckle_F2_225_twisted", "valve4_knuckle_F2_315_twisted_mirror"]
    show(*parts, names=names, reset_camera=Camera.KEEP)


if __name__ == "__main__":
    main()
