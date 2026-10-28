"""Gennemført 2.0 MCP server: the fire adviser's operating system for any MCP client (Claude, Copilot, IDE agents).

Answers come from the tested configurations of ETA-21/0110 (Mulcol Multimastic C System, board seals) and ETA-20/1322
(Mulcol Multicollar Slim, fire collars), and for the demonstration data from the IFC-derived penetration register, the
case log, the precedent library and the site records. Every answer carries the ETA section and page. It is decision
support: the adviser confirms against the source and signs any brandteknisk vurdering.

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
from gennemfoert import cases, engine, intake, precedents, text  # noqa: E402

READ = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
server = MCPServer(
    name="gennemfoert", title="Gennemført 2.0",
    instructions=("Passive fire protection: penetration seals checked 'valid only as tested' against ETA-21/0110 (Multimastic C board "
                  "seals) and ETA-20/1322 (Multicollar Slim fire collars). check_penetration answers one set-up; precheck_enquiry "
                  "triages a customer enquiry (completeness, tested or not, region); find_precedents returns earlier decisions on the same "
                  "kind of deviation; list_cases / get_case show the case log with its tamper-evident audit chain; verify_assessment "
                  "checks a code printed on an issued assessment; quote_project gives a material list with item numbers; "
                  "revision_impact lists penetrations whose decisions no longer hold after a model revision. Always cite ETA section and "
                  "page, state deviations plainly, and say that an adviser confirms against the source. Demo data is fictitious. "
                  "Answer in the user's language."),
    version="2.0.0")


def _json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _cite(r):
    return {"eta": r["eta"], "system": r.get("system"), "section": r["section"], "page": r["page"], "service": r["service"],
            "classification": r["classification"], "insulation": r["insulation"], "board": r.get("board"), "wrap": r.get("wrap"),
            "configuration": r.get("configuration"), "collars_per_face": r.get("collars_per_face"), "deviates": r.get("deviates", []),
            "checks": [{"parameter": c["check"], "designed": c["actual"], "tested": c["tested"], "ok": c["ok"], **({"note": c["note"]} if c.get("note") else {})}
                       for c in r["checks"]]}


def _verdict(v):
    return {"status": v["status"], "status_text": text.STATUS[v["status"]], "action": text.ACTION[v["status"]],
            "tested_solutions": [_cite(m) for m in v["matches"][:3]], "nearest_tested": [_cite(m) for m in v["nearest"][:2]],
            "tested_alternatives": [_cite(m) for m in v["alternatives"][:3]], "conditions": v["conditions"],
            "questions": v["questions"], "disclaimer": text.DISCLAIMER}


def _query(construction, thickness_mm, ei_required, service, material=None, outer_diameter_mm=None, wall_thickness_mm=None, system=None,
           insulation_type=None, insulation_thickness_mm=None, insulation_product=None, bundle_diameter_mm=None, aperture_mm=None,
           configuration="perpendicular", separation_mm=None):
    item = {"construction": {"kind": construction, "thickness_mm": thickness_mm, "ei_required": ei_required},
            "service": {"kind": service.lower(), "material": material, "od_mm": outer_diameter_mm, "wall_mm": wall_thickness_mm,
                        "bundle_mm": bundle_diameter_mm, "configuration": configuration or "perpendicular",
                        "system": None if system is None else ("open" if system.lower().startswith(("open", "åben", "aaben", "afløb")) else "closed"),
                        "insulation": "none" if not insulation_type or insulation_type == "none" else
                        {"category": insulation_type, "thickness_mm": insulation_thickness_mm, "product": insulation_product}},
            "aperture_mm": [float(a) for a in aperture_mm] if aperture_mm and len(aperture_mm) == 2 else None, "separation_mm": separation_mm}
    return item, intake.item_query(item)


@server.tool(annotations=READ)
def check_penetration(construction: str, thickness_mm: float, ei_required: int, service: str, material: str | None = None,
                      outer_diameter_mm: float | None = None, wall_thickness_mm: float | None = None, system: str | None = None,
                      insulation_type: str | None = None, insulation_thickness_mm: float | None = None,
                      insulation_product: str | None = None, bundle_diameter_mm: float | None = None,
                      aperture_mm: list[float] | None = None, configuration: str = "perpendicular",
                      separation_mm: float | None = None) -> dict:
    """Is this penetration seal valid as tested? Checks every tested row of both ETAs (board seals and fire collars).
    construction: 'rigid_floor' (concrete/aerated concrete deck, incl. hollow-core), 'rigid_wall' (concrete/masonry) or
    'flexible_wall' (steel studs + plasterboard). service: 'pipe', 'cable', 'cable_bundle', 'cable_tray' or 'duct'.
    material (pipes): PVC-U, PP, PE, PP-R, ABS, copper/kobber, steel/stål, Alupex. system: 'open' (drainage) or 'closed'
    (water, heating). insulation_type: 'none', 'stone_wool', 'elastomeric' (give the product, e.g. 'Armaflex AF'), 'PE-skum'.
    aperture_mm: [width, height] of the hole. configuration: 'perpendicular' (default), 'angled', 'elbow', 'socket',
    'zero_distance', 'corner', 'half_shell'. Returns status (TESTET / AFVIGELSE / IKKE_DAEKKET / ANDET_SYSTEM / MANGLER_DATA)
    with ETA, section, page and every parameter designed vs tested."""
    _, q = _query(construction, thickness_mm, ei_required, service, material, outer_diameter_mm, wall_thickness_mm, system, insulation_type,
                  insulation_thickness_mm, insulation_product, bundle_diameter_mm, aperture_mm, configuration, separation_mm)
    return {"query": {k: v for k, v in q.items() if v is not None}, **_verdict(engine.evaluate(q))}


@server.tool(annotations=READ)
def find_precedents(construction: str, thickness_mm: float, ei_required: int, service: str, material: str | None = None,
                    outer_diameter_mm: float | None = None, wall_thickness_mm: float | None = None, system: str | None = None,
                    insulation_type: str | None = None, insulation_thickness_mm: float | None = None,
                    insulation_product: str | None = None, configuration: str = "perpendicular") -> dict:
    """Earlier decided assessments with the same kind of deviation (same construction kind, same deviating parameters in the
    same direction), so the same question gets the same answer in every office. Same parameters as check_penetration.
    Returns the deviation signature (e.g. godstykkelse, tyndere, -19 %) and the matching precedents with their decision,
    conditions and argument (demo library, fictitious)."""
    _, q = _query(construction, thickness_mm, ei_required, service, material, outer_diameter_mm, wall_thickness_mm, system, insulation_type,
                  insulation_thickness_mm, insulation_product, None, None, configuration)
    v = engine.evaluate(q)
    if v["status"] == "TESTET":
        return {"status": "TESTET", "note": "Testet løsning: ingen vurdering nødvendig.", "tested_solutions": [_cite(m) for m in v["matches"][:1]]}
    near = v["nearest"][0] if v["nearest"] else None
    hits, sig, key = precedents.find(q, near)
    return {"status": v["status"], "nearest_tested": _cite(near) if near else None, "signature": sig, "key": key,
            "precedents": [{k: h[k] for k in ("id", "title", "decision", "conditions", "argument", "eta", "section", "date", "score")} for h in hits],
            "note": "Præcedens er vejledende; hver sag vurderes konkret af rådgiveren."}


@server.tool(annotations=READ)
def precheck_enquiry(items: list[dict], address: str | None = None, timeline: str = "Uafklaret") -> dict:
    """Triage a customer enquiry for a brandteknisk vurdering before it reaches an adviser. Each item:
    {"construction": {"kind", "thickness_mm", "ei_required", "hollow_core"?}, "service": {"kind", "material", "od_mm", "wall_mm",
    "system": "open"|"closed", "insulation": "none" | {"category", "product", "thickness_mm"}, "configuration"?},
    "aperture_mm": [w, h]?, "photos": {"hul", "installation", "konstruktion", "oversigt"}?}. timeline: 'Snarest muligt',
    'Inden for 1 måned', 'Inden for 3 måneder', 'Uafklaret'. Returns per item: completeness %, missing questions, pre-check
    status with the tested solution or the deviating parameters, triage (BESVARET_TESTET / TIL_VURDERING / MANGLER_INFO /
    ANDET_SYSTEM); and for the enquiry: region (ØST Ballerup / VEST Kolding), due date and status."""
    case = intake.receive({"project": {"address": address, "timeline": timeline}, "items": items}, seq=0)
    return {"region": case["region"], "office": case["office"], "due": case["due"], "status": case["status"],
            "items": [{"no": it["no"], "completeness": it["completeness"], "missing": it["missing"], "triage": it["triage"],
                       **_verdict(it["verdict"])} for it in case["items"]]}


@server.tool(annotations=READ)
def search_eta(text_query: str, construction: str | None = None, min_ei: int | None = None, system: str | None = None,
               limit: int = 15) -> list[dict]:
    """Search the tested configurations (678 rows: ETA-21/0110 board seals, ETA-20/1322 fire collars), e.g. 'copper Kaiflex',
    'PVC-U 110', 'elbow', 'cable tray'. Optional construction ('rigid_floor' | 'rigid_wall' | 'flexible_wall'), minimum EI and
    system ('Multimastic C' | 'Multicollar Slim')."""
    words = [w for w in text_query.lower().split() if w]
    out = []
    for r in engine.RECORDS:
        hay = " ".join([r["section"], r["heading"], r["service"]["text"], r["insulation"].get("text") or "", r["classification"]["text"],
                        r.get("system") or "", r.get("configuration") or "", engine.CONF_DA.get(r.get("configuration"), "")]).lower()
        if not all(w in hay for w in words):
            continue
        if construction and construction not in r["hosts"]:
            continue
        if min_ei and (r["classification"].get("EI") or 0) < min_ei:
            continue
        if system and (r.get("system") or "").lower() != system.lower():
            continue
        out.append({"eta": r["eta"], "system": r.get("system"), "section": r["section"], "page": r["page"], "heading": r["heading"],
                    "service": r["service"]["text"], "classification": r["classification"]["text"], "insulation": r["insulation"].get("text"),
                    "configuration": r.get("configuration"), "collars_per_face": r.get("collars_per_face"), "wrap": r.get("wrap"),
                    "seal_max": (r.get("seal_max") or {}).get("text"), "construction": r["hosts"], "min_thickness_mm": r["min_thickness"]})
        if len(out) >= max(1, min(int(limit), 50)):
            break
    return out


@server.tool(annotations=READ)
def knowledge_base() -> dict:
    """What the knowledge base contains: systems, ETAs, rows, sections, item numbers, documents registered but not yet
    extracted, and known data-quality notes in the source documents (e.g. a typo on ETA-20/1322 p. 17)."""
    return _json("results/kb.json")


@server.tool(annotations=READ)
def list_cases(status: str | None = None, region: str | None = None) -> list[dict]:
    """The case log (demo, 30 fictitious enquiries). Filter by status (MODTAGET, MANGLER_INFO, TIL_VURDERING, UDKAST,
    TIL_KONTROL, UDSENDT, BESVARET, ARKIVERET) or region (ØST, VEST)."""
    out = []
    for c in _json("results/cases.json"):
        if status and c["status"] != status.upper():
            continue
        if region and c["region"] != region.upper():
            continue
        out.append({"id": c["id"], "created": c["created"], "due": c["due"], "region": c["region"], "customer": (c.get("customer") or {}).get("company"),
                    "status": c["status"], "status_text": cases.LABEL[c["status"]], "assignee": c.get("assignee"),
                    "items": [{"no": i["no"], "title": i.get("title"), "triage": i["triage"], "decision": (i.get("decision") or {}).get("decision")}
                              for i in c["items"]]})
    return out


@server.tool(annotations=READ)
def get_case(case_id: str) -> dict:
    """One case with items, pre-check, decisions, and the audit log. audit_chain_valid says whether any logged event was
    changed, inserted or removed (SHA-256 chain); four_eyes says whether the reviewer differs from the author."""
    c = next((x for x in _json("results/cases.json") if x["id"].lower() == case_id.lower()), None)
    if not c:
        return {"error": f"unknown case {case_id}"}
    authors = {e["actor"] for e in c["events"] if e["action"] == "udkast_gemt"}
    reviewers = {e["actor"] for e in c["events"] if e["action"] == "kontrol_godkendt"}
    return {"id": c["id"], "status": c["status"], "status_text": cases.LABEL[c["status"]], "region": c["region"], "office": c["office"],
            "due": c["due"], "customer": c.get("customer"), "project": c.get("project"),
            "items": [{"no": i["no"], "title": i.get("title"), "completeness": i["completeness"], "missing": i["missing"], "triage": i["triage"],
                       "decision": i.get("decision"), **_verdict(i["verdict"])} for i in c["items"]],
            "audit_chain_valid": cases.verify(c), "four_eyes": bool(reviewers) and not (authors & reviewers) if authors else None,
            "events": [{k: e[k] for k in ("at", "actor", "action", "state", "kb")} | {"hash": e["hash"][:12]} for e in c["events"]]}


@server.tool(annotations=READ)
def verify_assessment(code: str) -> dict:
    """Check the verification code printed (and QR-coded) on an issued brandteknisk vurdering: genuine, which case and
    item, decision, date, knowledge-base version, and whether it is still valid."""
    v = _json("results/verify.json").get(code.strip().upper())
    return {"code": code.upper(), "genuine": bool(v), **(v or {"message": "Ukendt kode: vurderingen er ikke udstedt af dette system."})}


@server.tool(annotations=READ)
def quote_project() -> dict:
    """Material list for the demonstration project's tested seals, with the wholesaler's item numbers and the basis of each
    quantity (board area incl. waste, joint length, collar segments, clips). Indicative; prices from the customer agreement."""
    return _json("results/quote.json")


@server.tool(annotations=READ)
def revision_impact() -> dict:
    """Model revision A -> B of the demonstration project: penetrations added, removed and changed (matched by IFC GlobalId),
    with the changed parameters. Every changed penetration's earlier decision must be re-assessed."""
    return _json("results/revision.json")


