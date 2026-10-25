"""Write the verdicts back into the formats the project already uses.

- IFC: one IfcBuildingElementProxy (PROVISIONFORVOID) per penetration seal, filling the architect's opening
  (IfcRelFillsElement), with the standard Pset_ProvisionForVoid and a Gennemfoert_Taetning set (status,
  solution, ETA reference, deviations, conditions, inspection fields left blank for site).
- BCF 2.1: one topic per penetration that is not TESTET, with the service and the host selected.
"""
import datetime
import json
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import ifcopenshell
import ifcopenshell.api as api
import ifcopenshell.guid

from . import ifcw, text

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"


def write_ifc(model_path, pens, out=None):
    out = out or OUT / (Path(model_path).stem + "_gennemfoert.ifc")
    f = ifcopenshell.open(str(model_path))
    ifcw._materials.clear()
    group = api.run("root.create_entity", f, ifc_class="IfcGroup", name="Gennemføringer (Gennemført)")
    seals = []
    for p in pens:
        s, h, v = p["service"], p["host"], p["verdict"]
        storey = next((st for st in f.by_type("IfcBuildingStorey") if st.Name == s["storey"]), None)
        x, y, z = p["point"]
        ap = p.get("aperture_mm") or [200, 200]
        a, b = ap[0] / 2000, ap[1] / 2000
        d = h["thickness_mm"] / 2000
        if h["kind"] == "rigid_floor":
            box = (x - a, y - b, z - d, x + a, y + b, z + d)
        elif h["axis"] == 0:
            box = (x - d, y - a, z - b, x + d, y + a, z + b)
        else:
            box = (x - a, y - d, z - b, x + a, y + d, z + b)
        e = ifcw.element(f, "IfcBuildingElementProxy", f"{p['id']} Brandtætning", [ifcw.box_solid(f, *box)], storey,
                         predefined="PROVISIONFORVOID")
        e.Tag, e.Description = p["id"], text.STATUS[v["status"]]
        ifcw.add_pset(f, e, "Pset_ProvisionForVoid", {"Shape": "RECTANGLE", "Width": ap[0] / 1000, "Height": ap[1] / 1000,
                                                       "Depth": h["thickness_mm"] / 1000, "System": s.get("system") or ""})
        best = (v["matches"] or v["nearest"] or [None])[0]
        props = {"Id": p["id"], "Status": v["status"], "StatusTekst": text.STATUS[v["status"]], "Handling": text.ACTION[v["status"]],
                 "Gennemfoering": text.service_line(s), "Konstruktion": f"{text.HOST[h['kind']]} {h['thickness_mm']} mm, {h['rating']}",
                 "KravEI": h["ei_required"], "Loesning": text.solution_line(v),
                 "ETA": best["eta"] if best else "", "ETAAfsnit": best["section"] if best else "", "ETASide": best["page"] if best else 0,
                 "Klassifikation": best["classification"] if best else "",
                 "Afvigelser": ", ".join(best["deviates"]) if best and best.get("deviates") else "",
                 "Betingelser": " | ".join(v["conditions"]), "Spoergsmaal": " | ".join(v["questions"]),
                 "ServiceGlobalId": s["guid"], "KonstruktionGlobalId": h["guid"],
                 "Udfoert": False, "UdfoertAf": "", "Kontrolleret": False, "KontrolleretAf": "", "KontrolDato": "", "FotoReference": ""}
        ifcw.add_pset(f, e, "Gennemfoert_Taetning", props)
        if p.get("opening_guid"):
            f.createIfcRelFillsElement(ifcopenshell.guid.new(), None, "Brandtætning", None, f.by_guid(p["opening_guid"]), e)
        seals.append(e)
    api.run("group.assign_group", f, group=group, products=seals)
    out.parent.mkdir(parents=True, exist_ok=True)
    f.write(str(out))
    return out


def _vp(camera, target, guids):
    cx, cy, cz = camera
    dx, dy, dz = (target[0] - cx, target[1] - cy, target[2] - cz)
    nrm = (dx * dx + dy * dy + dz * dz) ** 0.5 or 1
    comps = "".join(f'<Component IfcGuid="{g}"/>' for g in guids)
    return (f'<?xml version="1.0" encoding="UTF-8"?><VisualizationInfo Guid="{uuid.uuid4()}"><Components>'
            f'<Selection>{comps}</Selection><Visibility DefaultVisibility="true"/></Components>'
            f'<PerspectiveCamera><CameraViewPoint><X>{cx:.3f}</X><Y>{cy:.3f}</Y><Z>{cz:.3f}</Z></CameraViewPoint>'
            f'<CameraDirection><X>{dx / nrm:.4f}</X><Y>{dy / nrm:.4f}</Y><Z>{dz / nrm:.4f}</Z></CameraDirection>'
            f'<CameraUpVector><X>0</X><Y>0</Y><Z>1</Z></CameraUpVector><FieldOfView>60</FieldOfView></PerspectiveCamera>'
            f'</VisualizationInfo>')


