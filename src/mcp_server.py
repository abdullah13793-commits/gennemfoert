"""Gennemført MCP server: penetration seals, valid as tested, for any MCP client (Claude, Copilot, IDE agents).

Answers come from the tested configurations of ETA-21/0110 (Mulcol Multimastic C System, ETA-Danmark 2021) and,
for the demonstration project, from the IFC-derived penetration register. Every answer carries the ETA section and
page. It is decision support: the adviser confirms against the source and signs any brandteknisk vurdering.

Run (stdio):   python src/mcp_server.py
Client config: {"mcpServers": {"gennemfoert": {"command": "python", "args": ["<repo>/src/mcp_server.py"]}}}
"""
import json
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gennemfoert import engine, text  # noqa: E402

READ = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
server = MCPServer(
    name="gennemfoert", title="Gennemført",
    instructions=("Passive fire protection: penetration seals checked 'valid only as tested' against ETA-21/0110 "
                  "(Mulcol Multimastic C System). Use check_penetration for a single enquiry (construction, EI, service, "
                  "size, insulation). Use project_overview / list_penetrations / get_penetration for the demonstration "
                  "project (Blok C, fictitious). Always cite the ETA section and page from the result, state deviations "
                  "plainly, and say that an adviser confirms against the source document. Answer in the user's language."),
    version="1.0.0")


def _register():
    return json.loads((ROOT / "results" / "register.json").read_text(encoding="utf-8"))


def _cite(r):
    return {"eta": r["eta"], "section": r["section"], "page": r["page"], "service": r["service"], "classification": r["classification"],
            "insulation": r["insulation"], "board": r.get("board"), "wrap": r.get("wrap"),
            "deviates": r.get("deviates", []),
            "checks": [{"parameter": c["check"], "designed": c["actual"], "tested": c["tested"], "ok": c["ok"], **({"note": c["note"]} if c.get("note") else {})}
                       for c in r["checks"]]}


def _verdict(v):
    return {"status": v["status"], "status_text": text.STATUS[v["status"]], "action": text.ACTION[v["status"]],
            "tested_solutions": [_cite(m) for m in v["matches"][:3]], "nearest_tested": [_cite(m) for m in v["nearest"][:2]],
            "tested_alternatives": [_cite(m) for m in v["alternatives"][:2]], "conditions": v["conditions"],
            "questions": v["questions"], "disclaimer": text.DISCLAIMER}


@server.tool(annotations=READ)
def check_penetration(construction: str, thickness_mm: float, ei_required: int, service: str, material: str | None = None,
                      outer_diameter_mm: float | None = None, wall_thickness_mm: float | None = None, system: str | None = None,
                      insulation_type: str | None = None, insulation_thickness_mm: float | None = None,
                      insulation_product: str | None = None, bundle_diameter_mm: float | None = None,
                      aperture_mm: list[float] | None = None) -> dict:
    """Is this penetration seal valid as tested? One enquiry, no model needed.
    construction: 'rigid_floor' (concrete/aerated concrete deck, incl. hollow-core), 'rigid_wall' (concrete/masonry) or
    'flexible_wall' (steel studs + plasterboard). service: 'pipe', 'cable', 'cable_bundle', 'cable_tray' or 'duct'.
    material (pipes): PVC-U, PP, PE, copper/kobber, steel/stål, Alupex. system: 'open' (drainage) or 'closed'
    (water, heating). insulation_type: 'none', 'stone_wool', 'elastomeric'. aperture_mm: [width, height] of the hole.
    Returns status (TESTET / AFVIGELSE / IKKE_DAEKKET / ANDET_SYSTEM / MANGLER_DATA) with ETA section, page and
    every parameter designed vs tested."""
    sk = service.lower()
    q = {"host_kind": construction, "thickness_mm": thickness_mm, "ei_required": ei_required, "service_kind": sk,
         "material": engine.norm_material(material), "od_mm": outer_diameter_mm, "wall_mm": wall_thickness_mm,
         "bundle_mm": bundle_diameter_mm, "open_system": None if system is None else system.lower().startswith(("open", "åben", "aaben")),
         "insulation": engine.norm_insulation(None if not insulation_type or insulation_type == "none" else
                                              {"category": insulation_type, "thickness_mm": insulation_thickness_mm, "product": insulation_product}),
         "hollow_core": False}
    if aperture_mm and len(aperture_mm) == 2:
        tot = (outer_diameter_mm or bundle_diameter_mm or 0) + 2 * (insulation_thickness_mm or 0)
        q["aperture_mm"] = [float(a) for a in aperture_mm]
        q["edge_mm"] = round((min(aperture_mm) - tot) / 2)
        q["fill"] = round(3.14159 * tot * tot / 4 / (aperture_mm[0] * aperture_mm[1]), 3)
    return {"query": {k: v for k, v in q.items() if v is not None}, **_verdict(engine.evaluate(q))}


