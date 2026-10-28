"""Data for the browser apps (v2): project register + 3D model, the knowledge base of both ETAs with page images, cases,
dashboard, precedents, verification index, site records, revision diff, quote and downloads.

python -m gennemfoert.export_web
"""
import json
import math
import multiprocessing
import shutil
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import numpy as np
import pymupdf
import trimesh
from PIL import Image

from . import engine, eta, pipeline, quote, revision, text

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
SCALE = 1.6
ETAS = {"ETA-21/0110": {"slug": "eta-21-0110", "pdf": eta.SRC, "product": "Mulcol Multimastic C System", "system": "Multimastic C",
                        "kind": "Brandplader, coating og fuge (gennemføringstætning)", "items": ["6476478013", "6476478014", "6476478010", "6476477922"],
                        "url": "https://s3.beijer-ref-web.cust.servinga.com/production/arm/media/a9/f3/09/1683700778/Mulcol_Multimastic_C_ETA_GB_V2146.pdf"},
        "ETA-20/1322": {"slug": "eta-20-1322", "pdf": ROOT / "data" / "eta" / "source" / "multicollar_eta.pdf", "product": "Mulcol Multicollar Slim",
                        "system": "Multicollar Slim", "kind": "Brandmanchet", "items": ["6476477918"],
                        "url": "https://www.armadan.dk/media/54/41/2d/1729094696/mulcol-multicollarslim-eta-gb-v2345-ast-2189640.pdf"}}
REGISTERED = [  # documents registered in the knowledge base but not yet extracted to rows (next in the import queue)
    {"eta": "ETA-20/1321", "product": "Mulcol Multidisc", "kind": "Kabeldisk", "pages": 49, "status": "registreret, ikke udtrukket"},
    {"eta": "ETA-17/0977", "product": "Mulcol Multifoam 2K", "kind": "Brandskum", "pages": 36, "status": "registreret, ikke udtrukket"},
]
QUALITY = [
    {"eta": "ETA-20/1322", "page": 17, "note": "PP Ø ≤ 125 mm: godstykkelse angivet som '7.1-3.6' (formentlig trykfejl for 7.1-14.6). Rækken matcher aldrig; spørg producenten."},
    {"eta": "ETA-21/0110", "page": 23, "note": "Flettede celler læses forkert af PDF'ens tekstlag; rækkerne er indtastet fra siden og kontrolleret (override)."},
    {"eta": "ETA-21/0110", "page": 48, "note": "Som ovenfor (override). Kobber ≤ 54 mm i dæk har kun E-klassifikation med stenuld."},
    {"eta": "ETA-20/1322", "page": 135, "note": "Kabeltabeller angiver kabeltyper (UTP Cat. 5/6, YMVK), ikke diametre: vises i databasen, matches ikke automatisk."},
]


def glb(model_path, out):
    m = ifcopenshell.open(str(model_path))
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    s.set("weld-vertices", True)
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
    groups = {}
    for g in sorted(meshes):
        e = m.by_guid(g)
        st = getattr(ifcopenshell.util.element.get_container(e), "Name", "?")
        code = {"Kælder": "K", "Stueetage": "ST", "1. sal": "1", "2. sal": "2"}.get(st, "X")
        if e.is_a("IfcWall") or e.is_a("IfcSlab"):
            ps = ifcopenshell.util.element.get_psets(e)
            rating = (ps.get("Pset_WallCommon") or ps.get("Pset_SlabCommon") or {}).get("FireRating")
            mat = getattr(ifcopenshell.util.element.get_material(e), "Name", "") or ""
            kind = "slab" if e.is_a("IfcSlab") else ("light" if "gips" in mat.lower() else "rigid")
            key = f"H_{code}_{kind}_{'r' if rating else 'n'}"
        elif e.is_a("IfcCovering"):
            key = f"I_{code}"
        else:
            sysn = next((r.RelatingGroup.PredefinedType for r in e.HasAssignments or [] if r.is_a("IfcRelAssignsToGroup")), "X")
            key = f"S_{code}_{sysn}"
        groups.setdefault(key, []).append(meshes[g])
    scene = trimesh.Scene()
    for key, ms in groups.items():
        scene.add_geometry(trimesh.util.concatenate(ms), node_name=key, geom_name=key)
    out.parent.mkdir(parents=True, exist_ok=True)
    scene.export(out)


