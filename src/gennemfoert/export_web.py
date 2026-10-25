"""Data for the browser app: building.glb, register.json, records.json and the ETA table images.

python -m gennemfoert.export_web
"""
import json
import multiprocessing
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import numpy as np
import pymupdf
import trimesh

from . import eta, text

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
SCALE = 1.7


def glb(model_path, pens, out):
    m = ifcopenshell.open(str(model_path))
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    s.set("weld-vertices", True)
    groups = {}
    classes = ["IfcWall", "IfcSlab", "IfcPipeSegment", "IfcDuctSegment", "IfcCableSegment", "IfcCableCarrierSegment", "IfcCovering"]
    elems = [e for c in classes for e in m.by_type(c)]
    it = ifcopenshell.geom.iterator(s, m, multiprocessing.cpu_count(), include=elems)
    meshes = {}
    if it.initialize():
        while True:
            sh = it.get()
            v = np.array(sh.geometry.verts).reshape(-1, 3)
            f = np.array(sh.geometry.faces).reshape(-1, 3)
            if len(f):
                meshes[sh.guid] = trimesh.Trimesh(v, f, process=False)
            if not it.next():
                break
    scene = trimesh.Scene()
    by_storey = {}
    for g in sorted(meshes):
        e = m.by_guid(g)
        st = getattr(ifcopenshell.util.element.get_container(e), "Name", "?")
        code = {"Kælder": "K", "Stueetage": "ST", "1. sal": "1", "2. sal": "2"}.get(st, "X")
        if e.is_a("IfcWall") or e.is_a("IfcSlab"):
            rating = (ifcopenshell.util.element.get_psets(e).get("Pset_WallCommon") or
                      ifcopenshell.util.element.get_psets(e).get("Pset_SlabCommon") or {}).get("FireRating")
            mat = getattr(ifcopenshell.util.element.get_material(e), "Name", "") or ""
            kind = "slab" if e.is_a("IfcSlab") else ("light" if "gips" in mat.lower() else "rigid")
            key = f"H_{code}_{kind}_{'r' if rating else 'n'}"
        elif e.is_a("IfcCovering"):
            key = f"I_{code}"
        else:
            sysn = next((r.RelatingGroup.PredefinedType for r in e.HasAssignments or [] if r.is_a("IfcRelAssignsToGroup")), "X")
            key = f"S_{code}_{sysn}"
        by_storey.setdefault(key, []).append(meshes[g])
    for key, ms in by_storey.items():
        merged = trimesh.util.concatenate(ms)
        scene.add_geometry(merged, node_name=key, geom_name=key)
    out.parent.mkdir(parents=True, exist_ok=True)
    scene.export(out)
    return out


def eta_images(records, out_dir):
    doc = pymupdf.open(eta.SRC)
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {}
    for page in sorted({r["page"] for r in records}):
        rows = [r["row_bbox"] for r in records if r["page"] == page and r.get("row_bbox")]
        pg = doc[page - 1]
        head = pg.search_for("Services")
        y0 = (head[0].y0 - 34) if head else (min(b[1] for b in rows) - 60)
        y1 = max(b[3] for b in rows) + 6
        title = [b for b in pg.search_for("Multimastic FB") if b.y0 < y0 + 10 and b.y0 > y0 - 60]
        y0 = min([y0] + [b.y0 - 4 for b in title])
        clip = pymupdf.Rect(14, max(0, y0), 583, min(pg.rect.height, y1))
        pg.get_pixmap(matrix=pymupdf.Matrix(SCALE, SCALE), clip=clip).save(out_dir / f"p{page}.png")
        meta[page] = {"x0": clip.x0, "y0": clip.y0, "w": clip.width, "h": clip.height}
    # convert to webp-sized jpeg for the web
    from PIL import Image
    for page in meta:
        pth = out_dir / f"p{page}.png"
        Image.open(pth).convert("RGB").save(out_dir / f"p{page}.jpg", quality=82, optimize=True)
        pth.unlink()
    return meta


def slim_check(c):
    return {"c": c["check"], "ok": c["ok"], "a": c["actual"], "t": c["tested"], "n": c.get("note")}


