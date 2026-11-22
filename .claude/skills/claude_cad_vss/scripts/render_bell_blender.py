"""Render the bell STL realistically with Blender (Cycles).

Usage:
  blender -b -P render_bell_blender.py -- STL OUT.png [--samples 128] [--cloth black|enji|navy|green|purple] [--res 1600 1200]
STL is in mm; it is scaled to metres. Lacquered brass, studio softboxes, glossy floor.
"""

import math
import sys
import time

import bpy
from mathutils import Matrix, Vector, noise

argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
stl, out = argv[0], argv[1]
samples = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 128
res = (1600, 1200)
# cloth colour presets: (base colour, sheen tint), linear RGB
CLOTHS = {
    "enji": ((0.045, 0.011, 0.012), (0.36, 0.09, 0.09)),
    "navy": ((0.010, 0.020, 0.075), (0.05, 0.12, 0.45)),
    "green": ((0.008, 0.065, 0.028), (0.05, 0.35, 0.15)),
    "purple": ((0.050, 0.010, 0.080), (0.25, 0.08, 0.42)),
    "black": ((0.012, 0.012, 0.014), (0.12, 0.12, 0.14)),
}
cloth_name = argv[argv.index("--cloth") + 1] if "--cloth" in argv else "black"
cloth_base, cloth_sheen = CLOTHS[cloth_name]
if "--res" in argv:
    i = argv.index("--res")
    res = (int(argv[i + 1]), int(argv[i + 2]))

T0 = time.time()


def tick(msg):
    print(f"[t={time.time() - T0:.1f}s] {msg}", flush=True)


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# --- model
bpy.ops.wm.stl_import(filepath=stl)
obj = bpy.context.selected_objects[0]
obj.data.transform(Matrix.Scale(0.001, 4))  # mm -> m (stl_import global_scale is not reliable in Blender 5)
bpy.ops.object.shade_smooth()
# STL has split vertices: merge so smooth shading works; keep sharp edges at real creases
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=1e-6)
bpy.ops.object.mode_set(mode="OBJECT")
try:
    bpy.ops.object.shade_auto_smooth(angle=math.radians(40))
except Exception:
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))

# --- rest pose: tilt so the lowest point (bell rim) and the far end of the tube share the table plane
mesh = obj.data
for _ in range(6):
    vs = [v.co.copy() for v in mesh.vertices]
    p1 = min(vs, key=lambda v: v.z)
    p2 = max(vs, key=lambda v: (v - p1).length)
    v = p2 - p1
    vh = Vector((v.x, v.y, 0))
    if vh.length < 1e-9:
        break
    vh.normalize()
    ang = math.atan2(v.z, Vector((v.x, v.y, 0)).length)
    mesh.transform(Matrix.Rotation(ang, 4, Vector((0, 0, 1)).cross(vh)))
vs = [v.co for v in mesh.vertices]
lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
size = (hi - lo).length
# xy-centre, sink 2 mm into the cloth (cloth top is z = 0)
obj.location = Vector((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z - 0.001))
look_at = Vector((0.0, 0.0, 0.0))

tick(f"rest pose done, verts={len(mesh.vertices)} size={size} lo={tuple(lo)} hi={tuple(hi)}")
# --- lacquered brass material (base metal + clear coat)
mat = bpy.data.materials.new("brass")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.80, 0.50, 0.13, 1)
bsdf.inputs["Metallic"].default_value = 1.0
bsdf.inputs["Roughness"].default_value = 0.2
bsdf.inputs["Coat Weight"].default_value = 1.0
bsdf.inputs["Coat Roughness"].default_value = 0.02
obj.data.materials.append(mat)

# --- table covered with crimson velvet: flat top, rounded edge, hanging sides with folds
hx, hy = 0.85 * size, 0.62 * size  # table top half-size: just big enough for the bell
hang, rad, step = 0.7 * size, 0.04 * size, 0.006
bx, by = (hi.x - lo.x) / 2, (hi.y - lo.y) / 2
nx, ny = int(2 * (hx + hang) / step), int(2 * (hy + hang) / step)
ex, ey = hx + hang, hy + hang
tick(f"grid {nx} x {ny}")


