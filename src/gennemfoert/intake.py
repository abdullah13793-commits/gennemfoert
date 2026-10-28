"""Structured enquiry (forespørgsel) for a brandteknisk vurdering, replacing a free-text form.

The fields follow the adviser's own checklist (project and challenge, construction, installation, fire requirement,
drawings and photos), but as data, one item per penetration type. Every item is pre-checked against the knowledge base
while it is entered: if the set-up is tested, the customer gets the tested solution at once and no assessment is needed
(deflection); if it deviates, the deviating parameter is named; if something is missing, the questions are asked
before the enquiry reaches an adviser.
"""
import datetime
import re

from . import engine

CONSTRUCTIONS = {"rigid_floor": "Massivt dæk (beton/letbeton, også huldæk)", "rigid_wall": "Massiv væg (beton, letbeton, murværk)",
                 "flexible_wall": "Let væg (stålskelet med gipsplader)"}
SERVICES = {"pipe": "Rør", "cable": "Kabel", "cable_bundle": "Kabelbundt", "cable_tray": "Kabelbakke", "duct": "Ventilationskanal"}
PHOTOS = {"hul": "Hullet/udsparingen med mål", "installation": "Røret/kablet med isolering og mærkning", "konstruktion": "Væg/dæk-opbygning (kant, lag)",
          "oversigt": "Oversigtsbillede af placeringen"}
REQUIRED = [  # (path, weight, question)
    ("construction.kind", 3, "Hvilken konstruktion (massivt dæk, massiv væg, let væg)?"),
    ("construction.thickness_mm", 2, "Konstruktionens tykkelse (mm)?"),
    ("construction.ei_required", 3, "Krævet brandmodstand (fx EI 60)?"),
    ("service.kind", 3, "Hvilken installation (rør, kabel, kabelbakke, kanal)?"),
    ("service.material", 2, "Rørmateriale?"),
    ("service.od_mm", 2, "Udvendig diameter (mm)?"),
    ("service.wall_mm", 1, "Godstykkelse (mm)?"),
    ("service.system", 1, "Åbent (afløb) eller lukket (brugsvand/varme) system?"),
    ("service.insulation", 1, "Isolering: type, fabrikat og tykkelse (eller ingen)?"),
    ("aperture_mm", 1, "Hullets størrelse (mm)?"),
]
# postcodes 5000-9999 are Funen and Jutland (west adviser, Kolding); 1000-4999 Zealand and islands (east, Ballerup)
REGIONS = {"ØST": {"office": "Ballerup", "advisers": ["Rådgiver Øst 1", "Rådgiver Øst 2"]},
           "VEST": {"office": "Kolding", "advisers": ["Rådgiver Vest"]}}
SLA_DAYS = {"Snarest muligt": 3, "Inden for 1 måned": 10, "Inden for 3 måneder": 20, "Uafklaret": 10}


def _get(d, path):
    for k in path.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def item_query(item):
    c, s = item.get("construction") or {}, item.get("service") or {}
    ins = s.get("insulation")
    q = {"host_kind": c.get("kind"), "thickness_mm": c.get("thickness_mm"), "ei_required": c.get("ei_required"),
         "hollow_core": bool(c.get("hollow_core")), "service_kind": s.get("kind"), "material": engine.norm_material(s.get("material")),
         "od_mm": s.get("od_mm"), "wall_mm": s.get("wall_mm"), "bundle_mm": s.get("bundle_mm"),
         "open_system": None if s.get("system") is None else s.get("system") == "open",
         "insulation": engine.norm_insulation(None if not ins or ins == "none" else ins),
         "configuration": s.get("configuration") or "perpendicular"}
    if item.get("aperture_mm"):
        ap = item["aperture_mm"]
        q["aperture_mm"] = ap
        tot = engine.outer_diameter(q)
        q["edge_mm"] = round((min(ap) - tot) / 2)
        q["fill"] = round(3.14159 * tot * tot / 4 / (ap[0] * ap[1]), 3) if tot else None
    if item.get("separation_mm") is not None:
        q["separation_mm"] = item["separation_mm"]
    return q


def completeness(item):
    s = item.get("service") or {}
    total, have, missing = 0, 0, []
    for path, w, question in REQUIRED:
        if path.startswith("service.") and s.get("kind") not in ("pipe", None) and path in ("service.material", "service.wall_mm",
                                                                                             "service.system", "service.insulation"):
            continue
        total += w
        v = _get(item, path)
        if v not in (None, "", []):
            have += w
        else:
            missing.append(question)
    photos = item.get("photos") or {}
    for k, label in PHOTOS.items():
        total += 1
        if photos.get(k):
            have += 1
        else:
            missing.append(f"Foto: {label}")
    return round(100 * have / total), missing


def precheck(item):
    q = item_query(item)
    if not q["host_kind"] or not q["service_kind"]:
        return {"status": "MANGLER_DATA", "questions": ["Konstruktion og installation skal angives."], "matches": [], "nearest": [],
                "alternatives": [], "conditions": []}
    return engine.evaluate(q)


def region_for(address):
    m = re.search(r"\b(\d{4})\b", address or "")
    if not m:
        return "ØST"
    return "VEST" if int(m.group(1)) >= 5000 else "ØST"


def receive(enquiry, now=None, seq=1):
    """Turn a submitted enquiry into a case: id, region, SLA, per-item completeness and pre-check, triage."""
    now = now or datetime.datetime.now().replace(microsecond=0)
    year = now.year
    region = region_for((enquiry.get("project") or {}).get("address"))
    items = []
    for i, it in enumerate(enquiry.get("items") or [], 1):
        score, missing = completeness(it)
        v = precheck(it)
        triage = {"TESTET": "BESVARET_TESTET", "MANGLER_DATA": "MANGLER_INFO", "ANDET_SYSTEM": "ANDET_SYSTEM"}.get(v["status"], "TIL_VURDERING")
        if v["status"] in ("AFVIGELSE", "IKKE_DAEKKET") and score < 70:
            triage = "MANGLER_INFO"
        items.append({**it, "no": i, "completeness": score, "missing": missing, "verdict": v, "triage": triage})
    needs_adviser = any(x["triage"] in ("TIL_VURDERING", "MANGLER_INFO") for x in items)
    status = "MODTAGET" if needs_adviser else "BESVARET"
    if any(x["triage"] == "MANGLER_INFO" for x in items):
        status = "MANGLER_INFO"
    timeline = (enquiry.get("project") or {}).get("timeline", "Uafklaret")
    due = now + datetime.timedelta(days=SLA_DAYS.get(timeline, 10))
    return {"id": f"BV-{year}-{seq:04d}", "created": now.isoformat(), "due": due.date().isoformat(), "region": region,
            "office": REGIONS[region]["office"], "customer": enquiry.get("customer"), "project": enquiry.get("project"),
            "items": items, "status": status, "assignee": None, "events": []}