def eta_images(records):
    meta = {}
    for eid, cfg in ETAS.items():
        recs = [r for r in records if r["eta"] == eid]
        doc = pymupdf.open(cfg["pdf"])
        d = WEB / "data" / "eta" / cfg["slug"]
        d.mkdir(parents=True, exist_ok=True)
        meta[eid] = {}
        for page in sorted({r["page"] for r in recs}):
            pg = doc[page - 1]
            rows = [r["row_bbox"] for r in recs if r["page"] == page and r.get("row_bbox")]
            if not rows:
                continue
            tabs = [r["table_bbox"] for r in recs if r["page"] == page and r.get("table_bbox")]
            if eid == "ETA-21/0110":
                head = pg.search_for("Services")
                y0 = (head[0].y0 - 34) if head else (min(b[1] for b in rows) - 60)
                title = [b for b in pg.search_for("Multimastic FB") if y0 - 60 < b.y0 < y0 + 10]
                y0 = min([y0] + [b.y0 - 4 for b in title])
            else:
                y0 = (min(t[1] for t in tabs) - 6) if tabs else (min(b[1] for b in rows) - 60)
            y1 = max([b[3] for b in rows] + [t[3] for t in tabs]) + 6
            clip = pymupdf.Rect(14, max(0, y0), pg.rect.width - 12, min(pg.rect.height, y1))
            pix = pg.get_pixmap(matrix=pymupdf.Matrix(SCALE, SCALE), clip=clip)
            Image.frombytes("RGB", (pix.width, pix.height), pix.samples).save(d / f"p{page}.jpg", quality=80, optimize=True)
            meta[eid][page] = {"x0": clip.x0, "y0": clip.y0, "w": clip.width, "h": clip.height, "dir": cfg["slug"]}
    return meta


def slim_check(c):
    return {"c": c["check"], "ok": c["ok"], "a": c["actual"], "t": c["tested"], "n": c.get("note")}


def slim_ref(r):
    return {"id": r["id"], "eta": r["eta"], "system": r.get("system"), "section": r["section"], "page": r["page"], "heading": r["heading"],
            "service": {"text": r["service"]}, "classification": {"text": r["classification"]},
            "insulation": {"text": r["insulation"], "length": r.get("insulation_length")}, "board": r.get("board"), "wrap": r.get("wrap"),
            "seal": r.get("seal"), "configuration": r.get("configuration"), "collars_per_face": r.get("collars_per_face"),
            "row_bbox": r.get("row_bbox"), "source": r["source"], "deviates": r.get("deviates", []), "checks": [slim_check(c) for c in r["checks"]]}


def slim_verdict(v):
    # same shape as engine.evaluate (and web/engine.js), so every page reads one format
    return {"status": v["status"], "matches": v["matches"][:4], "nearest": v["nearest"][:3], "alternatives": v["alternatives"][:3],
            "conditions": v["conditions"], "questions": v["questions"]}