@server.tool(annotations=READ)
def project_overview() -> dict:
    """The demonstration project: penetrations found in the IFC model, status counts, site progress and outputs."""
    reg = _json("results/register.json")
    pens = reg["penetrations"]
    site = _json("results/site.json") if (ROOT / "results" / "site.json").exists() else {}
    return {"project": "Blok C, etageboliger (fictitious demonstration model)", "model": reg["stats"]["model"],
            "penetrations": len(pens), "status": {k: {"count": v, "text": text.STATUS[k]} for k, v in reg["stats"]["status"].items()},
            "solution_systems": {s: sum(1 for p in pens if p["verdict"]["matches"] and p["verdict"]["matches"][0].get("system") == s)
                                 for s in ("Multimastic C", "Multicollar Slim")},
            "site": {"documented": len(site), "inspected": sum(1 for s in site.values() if s.get("inspector")),
                     "remarks": sum(1 for s in site.values() if s.get("remark"))},
            "unrated_crossings_ignored": reg["stats"]["unrated_crossings"], "knowledge_base": "ETA-21/0110 + ETA-20/1322",
            "outputs": ["out/Gennemfoeringsregister.xlsx", "out/Gennemfoeringsregister.pdf (with QR site labels)",
                        "out/Gennemfoert_afvigelser.bcfzip", "out/blok_c_vvs_gennemfoert.ifc", "out/vurderinger/*.docx",
                        "out/udstedte_vurderinger/*.pdf", "out/Dokumentationspakke_bygherre.pdf", "out/Dokumentation_brandtaetninger.csv"]}


