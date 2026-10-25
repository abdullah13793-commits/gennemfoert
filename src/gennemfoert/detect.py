"""Find every penetration of a fire-separating wall or deck in an IFC model.

A penetration is a pipe, duct, cable or cable tray whose axis passes right through a wall or slab. The fire
requirement comes from the host's FireRating (Pset_WallCommon / Pset_SlabCommon); rigid vs flexible
construction from the host's material; the aperture from the architect's opening (IfcOpeningElement) at that
spot; the service's size from its Pset; material, insulation (IfcCovering via IfcRelCoversBldgElements) and
system type (IfcDistributionSystem) from the model's relationships. Nothing is guessed: what is missing is
reported as missing.
"""
import multiprocessing
import re

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as ue
import numpy as np

SERVICES = ["IfcPipeSegment", "IfcDuctSegment", "IfcCableSegment", "IfcCableCarrierSegment"]
HOSTS = ["IfcWall", "IfcSlab"]
STOREY_CODE = {"Kælder": "K", "Stueetage": "ST", "1. sal": "1", "2. sal": "2", "3. sal": "3", "4. sal": "4"}
OPEN_SYSTEMS = {"DRAINAGE", "SEWAGE", "STORMWATER", "WASTEWATER", "VENTILATION", "EXHAUST"}


def bboxes(model, classes):
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    elems = [e for c in classes for e in model.by_type(c)]
    out = {}
    if not elems:
        return out
    it = ifcopenshell.geom.iterator(s, model, multiprocessing.cpu_count(), include=elems)
    if it.initialize():
        while True:
            sh = it.get()
            v = np.array(sh.geometry.verts).reshape(-1, 3)
            if len(v):
                out[sh.guid] = (v.min(0), v.max(0))
            if not it.next():
                break
    return out


def fire_minutes(rating):
    """'REI 60' -> {'R': 60, 'E': 60, 'I': 60}; 'EI 30' -> E, I; None -> None."""
    if not rating:
        return None
    m = re.search(r"\b(R?)(E?)(I?)\w*\s*(\d+)", rating.replace("-", " "))
    if not m or not (m.group(2) or m.group(3)):
        return None
    return int(m.group(4))


def host_info(e, bb):
    lo, hi = bb
    ext = hi - lo
    psets = ue.get_psets(e)
    rating = (psets.get("Pset_WallCommon") or psets.get("Pset_SlabCommon") or {}).get("FireRating")
    mat = ue.get_material(e)
    mname = getattr(mat, "Name", "") or ""
    if e.is_a("IfcSlab"):
        kind, axis = "rigid_floor", 2
    else:
        axis = int(np.argmin(ext[:2]))
        flexible = any(k in mname.lower() for k in ("gips", "stålskelet", "plasterboard", "stud"))
        kind = "flexible_wall" if flexible else "rigid_wall"
    return {"guid": e.GlobalId, "name": e.Name, "class": e.is_a(), "rating": rating, "ei_required": fire_minutes(rating),
            "kind": kind, "material": mname, "thickness_mm": round(float(ext[axis]) * 1000), "axis": axis,
            "hollow_core": "huldæk" in mname.lower() or "hollow" in mname.lower(),
            "storey": getattr(ue.get_container(e), "Name", None)}


def service_info(e, bb):
    lo, hi = bb
    ext = hi - lo
    axis = int(np.argmax(ext))
    psets = ue.get_psets(e)
    mat = ue.get_material(e)
    mname = getattr(mat, "Name", None) if mat is not None and mat.is_a("IfcMaterial") else None
    systems = [r.RelatingGroup for r in getattr(e, "HasAssignments", []) or []
               if r.is_a("IfcRelAssignsToGroup") and r.RelatingGroup.is_a("IfcDistributionSystem")]
    sys = systems[0] if systems else None
    d = {"guid": e.GlobalId, "name": e.Name, "class": e.is_a(), "axis": axis, "material": mname,
         "system": sys.Name if sys else None, "system_type": sys.PredefinedType if sys else None,
         "open_system": (sys.PredefinedType in OPEN_SYSTEMS) if sys else None,
         "storey": getattr(ue.get_container(e), "Name", None)}
    cross = [ext[i] for i in range(3) if i != axis]
    if e.is_a("IfcPipeSegment"):
        p = psets.get("Pset_PipeSegmentTypeCommon", {})
        od = p.get("OuterDiameter") or p.get("NominalDiameter")
        d["kind"] = "pipe"
        d["od_mm"] = round(od * 1000, 1) if od else None
        d["wall_mm"] = round((p["OuterDiameter"] - p["InnerDiameter"]) * 500, 2) if p.get("InnerDiameter") and p.get("OuterDiameter") else None
    elif e.is_a("IfcDuctSegment"):
        p = psets.get("Pset_DuctSegmentTypeCommon", {})
        d["kind"] = "duct"
        d["od_mm"] = round((p.get("NominalDiameterOrWidth") or max(cross)) * 1000)
    elif e.is_a("IfcCableSegment"):
        p = psets.get("Pset_CableSegmentTypeCommon", {})
        cable = round((p.get("OverallDiameter") or max(cross)) * 1000)
        bundle = round(float(max(cross)) * 1000)
        d["kind"] = "cable_bundle" if (e.ObjectType or "").lower() == "kabelbundt" else "cable"
        d["od_mm"] = cable
        d["bundle_mm"] = bundle if d["kind"] == "cable_bundle" else None
    else:
        p = psets.get("Pset_CableCarrierSegmentTypeCommon", {})
        d["kind"] = "cable_tray"
        d["width_mm"], d["height_mm"] = round((p.get("NominalWidth") or 0) * 1000), round((p.get("NominalHeight") or 0) * 1000)
    ins = None
    for rel in getattr(e, "HasCoverings", None) or []:
        for cov in rel.RelatedCoverings:
            m = ue.get_material(cov)
            if m is not None and m.is_a("IfcMaterialLayerSet") and m.MaterialLayers:
                layer = m.MaterialLayers[0]
                ins = {"product": layer.Material.Name, "category": layer.Material.Category,
                       "thickness_mm": round(layer.LayerThickness * 1000, 1), "extent": "continuous"}
    d["insulation"] = ins
    return d


