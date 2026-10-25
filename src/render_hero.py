"""Blender (Cycles) signature render: the demonstration block with storeys pulled apart, fire-separating walls and
decks as tinted glass, the MEP risers and branches in system colours, and every penetration seal as a glowing
ring in its register status. Run:
  blender -b -P src/render_hero.py -- [out.png] [samples] [width] [height]
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else str(ROOT / "renders" / "hero.png")
SAMPLES = int(argv[1]) if len(argv) > 1 else 96
W = int(argv[2]) if len(argv) > 2 else 1600
H = int(argv[3]) if len(argv) > 3 else 1200
LIFT = {"K": 0.0, "ST": 2.6, "1": 5.2, "2": 7.8}
CODE = {"Kælder": "K", "Stueetage": "ST", "1. sal": "1", "2. sal": "2"}
REG = json.load(open(ROOT / "web" / "data" / "register.json", encoding="utf-8"))


def lin(h):
    h = h.lstrip("#")
    s = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in s]


STATUS = {"TESTET": "#22c55e", "AFVIGELSE": "#f0a020", "IKKE_DAEKKET": "#ef4444", "ANDET_SYSTEM": "#7c8cf0", "MANGLER_DATA": "#c4c9d1"}
SYS = {"DRAINAGE": "#a8957a", "DOMESTICCOLDWATER": "#3b82f6", "DOMESTICHOTWATER": "#ef4444", "HEATING": "#f97316",
       "VENTILATION": "#b8bec8", "ELECTRICAL": "#eab308"}

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(ROOT / "web" / "building.glb"))
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
fix = Matrix.Rotation(-math.pi / 2, 4, "X")       # file holds IFC Z-up; the importer assumes Y-up
bpy.context.view_layer.update()
world = {o: o.matrix_world.copy() for o in objs}
for o in objs:
    o.parent = None
    o.matrix_world = fix @ world[o]
bpy.context.view_layer.update()


def principled(name, rgb, alpha=1.0, rough=0.5, emit=0.0, transmission=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Alpha"].default_value = alpha
    if transmission:
        b.inputs["Transmission Weight"].default_value = transmission
    if emit:
        b.inputs["Emission Color"].default_value = (*rgb, 1)
        b.inputs["Emission Strength"].default_value = emit
    return m


mats = {
    "rigid_r": principled("rigid", lin("#d9915c"), alpha=0.22, rough=0.35),
    "light_r": principled("light", lin("#7fa8e0"), alpha=0.22, rough=0.35),
    "slab_r": principled("slab", lin("#8a94a8"), alpha=0.16, rough=0.25),
    "rigid_n": principled("unrated", lin("#5a6170"), alpha=0.06, rough=0.6),
    "light_n": principled("unrated2", lin("#5a6170"), alpha=0.06, rough=0.6),
    "ins": principled("ins", lin("#f3efe6"), alpha=0.5, rough=0.9),
}
for o in objs:
    nm = o.name.split(".")[0]
    parts = nm.split("_")
    code = parts[1] if len(parts) > 1 else "K"
    o.location.z += LIFT.get(code, 0)
    o.data.materials.clear()
    if nm.startswith("H_"):
        o.data.materials.append(mats["_".join(parts[2:4])] if "_".join(parts[2:4]) in mats else mats["rigid_n"])
        o.visible_shadow = False
    elif nm.startswith("I_"):
        o.data.materials.append(mats["ins"])
        o.visible_shadow = False
    else:
        sysn = "_".join(parts[2:])
        o.data.materials.append(principled(f"sys_{sysn}", lin(SYS.get(sysn, "#999999")), rough=0.4, emit=0.6))
bpy.context.view_layer.update()

# status rings at every penetration
for p in REG:
    x, y, z = p["point"]
    z += LIFT[CODE[p["storey"]]]
    a = p["aperture"] or [200, 200]
    r = max(a) / 2000 * 1.7
    bpy.ops.mesh.primitive_torus_add(major_radius=r, minor_radius=r * 0.2, location=(x, y, z), major_segments=48, minor_segments=12)
    t = bpy.context.object
    if p["host"]["kind"] != "rigid_floor":
        t.rotation_euler = (0, math.pi / 2, 0) if p["host"]["axis"] == 0 else (math.pi / 2, 0, 0)
    strength = 9 if p["status"] == "TESTET" else 16
    t.data.materials.append(principled(f"st_{p['id']}", lin(STATUS[p["status"]]), rough=0.3, emit=strength))
    t.visible_shadow = False

# floor plates per storey (dark, glossy) to anchor the exploded levels
plate = principled("plate", (0.03, 0.035, 0.045), rough=0.22)
for code, dz in LIFT.items():
    z = {"K": -3.0, "ST": 0.0, "1": 3.0, "2": 6.0}[code] + dz - 0.05
    bpy.ops.mesh.primitive_cube_add(size=1, location=(18, 6, z - 0.25))
    pl = bpy.context.object
    pl.scale = (40, 16, 0.1)
    pl.data.materials.append(plate)
    pl.hide_render = code != "K"

allbb = [o.matrix_world @ Vector(v) for o in bpy.context.scene.objects if o.type == "MESH" and not o.hide_render for v in o.bound_box]
cen = Vector([(min(v[i] for v in allbb) + max(v[i] for v in allbb)) / 2 for i in range(3)])
size = max(max(v[i] for v in allbb) - min(v[i] for v in allbb) for i in range(3))
cam_data = bpy.data.cameras.new("cam")
cam_data.lens = 40
cam = bpy.data.objects.new("cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
cam.location = cen + Vector((-0.58, -1.0, 0.56)) * size * 1.08
cam.rotation_euler = (cen + Vector((0, 0, -1.0)) - cam.location).to_track_quat("-Z", "Y").to_euler()
bpy.context.scene.camera = cam
key = bpy.data.lights.new("key", "AREA")
key.energy, key.size, key.color = 5200, 30, (0.78, 0.84, 1.0)
ko = bpy.data.objects.new("key", key)
bpy.context.scene.collection.objects.link(ko)
ko.location = cen + Vector((-20, -18, 40))
ko.rotation_euler = (cen - ko.location).to_track_quat("-Z", "Y").to_euler()
rim = bpy.data.lights.new("rim", "AREA")
rim.energy, rim.size, rim.color = 2200, 20, (1.0, 0.8, 0.6)
ro = bpy.data.objects.new("rim", rim)
bpy.context.scene.collection.objects.link(ro)
ro.location = cen + Vector((30, 25, 18))
ro.rotation_euler = (cen - ro.location).to_track_quat("-Z", "Y").to_euler()
w = bpy.data.worlds.new("w")
bpy.context.scene.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.006, 0.007, 0.011, 1)
sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.cycles.device = "CPU"
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Medium High Contrast"
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("rendered", OUT)