@server.tool(annotations=READ)
def list_penetrations(status: str | None = None, storey: str | None = None, construction: str | None = None) -> list[dict]:
    """Penetrations of the demonstration project. Filter by status (TESTET, AFVIGELSE, IKKE_DAEKKET, ANDET_SYSTEM,
    MANGLER_DATA), storey ('Kælder', 'Stueetage', '1. sal', '2. sal') or construction kind."""
    rows = []
    for p in _json("results/register.json")["penetrations"]:
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
    deviations, tested alternatives, conditions, open questions, site record and the draft assessment file if one exists."""
    reg = _json("results/register.json")
    p = next((x for x in reg["penetrations"] if x["id"].lower() == penetration_id.lower()), None)
    if not p:
        return {"error": f"unknown penetration {penetration_id}", "known": [x["id"] for x in reg["penetrations"]][:80]}
    drafts = {i: a["draft"] for a in _json("results/assessments.json") for i in a["ids"]}
    site = _json("results/site.json").get(p["id"]) if (ROOT / "results" / "site.json").exists() else None
    s, h = p["service"], p["host"]
    return {"id": p["id"], "storey": s["storey"], "service": text.service_line(s), "system": s.get("system"),
            "construction": {"name": h["name"], "kind": h["kind"], "thickness_mm": h["thickness_mm"], "rating": h["rating"]},
            "aperture_mm": p.get("aperture_mm"), "separation_to_next_seal_mm": p.get("separation_mm"),
            "ifc": {"service_guid": s["guid"], "construction_guid": h["guid"]}, **_verdict(p["verdict"]), "site": site,
            "draft_assessment": f"out/vurderinger/{drafts[p['id']]}" if p["id"] in drafts else None}


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False))
def export_documents() -> dict:
    """Re-write the register (XLSX + PDF with QR labels), the BCF file and the IFC with seal objects into out/."""
    from gennemfoert import register, writeback
    reg = _json("results/register.json")
    pens = reg["penetrations"]
    x, m = register.write_xlsx(pens, reg["stats"])
    pdf = register.write_pdf(pens, reg["stats"])
    bcf, n = writeback.write_bcf(pens)
    ifc = writeback.write_ifc(ROOT / "models" / reg["stats"]["model"], pens)
    return {"register_xlsx": str(x), "register_pdf": str(pdf), "bcf": str(bcf), "bcf_topics": n, "ifc": str(ifc), "material_estimate": m}


if __name__ == "__main__":
    server.run("stdio")