def overlap(a0, a1, b0, b1):
    return min(a1, b1) - max(a0, b0)


def find(model):
    hb = bboxes(model, HOSTS)
    sb = bboxes(model, SERVICES)
    ob = bboxes(model, ["IfcOpeningElement"])
    hosts = {g: (model.by_guid(g), bb) for g, bb in hb.items()}
    openings = {}
    for g, bb in ob.items():
        op = model.by_guid(g)
        for rel in op.VoidsElements or []:
            openings.setdefault(rel.RelatingBuildingElement.GlobalId, []).append((g, bb))
    pens, unrated = [], 0
    for sg in sorted(sb):
        se = model.by_guid(sg)
        slo, shi = sb[sg]
        sinfo = service_info(se, (slo, shi))
        ax = sinfo["axis"]
        c = (slo + shi) / 2
        for hg in sorted(hosts):
            he, (hlo, hhi) = hosts[hg]
            hinfo = host_info(he, (hlo, hhi))
            if hinfo["axis"] != ax:
                continue
            if not (slo[ax] < hlo[ax] - 1e-3 and shi[ax] > hhi[ax] + 1e-3):
                continue                                          # must pass right through the host
            others = [i for i in range(3) if i != ax]
            if not all(hlo[i] < c[i] < hhi[i] for i in others):
                continue
            if hinfo["ei_required"] is None:
                unrated += 1
                continue
            ap, opening_guid = None, None
            for og, (olo, ohi) in openings.get(hg, []):
                if all(olo[i] <= c[i] <= ohi[i] for i in others):
                    ap = [round(float(ohi[i] - olo[i]) * 1000) for i in others]
                    opening_guid = og
                    ap_box = (olo, ohi)
                    break
            point = [round(float(v), 3) for v in c]
            point[ax] = round(float((hlo[ax] + hhi[ax]) / 2), 3)
            pens.append({"service": sinfo, "host": hinfo, "point": point, "aperture_mm": ap, "opening_guid": opening_guid,
                         "_ap_box": [list(map(float, ap_box[0])), list(map(float, ap_box[1]))] if ap else None, "_others": others})
    # separation between neighbouring seals in the same host (edge to edge, in the host plane)
    for p in pens:
        p["separation_mm"] = None
        if not p["_ap_box"]:
            continue
        for q in pens:
            if q is p or q["host"]["guid"] != p["host"]["guid"] or not q["_ap_box"]:
                continue
            gaps = [max(q["_ap_box"][0][i] - p["_ap_box"][1][i], p["_ap_box"][0][i] - q["_ap_box"][1][i]) for i in p["_others"]]
            gap = max(gaps) if max(gaps) > 0 else 0.0
            if gap * 1000 < 2000:
                p["separation_mm"] = round(min(p["separation_mm"] or 1e9, gap * 1000))
    # ids: G-<storey>-<nn>, in reading order
    pens.sort(key=lambda p: (list(STOREY_CODE).index(p["service"]["storey"]) if p["service"]["storey"] in STOREY_CODE else 9,
                             p["point"][0], p["point"][1], p["point"][2]))
    counter = {}
    for p in pens:
        code = STOREY_CODE.get(p["service"]["storey"], "X")
        counter[code] = counter.get(code, 0) + 1
        p["id"] = f"G-{code}-{counter[code]:02d}"
        p.pop("_ap_box"), p.pop("_others")
    return pens, {"unrated_crossings": unrated, "hosts": len(hosts), "services": len(sb)}
