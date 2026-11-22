"""bell01 を RefBell ベル(claude_cad_vss のサンプル)と比べる。

RefBell は社内図面なので、結果(数値・画像)は output/bell01/compare_refbell/(git 管理外)にだけ出す。

    uv run python cad/bell01/tools/compare_refbell.py [--show]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import ezdxf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / ".claude/skills/claude_cad_vss/scripts"))
sys.path.insert(0, str(ROOT / "cad/bell01/ocp"))
from bell01_surface import CTR_DXF, LD_CSV, read_centerline, read_ld  # noqa: E402
from bell_from_dxf import build_centerline, read_table  # noqa: E402

from bope_claude_cad.vss import fit_profile, variable_pipe_law  # noqa: E402

HR_DXF = ROOT / "jigs/*_seat/input/refbell_bell_assy.dxf"
OUT = ROOT / "output/bell01/compare_refbell"


def outline(cl, prof, n=600):
    """芯線の平面(XY)での、内径の左右の輪郭線。"""
    ls = np.linspace(0, prof.l_end, n)
    pts, left, right = [], [], []
    for s in ls:
        u = s / cl.length
        p, t = cl.position_at(u), cl.tangent_at(u)
        nx, ny = -t.Y, t.X
        r = float(prof(s)) / 2
        pts.append((p.X, p.Y))
        left.append((p.X + r * nx, p.Y + r * ny))
        right.append((p.X - r * nx, p.Y - r * ny))
    return np.array(pts), np.array(left), np.array(right)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    cl_b = read_centerline(CTR_DXF)
    L_b, D_b = read_ld(LD_CSV)
    prof_b = fit_profile(L_b, D_b, cl_b.length)

    msp = ezdxf.readfile(HR_DXF).modelspace()
    L_h, D_h = read_table(msp)
    cl_h = build_centerline(msp)
    prof_h = fit_profile(L_h, D_h, cl_h.length)

    lines = [
        f"bell01 : centerline {cl_b.length:.3f}, D {float(prof_b(0)):.3f} -> {float(prof_b(prof_b.l_end)):.3f}",
        f"RefBell  : centerline {cl_h.length:.3f}, D {float(prof_h(0)):.3f} -> {float(prof_h(prof_h.l_end)):.3f}"
        f", table rows {len(L_h)}",
        "",
        "segments (bell01):",
        *[f"  {e.geom_type.name:6s} len {e.length:8.3f}" + (f" R{e.radius:.1f}" if e.geom_type.name == "CIRCLE" else "")
          for e in cl_b.edges()],
        "segments (RefBell):",
        *[f"  {e.geom_type.name:6s} len {e.length:8.3f}" + (f" R{e.radius:.1f}" if e.geom_type.name == "CIRCLE" else "")
          for e in cl_h.edges()],
        "",
        "    L   D_bell01   D_RefBell   diff",
    ]
    lmax = min(prof_b.l_end, prof_h.l_end)
    for s in [0, 5, 10, 20, 30, 50, 75, 100, 120, 150, 200, 250, 300, 400, 500, 600, 700, 800, lmax]:
        db, dh = float(prof_b(s)), float(prof_h(s))
        lines.append(f"{s:7.1f} {db:9.3f} {dh:9.3f} {db - dh:+8.3f}")
    bb_b = cl_b.bounding_box()
    bb_h = cl_h.bounding_box()
    lines += ["", f"centerline bbox bell01 x {bb_b.min.X:.1f}..{bb_b.max.X:.1f} y {bb_b.min.Y:.1f}..{bb_b.max.Y:.1f}",
              f"centerline bbox RefBell  x {bb_h.min.X:.1f}..{bb_h.max.X:.1f} y {bb_h.min.Y:.1f}..{bb_h.max.Y:.1f}"]
    report = "\n".join(lines)
    (OUT / "compare.txt").write_text(report + "\n", encoding="utf-8")
    print(report)

    fig, ax = plt.subplots(1, 3, figsize=(18, 6))
    g = np.linspace(0, max(prof_b.l_end, prof_h.l_end), 2000)
    ax[0].plot(g[g <= prof_b.l_end], prof_b(g[g <= prof_b.l_end]), label="bell01")
    ax[0].plot(g[g <= prof_h.l_end], prof_h(g[g <= prof_h.l_end]), label="RefBell")
    ax[0].set_xlabel("L (mm)"), ax[0].set_ylabel("D (mm)"), ax[0].set_yscale("log"), ax[0].legend(), ax[0].grid(True, which="both")
    gg = np.linspace(0, lmax, 2000)
    ax[1].plot(gg, prof_b(gg) - prof_h(gg))
    ax[1].set_xlabel("L (mm)"), ax[1].set_ylabel("D_bell01 - D_RefBell (mm)"), ax[1].grid(True)
    ax[1].set_ylim(-20, 20)
    for cl, prof, name in [(cl_b, prof_b, "bell01"), (cl_h, prof_h, "RefBell")]:
        c, lft, rgt = outline(cl, prof)
        (ln,) = ax[2].plot(c[:, 0], c[:, 1], "--", lw=0.8, label=f"{name} centerline")
        ax[2].plot(lft[:, 0], lft[:, 1], color=ln.get_color(), lw=1.2)
        ax[2].plot(rgt[:, 0], rgt[:, 1], color=ln.get_color(), lw=1.2)
    ax[2].set_aspect("equal"), ax[2].grid(True), ax[2].legend()
    ax[2].set_title("bore outline in the centerline plane")
    fig.tight_layout()
    fig.savefig(OUT / "compare.png", dpi=110)
    print(f"-> {OUT}")

    if a.show:
        from ocp_vscode import Camera

        from bope_claude_cad.viewer import show

        bore_b, _ = variable_pipe_law(cl_b, L_b, D_b)
        bore_h, _ = variable_pipe_law(cl_h, L_h, D_h)
        show(bore_b, cl_b, bore_h, cl_h,
             names=["bell01_bore", "bell01_centerline", "refbell_bore", "refbell_centerline"],
             colors=["#cf9f30", "red", "#6080c0", "blue"], alphas=[0.6, 1.0, 0.6, 1.0],
             reset_camera=Camera.KEEP)


if __name__ == "__main__":
    main()