def main():
    reg = json.loads((ROOT / "results" / "register.json").read_text(encoding="utf-8"))
    pens = reg["penetrations"]
    ass = ROOT / "results" / "assessments.json"
    assessments = {i: a["draft"] for a in json.loads(ass.read_text(encoding="utf-8")) for i in a["ids"]} if ass.exists() else {}
    out = []
    for p in pens:
        out.append({"id": p["id"], "storey": p["service"]["storey"], "point": p["point"], "aperture": p.get("aperture_mm"),
                    "separation": p.get("separation_mm"), "service": {**{k: p["service"].get(k) for k in
                    ("name", "kind", "material", "od_mm", "wall_mm", "bundle_mm", "width_mm", "height_mm", "system", "system_type",
                     "open_system", "insulation", "axis", "guid")}, "line": text.service_line(p["service"])},
                    "host": {k: p["host"][k] for k in ("name", "kind", "rating", "ei_required", "thickness_mm", "material", "axis", "hollow_core", "guid")},
                    **slim_verdict(p["verdict"]), "draft": assessments.get(p["id"])})
    recs = engine.RECORDS
    (WEB / "data").mkdir(parents=True, exist_ok=True)
    meta = eta_images(recs)
    slim_recs = [{k: r[k] for k in ("id", "eta", "system", "section", "heading", "page", "graph_page", "source", "row_bbox", "hosts", "min_thickness",
                                    "board", "configuration", "collars_per_face", "service", "classification", "insulation", "wrap", "seal_max",
                                    "edge_min", "between_min") if k in r} for r in recs]
    kb = {"systems": [{"eta": e, "product": c["product"], "system": c["system"], "kind": c["kind"], "items": c["items"], "url": c["url"],
                       "records": sum(1 for r in recs if r["eta"] == e), "sections": len({r["section"] for r in recs if r["eta"] == e}),
                       "pages_with_rows": len(meta.get(e, {})), "overrides": sum(1 for r in recs if r["eta"] == e and r["source"] == "override")}
                      for e, c in ETAS.items()],
          "registered": REGISTERED, "quality": QUALITY, "version": __import__("gennemfoert.report", fromlist=["kb_version"]).kb_version()}
    # revision B
    revb, _ = pipeline.run(ROOT / "models" / "blok_c_vvs_revB.ifc")
    rev = revision.diff(pens, revb)
    pq = quote.project_quote(pens)
    summary = {"project": "Blok C, etageboliger (demonstration)", "model": reg["stats"]["model"], "count": len(pens),
               "status": reg["stats"]["status"], "unrated": reg["stats"]["unrated_crossings"], "seconds": reg["stats"]["seconds"],
               "labels": text.STATUS, "short": text.SHORT, "actions": text.ACTION, "disclaimer": text.DISCLAIMER,
               "eta": {"pages": meta, "scale": SCALE, "records": len(recs)}, "kb": kb}
    files = {"register.json": out, "summary.json": summary, "records.json": slim_recs, "revision.json": rev, "quote.json": pq}
    for name in ("cases.json", "dashboard.json", "verify.json", "site.json"):
        files[name] = json.loads((ROOT / "results" / name).read_text(encoding="utf-8"))
    files["precedents.json"] = json.loads((ROOT / "data" / "precedents.json").read_text(encoding="utf-8"))
    for name, data in files.items():
        (WEB / "data" / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    for name, data in (("revision.json", rev), ("quote.json", pq), ("kb.json", kb)):          # for the MCP server
        (ROOT / "results" / name).write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    glb(ROOT / "models" / reg["stats"]["model"], WEB / "building.glb")
    dl = WEB / "downloads"
    if dl.exists():
        shutil.rmtree(dl)
    for sub in ("vurderinger", "udstedte"):
        (dl / sub).mkdir(parents=True)
    for f in ["Gennemfoeringsregister.pdf", "Gennemfoeringsregister.xlsx", "Gennemfoert_afvigelser.bcfzip", "blok_c_vvs_gennemfoert.ifc",
              "Dokumentationspakke_bygherre.pdf", "Dokumentation_brandtaetninger.csv"]:
        if (ROOT / "out" / f).exists():
            shutil.copy(ROOT / "out" / f, dl / f)
    for f in ("blok_c_vvs.ifc", "blok_c_vvs_revB.ifc"):
        shutil.copy(ROOT / "models" / f, dl / f)
    for f in (ROOT / "out" / "vurderinger").glob("*.docx"):
        shutil.copy(f, dl / "vurderinger" / f.name)
    for f in (ROOT / "out" / "udstedte_vurderinger").glob("*.pdf"):
        shutil.copy(f, dl / "udstedte" / f.name)
    import csv
    with open(dl / "Tilbud_materialeliste.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["Varenr.", "Tekst", "Antal", "Enhed", "Grundlag"])
        for ln in pq["lines"]:
            w.writerow([ln["no"], ln["name"], ln["qty"], ln["unit"], ln["basis"]])
    summary["downloads"] = sorted(str(p.relative_to(dl)).replace("\\", "/") for p in dl.rglob("*") if p.is_file())
    (WEB / "data" / "summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    size = sum(f.stat().st_size for f in WEB.rglob("*") if f.is_file()) / 1e6
    print("web v2 data:", len(out), "penetrations;", len(recs), "records;", {e: len(m) for e, m in meta.items()}, "page images; web MB", round(size, 1))


if __name__ == "__main__":
    main()