def drape(t, h):
    """Distance t beyond the table edge -> (outward offset, drop)."""
    if t <= 0:
        return 0.0, 0.0
    a = min(t / rad, math.pi / 2)
    out, drop = rad * math.sin(a), rad * (1 - math.cos(a))
    if t > rad * math.pi / 2:
        drop += t - rad * math.pi / 2
    return out, drop


verts, faces = [], []
for j in range(ny + 1):
    y0 = -ey + 2 * ey * j / ny
    for i in range(nx + 1):
        x0 = -ex + 2 * ex * i / nx
        tx, ty = abs(x0) - hx, abs(y0) - hy
        ox, dx = drape(tx, hx)
        oy, dy = drape(ty, hy)
        x = math.copysign(min(abs(x0), hx) + ox, x0) if tx > 0 else x0
        y = math.copysign(min(abs(y0), hy) + oy, y0) if ty > 0 else y0
        z = -(dx + dy)
        # folds: organ-pleat folds on the hanging parts, creases and soft wrinkles on top
        fold = min(max(dx, dy) / (0.12 * size), 1.0)
        if tx > 0:
            ph = y0 / size * 20 + 2.5 * noise.noise(Vector((y0 * 2, 0, 1)))
            x += math.copysign(1, x0) * size * fold * (0.045 * math.sin(ph) + 0.015 * math.sin(2.3 * ph + 1))
        if ty > 0:
            ph = x0 / size * 20 + 2.5 * noise.noise(Vector((x0 * 2, 1, 0)))
            y += math.copysign(1, y0) * size * fold * (0.045 * math.sin(ph) + 0.015 * math.sin(2.3 * ph + 1))
        q = math.hypot(x0 / bx, y0 / by)
        free = min(max((q - 1.05) / 0.7, 0.0), 1.0)  # near the bell: folds may dip down but never rise into it
        top = 1.0 - 0.7 * min(max(dx, dy) / (0.1 * size), 1.0)
        n1 = noise.noise(Vector((x0 * 3.0, y0 * 3.0, 0)))
        n2 = noise.noise(Vector((x0 * 5.5 + n1, y0 * 5.5 - n1, 3)))
        ridge = (1.0 - abs(n2)) ** 3 - 0.3  # sharp crests = creases
        wr = 0.026 * n1 + 0.04 * ridge + 0.004 * noise.noise(Vector((x0 * 16, y0 * 16, 5)))
        if wr > 0:
            wr *= free  # upward bumps only away from the bell
        else:
            wr *= 0.4 + 0.6 * free
        z += top * wr
        verts.append((x, y, z))
for j in range(ny):
    for i in range(nx):
        k = j * (nx + 1) + i
        faces.append((k, k + 1, k + nx + 2, k + nx + 1))
tick(f"cloth verts built {len(verts)}")
cm = bpy.data.meshes.new("cloth")
cm.from_pydata(verts, [], faces)
cm.update()
cloth = bpy.data.objects.new("cloth", cm)
scene.collection.objects.link(cloth)
bpy.context.view_layer.objects.active = cloth
cloth.select_set(True)
bpy.ops.object.shade_smooth()
vm = bpy.data.materials.new("velvet")
vm.use_nodes = True
vn = vm.node_tree
vb = vn.nodes["Principled BSDF"]
vb.inputs["Base Color"].default_value = (*cloth_base, 1)
vb.inputs["Roughness"].default_value = 0.6
vb.inputs["Sheen Weight"].default_value = 0.4
vb.inputs["Sheen Roughness"].default_value = 0.35
vb.inputs["Specular IOR Level"].default_value = 0.02
vb.inputs["Sheen Tint"].default_value = (*cloth_sheen, 1)
nz = vn.nodes.new("ShaderNodeTexNoise")
nz.inputs["Scale"].default_value = 900
nz.inputs["Detail"].default_value = 6
bp = vn.nodes.new("ShaderNodeBump")
bp.inputs["Strength"].default_value = 0.08
bp.inputs["Distance"].default_value = 0.001
vn.links.new(nz.outputs["Fac"], bp.inputs["Height"])
vn.links.new(bp.outputs["Normal"], vb.inputs["Normal"])
cloth.data.materials.append(vm)
# brass must not mirror the dark red cloth (that makes the flare melt into it): hide the cloth from glossy rays
cloth.visible_glossy = False
# remove grid-scale teeth along the hanging edge (Laplacian smoothing keeps the broad folds)
sm = cloth.modifiers.new("smooth", "SMOOTH")
sm.factor = 0.6
sm.iterations = 12

