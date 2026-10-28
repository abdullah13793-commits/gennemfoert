"""Demonstration MEP model: a 3-storey Danish apartment block with a basement (IFC4), drawn the way an MEP
consultant hands it over: hollow-core decks, shafts with lightweight EI 60 walls, concrete party and stair walls,
a basement plant room, risers and branches with insulation, cable routes, and an opening (udsparing) per
penetration.

The building is fictitious. Every service configuration is planted with the result a careful adviser would reach
from ETA-21/0110 (the answer key in models/planted.json, written by hand from the ETA pages, never read by the engine).

python -m gennemfoert.model  ->  models/blok_c_vvs.ifc, models/planted.json
"""
import json
import uuid
from pathlib import Path

import ifcopenshell.api as api

from . import ifcw
from .ifcw import box_solid, cyl_solid, element

ROOT = Path(__file__).resolve().parents[2]
SLAB = 0.22
LEVELS = [("Kælder", -3.0), ("Stueetage", 0.0), ("1. sal", 3.0), ("2. sal", 6.0)]
TOP = 9.0

# Service configurations: geometry/material + what the ETA says (hand-derived answer key)
SERVICES = {
    "afl110_34": dict(cls="IfcPipeSegment", name="Faldstamme PVC-U 110x3,4", mat="PVC-U", od=110, wall=3.4, sys="Afløb"),
    "afl110_32": dict(cls="IfcPipeSegment", name="Faldstamme PVC-U 110x3,2", mat="PVC-U", od=110, wall=3.2, sys="Afløb"),
    "pp75": dict(cls="IfcPipeSegment", name="Faldstamme PP 75x2,6", mat="PP", od=75, wall=2.6, sys="Afløb"),
    "kv22_kaiflex": dict(cls="IfcPipeSegment", name="Brugsvand koldt Cu 22x1,0", mat="Kobber", od=22, wall=1.0, sys="Brugsvand koldt",
                         ins=("Kaiflex ST", 0.013, "elastomer")),
    "kv22_armaflex": dict(cls="IfcPipeSegment", name="Brugsvand koldt Cu 22x1,0", mat="Kobber", od=22, wall=1.0, sys="Brugsvand koldt",
                          ins=("Armaflex AF", 0.013, "elastomer")),
    "vv28_stenuld": dict(cls="IfcPipeSegment", name="Brugsvand varmt Cu 28x1,0", mat="Kobber", od=28, wall=1.0, sys="Brugsvand varmt",
                         ins=("Stenuld rørskål 80 kg/m³", 0.030, "stenuld")),
    "vb42_stenuld": dict(cls="IfcPipeSegment", name="Varmestreng stål 42,4x2,6", mat="Stål", od=42.4, wall=2.6, sys="Varme",
                         ins=("Stenuld rørskål 80 kg/m³", 0.030, "stenuld")),
    "pp50": dict(cls="IfcPipeSegment", name="Afløbsgren PP 50x1,8", mat="PP", od=50, wall=1.8, sys="Afløb"),
    "kv15_kaiflex": dict(cls="IfcPipeSegment", name="Brugsvand koldt Cu 15x1,0", mat="Kobber", od=15, wall=1.0, sys="Brugsvand koldt",
                         ins=("Kaiflex ST", 0.009, "elastomer")),
    "vb28_stenuld": dict(cls="IfcPipeSegment", name="Radiatorgren stål 26,9x2,3", mat="Stål", od=26.9, wall=2.3, sys="Varme",
                         ins=("Stenuld rørskål 80 kg/m³", 0.020, "stenuld")),
    "kanal160": dict(cls="IfcDuctSegment", name="Ventilationskanal Ø160", mat="Galvaniseret stål", od=160, wall=0.6, sys="Ventilation"),
    "uden_data": dict(cls="IfcPipeSegment", name="Brugsvand rør (ukendt)", mat=None, od=22, wall=None, sys="Brugsvand koldt"),
    "kabelbundt": dict(cls="IfcCableSegment", name="Kabelbundt (kabler ≤ 16 mm)", mat="Kabler", od=80, cable=16, sys="El"),
    "kabel90": dict(cls="IfcCableSegment", name="Hovedkabel Ø90", mat="Kabel", od=90, cable=90, sys="El"),
    "kabelbakke": dict(cls="IfcCableCarrierSegment", name="Kabelbakke stål 200x60", mat="Stål", w=200, h=60, sys="El"),
    "vb60_stenuld": dict(cls="IfcPipeSegment", name="Varmehovedledning stål 60,3x2,9", mat="Stål", od=60.3, wall=2.9, sys="Varme",
                         ins=("Stenuld rørskål 80 kg/m³", 0.030, "stenuld")),
    "vb89_stenuld": dict(cls="IfcPipeSegment", name="Varmehovedledning stål 88,9x3,2", mat="Stål", od=88.9, wall=3.2, sys="Varme",
                         ins=("Stenuld rørskål 80 kg/m³", 0.050, "stenuld")),
    "pe160": dict(cls="IfcPipeSegment", name="Kloakledning PE 160x6,2", mat="PE", od=160, wall=6.2, sys="Afløb"),
    "pvc200": dict(cls="IfcPipeSegment", name="Kloakledning PVC-U 200x5,9", mat="PVC-U", od=200, wall=5.9, sys="Afløb"),
    "alupex16": dict(cls="IfcPipeSegment", name="Gulvvarme Alupex 16x2,25", mat="Alupex (PEX-AL-PEX)", od=16, wall=2.25, sys="Varme",
                     ins=("Stenuld rørskål 80 kg/m³", 0.020, "stenuld")),
    "pvc32": dict(cls="IfcPipeSegment", name="Kondensafløb PVC-U 32x1,8", mat="PVC-U", od=32, wall=1.8, sys="Afløb"),
}

