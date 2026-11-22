"""Show two 3D-centerline examples (helix, line + 2 arcs in different planes) in OCP Viewer.

Usage: uv run python skills/claude_cad_vss/scripts/show_3d_examples.py [--hide-centerline]
Toggle later without re-sending:
  uv run python -m bope_claude_cad.viewer hide helix_centerline bent3d_centerline
  uv run python -m bope_claude_cad.viewer all
"""

import argparse
import math

import numpy as np
from build123d import Edge, Helix, Line, ThreePointArc, Vector, Wire
from ocp_vscode import Camera

from bope_claude_cad.viewer import show, visibility
from bope_claude_cad.vss import variable_pipe_law

ap = argparse.ArgumentParser()
ap.add_argument("--hide-centerline", action="store_true", help="hide the centerlines after showing")
args = ap.parse_args()

# 1. helix R=100, pitch 150, 2 turns
h = Helix(pitch=150, height=300, radius=100)
helix = Wire([h]) if isinstance(h, Edge) else h.wire()

# 2. straight + two quarter arcs in different planes (tangent continuous, non-planar), shifted in X
r = 100.0
k = r * math.cos(math.radians(45))
dx = Vector(400, 0, 0)
c1, c2 = Vector(0, 100, 100) + dx, Vector(100, 100, 200) + dx
bent = Wire(
    [
        Line(Vector(0, 0, 0) + dx, Vector(0, 0, 100) + dx),
        ThreePointArc(Vector(0, 0, 100) + dx, c1 + Vector(0, -k, k), Vector(0, 100, 200) + dx),
        ThreePointArc(Vector(0, 100, 200) + dx, c2 + Vector(-k, k, 0), Vector(100, 200, 200) + dx),
    ]
)


def pipe(cl, d0, d1):
    ls = np.linspace(0, cl.length, 25)
    ds = np.linspace(d0, d1, 25) + 3 * np.sin(ls / cl.length * 3 * math.pi)
    return variable_pipe_law(cl, ls, ds)[0]


show(
    pipe(helix, 40, 20),
    helix,
    pipe(bent, 40, 24),
    bent,
    names=["helix_pipe", "helix_centerline", "bent3d_pipe", "bent3d_centerline"],
    colors=["lightsteelblue", "red", "lightsteelblue", "red"],
    alphas=[0.6, 1.0, 0.6, 1.0],
    reset_camera=Camera.KEEP,
)
if args.hide_centerline:
    visibility("hide", ["helix_centerline", "bent3d_centerline"])
print("shown")