def write_bcf(pens, project="Blok C (demonstration)", out=None):
    out = out or OUT / "Gennemfoert_afvigelser.bcfzip"
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    n = 0
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("bcf.version", '<?xml version="1.0" encoding="UTF-8"?><Version VersionId="2.1"><DetailedVersion>2.1</DetailedVersion></Version>')
        z.writestr("project.bcfp", f'<?xml version="1.0" encoding="UTF-8"?><ProjectExtension><Project ProjectId="{uuid.uuid4()}">'
                                   f'<Name>{escape(project)} - Gennemført</Name></Project><ExtensionSchema></ExtensionSchema></ProjectExtension>')
        for p in pens:
            v = p["verdict"]
            if v["status"] == "TESTET":
                continue
            n += 1
            s, h = p["service"], p["host"]
            tid = str(uuid.uuid4())
            target = p["point"]
            cam = (target[0] - 3.5, target[1] - 4.5, target[2] + 2.5)
            lines = [f"{text.STATUS[v['status']]}", "", f"Gennemføring: {text.service_line(s)}",
                     f"Konstruktion: {h['name']} ({text.HOST[h['kind']]} {h['thickness_mm']} mm, {h['rating']})"]
            if v["nearest"]:
                nb = v["nearest"][0]
                lines.append(f"Nærmeste testede løsning: {nb['eta']} {nb['section']}, s. {nb['page']}: {nb['service']} | {nb['classification']}")
                for c in nb["checks"]:
                    if not c["ok"]:
                        lines.append(f"  Afviger: {c['check']}: projekteret {c['actual']}, testet {c['tested']}")
            for a in v.get("alternatives", [])[:1]:
                lines.append(f"Testet alternativ: {a['eta']} {a['section']} (s. {a['page']}): {a['insulation']} | {a['classification']}")
            for qn in v["questions"]:
                lines.append(f"Spørgsmål: {qn}")
            for c in v["conditions"]:
                lines.append(f"Note: {c}")
            lines += ["", f"Handling: {text.ACTION[v['status']]}", text.DISCLAIMER]
            markup = (f'<?xml version="1.0" encoding="UTF-8"?><Markup><Topic Guid="{tid}" TopicType="Issue" TopicStatus="Open">'
                      f'<Title>{escape(p["id"] + " " + text.STATUS[v["status"]] + ": " + text.service_line(s))}</Title>'
                      f'<Priority>{text.PRIORITY[v["status"]]}</Priority><Labels>Brandtætning</Labels><Labels>{v["status"]}</Labels>'
                      f'<CreationDate>{now}</CreationDate><CreationAuthor>Gennemført</CreationAuthor>'
                      f'<Description>{escape(chr(10).join(lines))}</Description></Topic>'
                      f'<Viewpoints Guid="{uuid.uuid4()}"><Viewpoint>viewpoint.bcfv</Viewpoint></Viewpoints></Markup>')
            z.writestr(f"{tid}/markup.bcf", markup)
            z.writestr(f"{tid}/viewpoint.bcfv", _vp(cam, target, [s["guid"], h["guid"]]))
    return out, n


if __name__ == "__main__":
    reg = json.loads((ROOT / "results" / "register.json").read_text(encoding="utf-8"))
    pens = reg["penetrations"]
    ifc = write_ifc(ROOT / "models" / reg["stats"]["model"], pens)
    bcf, n = write_bcf(pens)
    # verify: re-open, count proxies and psets, parse BCF
    g = ifcopenshell.open(str(ifc))
    import ifcopenshell.util.element as ue
    prox = [e for e in g.by_type("IfcBuildingElementProxy") if e.PredefinedType == "PROVISIONFORVOID"]
    with_ps = sum(1 for e in prox if ue.get_pset(e, "Gennemfoert_Taetning") and ue.get_pset(e, "Pset_ProvisionForVoid"))
    fills = sum(1 for e in prox if e.FillsVoids)
    import xml.dom.minidom
    with zipfile.ZipFile(bcf) as z:
        parsed = sum(1 for nm in z.namelist() if nm.endswith((".bcf", ".bcfv", ".version", ".bcfp")) and xml.dom.minidom.parseString(z.read(nm)))
    res = {"ifc": ifc.name, "seals": len(prox), "with_psets": with_ps, "fills_opening": fills, "bcf": bcf.name, "bcf_topics": n,
           "bcf_xml_parsed": parsed}
    (ROOT / "results" / "writeback.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(res)