# Answer key per (service, host kind): status and, for deviations, the parameter(s) that deviate
EXPECT = {
    ("afl110_34", "floor"): dict(status="TESTET", sections=["A.4.5"]),
    ("afl110_32", "floor"): dict(status="AFVIGELSE", deviates=["godstykkelse"]),
    ("pp75", "floor"): dict(status="IKKE_DAEKKET"),
    ("kv22_kaiflex", "floor"): dict(status="TESTET", sections=["A.4.8"]),
    ("kv22_armaflex", "floor"): dict(status="AFVIGELSE", deviates=["isoleringsfabrikat"]),
    ("vv28_stenuld", "floor"): dict(status="AFVIGELSE", alternative="A.4.8"),
    ("vb42_stenuld", "floor"): dict(status="TESTET", sections=["A.4.3", "A.4.4.1", "A.4.4.2"]),
    ("pp50", "shaft"): dict(status="AFVIGELSE", deviates=["diameter"]),
    ("kv15_kaiflex", "shaft"): dict(status="TESTET", sections=["A.1.6.2"]),
    ("vb28_stenuld", "shaft"): dict(status="AFVIGELSE", deviates=["diameter"]),
    ("kanal160", "shaft"): dict(status="ANDET_SYSTEM"),
    ("uden_data", "shaft"): dict(status="MANGLER_DATA"),
    ("kabelbundt", "stair"): dict(status="TESTET"),
    ("kabel90", "stair"): dict(status="AFVIGELSE", deviates=["diameter"]),
    ("kabelbakke", "party"): dict(status="TESTET"),
    ("afl110_34", "party"): dict(status="TESTET", sections=["A.3.5"]),
    ("vb60_stenuld", "plant"): dict(status="TESTET"),
    ("vb89_stenuld", "plant"): dict(status="TESTET", sections=["A.3.4"]),
    ("pe160", "plant"): dict(status="TESTET", sections=["A.3.5"]),
    ("pvc200", "plant"): dict(status="AFVIGELSE", deviates=["diameter"]),
    ("alupex16", "plant"): dict(status="TESTET", sections=["A.3.3.1"]),
    ("pvc32", "storage"): dict(status="TESTET", sections=["A.2.1"]),
    ("kabelbakke", "party_close"): dict(status="AFVIGELSE", deviates=["afstand mellem tætninger"]),
    ("kabelbundt", "party_close"): dict(status="AFVIGELSE", deviates=["afstand mellem tætninger"]),
}