# dark floor far below the hanging cloth
bpy.ops.mesh.primitive_plane_add(size=size * 14, location=(0, 0, -(hang + 0.35 * size)))
flr = bpy.context.active_object
fmat = bpy.data.materials.new("floor")
fmat.use_nodes = True
fbs = fmat.node_tree.nodes["Principled BSDF"]
fbs.inputs["Base Color"].default_value = (0.02, 0.015, 0.015, 1)
fbs.inputs["Roughness"].default_value = 0.5
flr.data.materials.append(fmat)

# --- world: dark gradient so brass reflects the softboxes
world = bpy.data.worlds.new("w")
world.use_nodes = True
wb = world.node_tree.nodes["Background"]
wb.inputs["Color"].default_value = (0.55, 0.50, 0.45, 1)
wb.inputs["Strength"].default_value = 0.3
scene.world = world


def softbox(name, loc, sz, energy):
    bpy.ops.object.light_add(type="AREA", location=loc)
    lt = bpy.context.active_object
    lt.name = name
    lt.data.shape = "RECTANGLE"
    lt.data.size = sz[0]
    lt.data.size_y = sz[1]
    lt.data.energy = energy
    direction = look_at - Vector(loc)
    lt.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return lt


d = size * 1.6
softbox("key", (d, -d * 0.6, d * 1.0), (size * 1.2, size * 0.8), 1800 * size**2 * 0.03)
softbox("fill", (-d * 1.2, -d * 0.4, d * 0.5), (size * 1.0, size * 1.0), 700 * size**2 * 0.03)
softbox("rim", (-d * 0.5, d * 1.3, d * 0.7), (size * 2.2, size * 0.5), 4500 * size**2 * 0.03)
softbox("top", (0, 0, d * 1.5), (size * 1.5, size * 1.5), 600 * size**2 * 0.03)
softbox("rake", (-d * 1.4, -d * 0.3, d * 0.12), (size * 1.6, size * 0.5), 3500 * size**2 * 0.03)
softbox("rake2", (d * 1.4, d * 0.4, d * 0.12), (size * 1.6, size * 0.5), 5000 * size**2 * 0.03)

# --- camera: looks mostly along -Z onto the centerline plane, tilted for depth
cam_data = bpy.data.cameras.new("cam")
cam_data.lens = 50
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
cam.location = Vector((size * 0.25, -size * 1.0, size * 1.25))
cam.rotation_euler = (look_at - cam.location).to_track_quat("-Z", "Y").to_euler()
scene.camera = cam

# --- render settings
scene.render.engine = "CYCLES"
scene.cycles.samples = samples
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 12
scene.cycles.glossy_bounces = 8
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for t in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
        try:
            prefs.compute_device_type = t
            prefs.get_devices()
            if any(dv.type != "CPU" for dv in prefs.devices):
                for dv in prefs.devices:
                    dv.use = True
                scene.cycles.device = "GPU"
                break
        except Exception:
            continue
except Exception:
    pass
scene.render.resolution_x, scene.render.resolution_y = res
scene.render.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "Khronos PBR Neutral"
scene.render.filepath = out
tick('start render')
bpy.ops.render.render(write_still=True)
tick('render done')
print("rendered:", out, "device:", scene.cycles.device)
