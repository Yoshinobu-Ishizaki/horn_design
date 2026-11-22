"""Show the variable-section bell and its centerline in OCP Viewer.

Usage: uv run python skills/claude_cad_vss/scripts/show_bell.py DXF [--ds 3]
"""

import argparse
import sys
from pathlib import Path

import ezdxf
from ocp_vscode import Camera, StudioBackground, StudioEnvironment, StudioToneMapping

sys.path.insert(0, str(Path(__file__).parent))
from bell_from_dxf import build_centerline, read_table

from bope_claude_cad.viewer import show, visibility
from bope_claude_cad.vss import variable_pipe_law, variable_pipe_wall

ap = argparse.ArgumentParser()
ap.add_argument("dxf")
ap.add_argument("--hide-centerline", action="store_true", help="hide the centerline after showing")
ap.add_argument("--wall", type=float, default=0.0, help="wall thickness (mm) added outward; 0 = surface only")
a = ap.parse_args()

msp = ezdxf.readfile(a.dxf).modelspace()
L, D = read_table(msp)
cl = build_centerline(msp)
if a.wall > 0:
    solid, prof = variable_pipe_wall(cl, L, D, a.wall)
else:
    solid, prof = variable_pipe_law(cl, L, D)
show(
    solid,
    cl,
    names=["bell_bore", "centerline"],
    # lacquered brass: sampled from the open bell flare of a French horn photo (hue ~51, sat ~0.5)
    colors=["#cf9f30", "red"],
    alphas=[1.0, 1.0],
    reset_camera=Camera.KEEP,
    # shiny metal: Studio tab (environment reflections), full metalness, low roughness
    tab="studio",
    metalness=1.0,
    roughness=0.02,
    studio_environment=StudioEnvironment.HIGH_CONTRAST_STUDIO,
    studio_tone_mapping=StudioToneMapping.NEUTRAL,
    studio_exposure=0.8,
    studio_background=StudioBackground.GRADIENT_DARK,
)
if a.hide_centerline:
    visibility("hide", ["centerline"])
print("shown: faces", len(solid.faces()), "area", round(solid.area))