SYSTEMS = {"Afløb": "DRAINAGE", "Brugsvand koldt": "DOMESTICCOLDWATER", "Brugsvand varmt": "DOMESTICHOTWATER",
           "Varme": "HEATING", "Ventilation": "VENTILATION", "El": "ELECTRICAL"}


class B:
    def __init__(self):
        ifcw._materials.clear()
        self.f, self.project, _ = ifcw.new_file("Blok C, Etageboliger (demonstration)")
        f = self.f
        self.site = element(f, "IfcSite", "Grund", container=self.project)
        self.bldg = element(f, "IfcBuilding", "Blok C (demonstration)", container=self.site,
                            psets={"Pset_BuildingCommon": {"NumberOfStoreys": 3}})
        self.st = {}
        for n, z in LEVELS:
            s = element(f, "IfcBuildingStorey", n, container=self.bldg)
            s.Elevation = z
            self.st[n] = s
        self.systems = {}
        for n, t in SYSTEMS.items():
            s = api.run("system.add_system", f, ifc_class="IfcDistributionSystem")
            s.Name, s.PredefinedType = n, t
            self.systems[n] = s
        self.planted = []
        self.n = 0

    def wall(self, storey, name, x0, y0, x1, y1, z0, z1, rating, mat, kind, seed=None):
        props = {"LoadBearing": mat.startswith("Beton"), "IsExternal": False}
        if rating:
            props["FireRating"] = rating
        w = element(self.f, "IfcWall", name, [box_solid(self.f, x0, y0, z0, x1, y1, z1)], self.st[storey],
                    psets={"Pset_WallCommon": props}, predefined="SOLIDWALL" if mat.startswith("Beton") else "PARTITIONING")
        ifcw.assign_material(self.f, w, mat)
        w.Description = kind
        w.GlobalId = gid(seed or f"wall/{storey}/{x0:.3f}/{y0:.3f}")
        return w

    def slab(self, storey, z, x0=0.0, x1=36.0):
        s = element(self.f, "IfcSlab", f"Huldæk 220 over {storey}", [box_solid(self.f, x0, 0, z - SLAB, x1, 12, z)],
                    self.st[storey], psets={"Pset_SlabCommon": {"FireRating": "REI 60", "LoadBearing": True}}, predefined="FLOOR")
        ifcw.assign_material(self.f, s, "Beton, huldæk 220 mm")
        s.GlobalId = gid(f"slab/{storey}")
        return s

    def service(self, key, storey, p0, axis, length, host, host_kind, center, size, tag, seed=None):
        """One straight segment through one host, with its insulation and the architect's opening."""
        f, s = self.f, SERVICES[key]
        self.n += 1
        r = s.get("od", 50) / 2000
        if s["cls"] == "IfcCableCarrierSegment":
            hw, hh = s["w"] / 2000, s["h"] / 2000
            ax = axis.index(1)
            lo = [p0[i] - (hw if i != ax and i != 2 else 0) for i in range(3)]
            hi = [p0[i] + (hw if i != ax and i != 2 else 0) for i in range(3)]
            lo[ax], hi[ax] = p0[ax], p0[ax] + length
            lo[2], hi[2] = p0[2] - hh, p0[2] + hh
            solid = box_solid(f, *lo, *hi)
            pre = "CABLETRAYSEGMENT"
        else:
            inner = None if s["cls"] == "IfcCableSegment" else (s.get("wall") or 2.0) / 1000
            solid = cyl_solid(f, p0, axis, length, r, inner if s["cls"] != "IfcDuctSegment" else 0.0006)
            pre = {"IfcPipeSegment": "RIGIDSEGMENT", "IfcDuctSegment": "RIGIDSEGMENT", "IfcCableSegment": "CABLESEGMENT"}[s["cls"]]
        el = element(f, s["cls"], f"{s['name']} ({tag})", [solid], self.st[storey], predefined=pre)
        el.GlobalId = gid(seed or f"svc/{key}/{tag}")
        if s["cls"] == "IfcPipeSegment":
            props = {"OuterDiameter": s["od"] / 1000, "NominalDiameter": s["od"] / 1000}
            if s.get("wall"):
                props["InnerDiameter"] = round((s["od"] - 2 * s["wall"]) / 1000, 5)
            ifcw.add_pset(f, el, "Pset_PipeSegmentTypeCommon", props)
        elif s["cls"] == "IfcDuctSegment":
            ifcw.add_pset(f, el, "Pset_DuctSegmentTypeCommon", {"NominalDiameterOrWidth": s["od"] / 1000})
        elif s["cls"] == "IfcCableSegment":
            ifcw.add_pset(f, el, "Pset_CableSegmentTypeCommon", {"OverallDiameter": s["cable"] / 1000})
            el.ObjectType = "Kabelbundt" if "bundt" in s["name"].lower() else "Kabel"
        else:
            ifcw.add_pset(f, el, "Pset_CableCarrierSegmentTypeCommon", {"NominalWidth": s["w"] / 1000, "NominalHeight": s["h"] / 1000})
        if s.get("mat"):
            ifcw.assign_material(f, el, s["mat"])
        api.run("system.assign_system", f, products=[el], system=self.systems[s["sys"]])
        if s.get("ins"):
            prod, t, cat = s["ins"]
            cov = element(f, "IfcCovering", f"Isolering {prod} {t * 1000:.0f} mm", [cyl_solid(f, p0, axis, length, r + t, t)],
                          self.st[storey], predefined="INSULATION")
            ifcw.layered(f, cov, prod, t, cat)
            f.createIfcRelCoversBldgElements(ifcopenshell_guid(), None, "Isolering", None, el, [cov])
        # the architect's opening in the host (udsparing), sized for a board seal
        cx, cy, cz = center
        hx, hy = size[0] / 2000, size[1] / 2000
        if host_kind == "floor":
            ifcw.opening(f, host, [box_solid(f, cx - hx, cy - hy, cz - SLAB - 0.01, cx + hx, cy + hy, cz + 0.01)])
        elif axis[0]:
            ifcw.opening(f, host, [box_solid(f, cx - 0.12, cy - hx, cz - hy, cx + 0.12, cy + hx, cz + hy)])
        else:
            ifcw.opening(f, host, [box_solid(f, cx - hx, cy - 0.12, cz - hy, cx + hx, cy + 0.12, cz + hy)])
        exp = EXPECT.get((key, host_kind), {}) if host is not None else {"status": "IKKE_BRANDADSKILLENDE"}
        self.planted.append({"service_guid": el.GlobalId, "service": el.Name, "key": key, "host": host.Name if host else None,
                             "host_guid": host.GlobalId if host else None, "host_kind": host_kind, "storey": storey, **exp})
        return el