@server.tool(annotations=READ)
def search_eta(text_query: str, construction: str | None = None, min_ei: int | None = None, limit: int = 15) -> list[dict]:
    """Search the tested configurations of ETA-21/0110 (293 rows from Annex A), e.g. 'copper Kaiflex', 'PVC-U 110',
    'cable tray'. Optional construction ('rigid_floor' | 'rigid_wall' | 'flexible_wall') and minimum EI."""
    words = [w for w in text_query.lower().split() if w]
    out = []
    for r in engine.RECORDS:
        hay = " ".join([r["section"], r["heading"], r["service"]["text"], r["insulation"]["text"], r["classification"]["text"]]).lower()
        if not all(w in hay for w in words):
            continue
        if construction and construction not in r["hosts"]:
            continue
        if min_ei and (r["classification"].get("EI") or 0) < min_ei:
            continue
        out.append({"eta": r["eta"], "section": r["section"], "page": r["page"], "heading": r["heading"], "service": r["service"]["text"],
                    "classification": r["classification"]["text"], "insulation": r["insulation"]["text"], "wrap": r.get("wrap"),
                    "seal_max": (r.get("seal_max") or {}).get("text"), "construction": r["hosts"], "min_thickness_mm": r["min_thickness"]})
        if len(out) >= max(1, min(int(limit), 50)):
            break
    return out


@server.tool(annotations=READ)
def project_overview() -> dict:
    """The demonstration project: penetrations found in the IFC model, status counts, and what to do next."""
    reg = _register()
    pens = reg["penetrations"]
    return {"project": "Blok C, etageboliger (fictitious demonstration model)", "model": reg["stats"]["model"],
            "penetrations": len(pens), "status": {k: {"count": v, "text": text.STATUS[k]} for k, v in reg["stats"]["status"].items()},
            "unrated_crossings_ignored": reg["stats"]["unrated_crossings"], "eta": "ETA-21/0110 Mulcol Multimastic C System",
            "outputs": ["out/Gennemfoeringsregister.xlsx", "out/Gennemfoeringsregister.pdf (with QR site labels)",
                        "out/Gennemfoert_afvigelser.bcfzip", "out/blok_c_vvs_gennemfoert.ifc", "out/vurderinger/*.docx"]}


@server.tool(annotations=READ)
def list_penetrations(status: str | None = None, storey: str | None = None, construction: str | None = None) -> list[dict]:
    """Penetrations of the demonstration project. Filter by status (TESTET, AFVIGELSE, IKKE_DAEKKET, ANDET_SYSTEM,
    MANGLER_DATA), storey ('Kælder', 'Stueetage', '1. sal', '2. sal') or construction kind."""
    rows = []
    for p in _register()["penetrations"]:
        v = p["verdict"]
        if status and v["status"] != status.upper():
            continue
        if storey and p["service"]["storey"] != storey:
            continue
        if construction and p["host"]["kind"] != construction:
            continue
        rows.append({"id": p["id"], "storey": p["service"]["storey"], "service": text.service_line(p["service"]),
                     "construction": f"{p['host']['name']} ({p['host']['rating']})", "status": v["status"], "solution": text.solution_line(v)})
    return rows


@server.tool(annotations=READ)
def get_penetration(penetration_id: str) -> dict:
    """Everything about one penetration (e.g. 'G-ST-02'): service, construction, aperture, verdict with ETA citations,
    deviations, tested alternatives, conditions, open questions and the draft assessment file if one exists."""
    reg = _register()
    p = next((x for x in reg["penetrations"] if x["id"].lower() == penetration_id.lower()), None)
    if not p:
        return {"error": f"unknown penetration {penetration_id}", "known": [x["id"] for x in reg["penetrations"]][:80]}
    drafts = {i: a["draft"] for a in json.loads((ROOT / "results" / "assessments.json").read_text(encoding="utf-8")) for i in a["ids"]}
    s, h = p["service"], p["host"]
    return {"id": p["id"], "storey": s["storey"], "service": text.service_line(s), "system": s.get("system"),
            "construction": {"name": h["name"], "kind": h["kind"], "thickness_mm": h["thickness_mm"], "rating": h["rating"]},
            "aperture_mm": p.get("aperture_mm"), "separation_to_next_seal_mm": p.get("separation_mm"),
            "ifc": {"service_guid": s["guid"], "construction_guid": h["guid"]}, **_verdict(p["verdict"]),
            "draft_assessment": f"out/vurderinger/{drafts[p['id']]}" if p["id"] in drafts else None}


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False))
def export_documents() -> dict:
    """Re-write the register (XLSX + PDF with QR labels), the BCF file and the IFC with seal objects into out/."""
    from gennemfoert import register, writeback
    reg = _register()
    pens = reg["penetrations"]
    x, m = register.write_xlsx(pens, reg["stats"])
    pdf = register.write_pdf(pens, reg["stats"])
    bcf, n = writeback.write_bcf(pens)
    ifc = writeback.write_ifc(ROOT / "models" / reg["stats"]["model"], pens)
    return {"register_xlsx": str(x), "register_pdf": str(pdf), "bcf": str(bcf), "bcf_topics": n, "ifc": str(ifc), "material_estimate": m}


if __name__ == "__main__":
    server.run("stdio")