def slim_ref(r):
    return {"id": r["id"], "eta": r["eta"], "section": r["section"], "page": r["page"], "heading": r["heading"],
            "service": {"text": r["service"]}, "classification": {"text": r["classification"]},
            "insulation": {"text": r["insulation"], "length": r.get("insulation_length")}, "board": r.get("board"), "wrap": r.get("wrap"),
            "seal": r.get("seal"), "row_bbox": r.get("row_bbox"), "source": r["source"], "deviates": r.get("deviates", []),
            "checks": [slim_check(c) for c in r["checks"]]}


def main():
    reg = json.loads((ROOT / "results" / "register.json").read_text(encoding="utf-8"))
    pens = reg["penetrations"]
    assessments = {i: a["draft"] for a in json.loads((ROOT / "results" / "assessments.json").read_text(encoding="utf-8")) for i in a["ids"]}
    out = []
    for p in pens:
        v = p["verdict"]
        out.append({"id": p["id"], "storey": p["service"]["storey"], "point": p["point"], "aperture": p.get("aperture_mm"),
                    "separation": p.get("separation_mm"), "service": {**{k: p["service"].get(k) for k in
                    ("name", "kind", "material", "od_mm", "wall_mm", "bundle_mm", "width_mm", "height_mm", "system", "system_type",
                     "open_system", "insulation", "axis")}, "line": text.service_line(p["service"])},
                    "host": {k: p["host"][k] for k in ("name", "kind", "rating", "ei_required", "thickness_mm", "material", "axis", "hollow_core")},
                    "status": v["status"], "matches": [slim_ref(r) for r in v["matches"][:4]], "nearest": [slim_ref(r) for r in v["nearest"][:2]],
                    "alternatives": [slim_ref(r) for r in v["alternatives"][:2]], "conditions": v["conditions"], "questions": v["questions"],
                    "draft": assessments.get(p["id"])})
    recs = eta.RECORDS if hasattr(eta, "RECORDS") else json.loads((ROOT / "data" / "eta" / "records.json").read_text(encoding="utf-8"))
    (WEB / "data").mkdir(parents=True, exist_ok=True)
    meta = eta_images(recs, WEB / "data" / "eta")
    summary = {"project": "Blok C, etageboliger (demonstration)", "model": reg["stats"]["model"], "count": len(pens),
               "status": reg["stats"]["status"], "unrated": reg["stats"]["unrated_crossings"], "seconds": reg["stats"]["seconds"],
               "labels": text.STATUS, "short": text.SHORT, "actions": text.ACTION, "disclaimer": text.DISCLAIMER,
               "eta": {"id": eta.ETA_ID, "product": eta.PRODUCT, "records": len(recs), "sections": len({r["section"] for r in recs}),
                       "pages": meta, "scale": SCALE},
               "materials": json.loads((ROOT / "results" / "materials.json").read_text(encoding="utf-8"))}
    (WEB / "data" / "register.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    (WEB / "data" / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    (WEB / "data" / "records.json").write_text(json.dumps(recs, ensure_ascii=False), encoding="utf-8")
    glb(ROOT / "models" / reg["stats"]["model"], pens, WEB / "building.glb")
    import shutil
    dl = WEB / "downloads"
    if dl.exists():
        shutil.rmtree(dl)
    (dl / "vurderinger").mkdir(parents=True)
    for f in ["Gennemfoeringsregister.pdf", "Gennemfoeringsregister.xlsx", "Gennemfoert_afvigelser.bcfzip", "blok_c_vvs_gennemfoert.ifc"]:
        shutil.copy(ROOT / "out" / f, dl / f)
    shutil.copy(ROOT / "models" / reg["stats"]["model"], dl / reg["stats"]["model"])
    for f in (ROOT / "out" / "vurderinger").glob("*.docx"):
        shutil.copy(f, dl / "vurderinger" / f.name)
    size = sum(f.stat().st_size for f in WEB.rglob("*") if f.is_file()) / 1e6
    print("web data written;", len(out), "penetrations;", len(meta), "ETA page images; web MB", round(size, 1))


if __name__ == "__main__":
    import ifcopenshell.util.element  # noqa: F401
    main()