def gid(seed):
    """Stable GlobalId from a seed, so unchanged elements keep their id across model revisions."""
    import ifcopenshell.guid
    return ifcopenshell.guid.compress(uuid.uuid5(uuid.NAMESPACE_URL, "blok-c/" + seed).hex)


def ifcopenshell_guid():
    import ifcopenshell.guid
    return ifcopenshell.guid.new()


def build(out=ROOT / "models" / "blok_c_vvs.ifc", rev="A"):
    """rev "B": the B1 stack gets 110x3.4 drains, the A2 radiator branch is replaced by a water branch, and the party wall
    on the ground floor (west) is upgraded to EI 90."""
    b = B()
    f = b.f
    slabs = {n: b.slab(n, z + 3.0) for n, z in LEVELS[:-1]}           # deck above each storey (below the next)
    slabs["2. sal"] = b.slab("2. sal", TOP)
    walls = {}
    for n, z in LEVELS:
        z0, z1 = z, z + 3.0 - SLAB
        walls[(n, "trappe_v")] = b.wall(n, "Trapperumsvæg, beton 200", 15.9, 0, 16.1, 12, z0, z1, "REI 60", "Beton", "rigid")
        walls[(n, "trappe_ø")] = b.wall(n, "Trapperumsvæg, beton 200", 19.9, 0, 20.1, 12, z0, z1, "REI 60", "Beton", "rigid")
        if n == "Kælder":
            walls[(n, "teknik")] = b.wall(n, "Teknikrumsvæg, beton 150", 11.925, 0, 12.075, 12, z0, z1, "EI 60", "Beton", "rigid")
            walls[(n, "depot")] = b.wall(n, "Depotvæg, gips på stålskelet 75", 23.9625, 0, 24.0375, 12, z0, z1, "EI 30",
                                         "Gips på stålskelet, 2x12,5 mm pr. side", "flexible")
            walls[(n, "let")] = b.wall(n, "Let skillevæg (ikke brandklassificeret)", 29.95, 0, 30.05, 12, z0, z1, None,
                                       "Gips på stålskelet", "flexible")
        else:
            party = "EI 90" if rev == "B" and n == "Stueetage" else "EI 60"
            walls[(n, "lejl_v")] = b.wall(n, "Lejlighedsskel, beton 180", 7.91, 0, 8.09, 12, z0, z1, party, "Beton", "rigid")
            walls[(n, "lejl_ø")] = b.wall(n, "Lejlighedsskel, beton 180", 27.91, 0, 28.09, 12, z0, z1, "EI 60", "Beton", "rigid")
        # shaft walls (north face of each shaft, where the branches leave)
        for sx, tag in ((6.2, "A1"), (9.8, "A2"), (26.2, "B1"), (29.8, "B2")):
            walls[(n, "skakt", tag)] = b.wall(n, f"Skaktvæg {tag}, gips på stålskelet 100", sx - 0.6, 6.4, sx + 0.6, 6.5, z0, z1, "EI 60",
                                             "Gips på stålskelet, 2x12,5 mm pr. side", "flexible")

    # risers through every deck, per shaft
    stacks = {"A1": (6.2, ["afl110_34", "kv22_kaiflex", "vb42_stenuld"]),
              "A2": (9.8, ["afl110_34", "kv22_kaiflex", "vb42_stenuld"]),
              "B1": (26.2, ["afl110_34" if rev == "B" else "afl110_32", "kv22_armaflex", "vv28_stenuld"]),
              "B2": (29.8, ["pp75", "kv22_kaiflex", "vb42_stenuld"])}
    for tag, (sx, keys) in stacks.items():
        for k, key in enumerate(keys):
            x, y = sx - 0.45 + 0.45 * k, 6.0
            for n, z in LEVELS[:-1]:
                top = z + 3.0
                b.service(key, n, (x, y, z + 0.05), (0, 0, 1), 3.05, slabs[n], "floor", (x, y, top), (220, 220), f"{tag}, dæk over {n}",
                          seed=f"stack/{tag}/{k}/{n}")
    # branches through the shaft walls (north, +y)
    branches = {"A1": [("pp50", LEVELS[1:]), ("kv15_kaiflex", LEVELS[1:])],
                "A2": [("kv15_kaiflex" if rev == "B" else "vb28_stenuld", LEVELS[1:2]), ("kanal160", LEVELS[1:2])],
                "B1": [("kv15_kaiflex", LEVELS[2:3]), ("uden_data", LEVELS[2:3])]}
    for tag, items in branches.items():
        sx = dict((t, v[0]) for t, v in stacks.items())[tag]
        for k, (key, levels) in enumerate(items):
            x = sx - 0.25 + 0.5 * k
            for n, z in levels:
                zc = z + 2.3
                b.service(key, n, (x, 6.0, zc), (0, 1, 0), 3.0, walls[(n, "skakt", tag)], "shaft", (x, 6.45, zc), (240, 240), f"skakt {tag}, {n}")
    # cables through the stair wall, a tray and a drain through the party wall
    b.service("kabelbundt", "Stueetage", (14.5, 2.0, 2.4), (1, 0, 0), 3.0, walls[("Stueetage", "trappe_v")], "stair", (16.0, 2.0, 2.4), (200, 200), "trapperum, stue")
    b.service("kabel90", "1. sal", (14.5, 2.0, 5.4), (1, 0, 0), 3.0, walls[("1. sal", "trappe_v")], "stair", (16.0, 2.0, 5.4), (200, 200), "trapperum, 1. sal")
    b.service("kabelbakke", "Stueetage", (6.5, 3.0, 2.5), (1, 0, 0), 3.0, walls[("Stueetage", "lejl_v")], "party", (8.0, 3.0, 2.5), (320, 180), "lejlighedsskel, stue")
    b.service("afl110_34", "Stueetage", (6.5, 9.0, 0.4), (1, 0, 0), 3.0, walls[("Stueetage", "lejl_v")], "party", (8.0, 9.0, 0.4), (220, 220), "lejlighedsskel, stue")
    # two seals too close together (120 mm between the openings) on 2. sal
    b.service("kabelbakke", "2. sal", (26.5, 3.0, 8.5), (1, 0, 0), 3.0, walls[("2. sal", "lejl_ø")], "party_close", (28.0, 3.0, 8.5), (320, 180), "lejlighedsskel, 2. sal")
    b.service("kabelbundt", "2. sal", (26.5, 3.0 + 0.16 + 0.12 + 0.10, 8.5), (1, 0, 0), 3.0, walls[("2. sal", "lejl_ø")], "party_close",
              (28.0, 3.0 + 0.16 + 0.12 + 0.10, 8.5), (200, 200), "lejlighedsskel, 2. sal")
    # basement: plant-room wall, storage wall, and one crossing of an unrated partition
    for k, key in enumerate(["vb60_stenuld", "vb89_stenuld", "pe160", "pvc200", "alupex16"]):
        y = 1.5 + 1.8 * k
        size = {"pe160": (300, 300), "pvc200": (340, 340)}.get(key, (260, 260))
        b.service(key, "Kælder", (6.0, y, -0.9), (1, 0, 0), 9.5, walls[("Kælder", "teknik")], "plant", (12.0, y, -0.9), size, "teknikrum")
    b.service("pvc32", "Kælder", (22.0, 8.0, -0.6), (1, 0, 0), 3.5, walls[("Kælder", "depot")], "storage", (24.0, 8.0, -0.6), (160, 160), "depot")
    b.service("pvc32", "Kælder", (28.5, 8.0, -0.6), (1, 0, 0), 2.5, walls[("Kælder", "let")], "unrated", (30.0, 8.0, -0.6), (160, 160), "let væg")
    b.planted[-1].update(status="IKKE_BRANDADSKILLENDE")
    out.parent.mkdir(parents=True, exist_ok=True)
    f.write(str(out))
    (out.parent / ("planted.json" if rev == "A" else f"planted_rev{rev}.json")).write_text(json.dumps(b.planted, indent=1, ensure_ascii=False), encoding="utf-8")
    return f, b.planted


if __name__ == "__main__":
    f, planted = build()
    from collections import Counter
    print(len(planted), "penetrations planted;", Counter(p.get("status") for p in planted))
