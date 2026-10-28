"""Demonstration data for the workflow: enquiries over 12 weeks run through intake, triage, decisions, four-eyes review
and issue, plus a precedent library, issued PDFs and a verification index. Everything here is FICTITIOUS example data
(customers, addresses, decisions, arguments) made to show the process; it is not anybody's real case history.

python -m gennemfoert.demo
"""
import copy
import datetime
import json
import random
from pathlib import Path

from . import cases, engine, intake, precedents, report

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "results"
SEED = 2026

DECK = {"kind": "rigid_floor", "label": "Huldæk, beton", "thickness_mm": 220, "ei_required": 60, "hollow_core": True}
WALL150 = {"kind": "rigid_wall", "label": "Betonvæg", "thickness_mm": 150, "ei_required": 60}
GYPS = {"kind": "flexible_wall", "label": "Skaktvæg, 2x12,5 mm gips pr. side på stålskelet", "thickness_mm": 100, "ei_required": 60}
TEMPLATES = [
    ("PVC-afløb 110x3,2 i huldæk", DECK, {"kind": "pipe", "label": "Faldstamme PVC-U", "material": "PVC-U", "od_mm": 110, "wall_mm": 3.2, "system": "open"}, [220, 220]),
    ("PP-afløb 50x1,8 i let skaktvæg", GYPS, {"kind": "pipe", "label": "Afløbsgren PP", "material": "PP", "od_mm": 50, "wall_mm": 1.8, "system": "open"}, [80, 80]),
    ("Kobber 22x1 med Armaflex 13 i dæk", DECK, {"kind": "pipe", "label": "Brugsvand koldt, kobber", "material": "kobber", "od_mm": 22, "wall_mm": 1.0,
                                                  "system": "closed", "insulation": {"category": "elastomer", "product": "Armaflex AF", "thickness_mm": 13}}, [220, 220]),
    ("Stål 60,3 med stenuld 30 i betonvæg", WALL150, {"kind": "pipe", "label": "Varmerør, stål", "material": "stål", "od_mm": 60.3, "wall_mm": 2.9,
                                                       "system": "closed", "insulation": {"category": "stenuld", "product": "Stenuld rørskål", "thickness_mm": 30}}, [260, 260]),
    ("Kobber 28x1 med stenuld 30 i dæk", DECK, {"kind": "pipe", "label": "Brugsvand varmt, kobber", "material": "kobber", "od_mm": 28, "wall_mm": 1.0,
                                                 "system": "closed", "insulation": {"category": "stenuld", "product": "Stenuld rørskål", "thickness_mm": 30}}, [220, 220]),
    ("PE 160 kloak i dæk, EI 90", {**DECK, "ei_required": 90}, {"kind": "pipe", "label": "Kloak PE", "material": "PE", "od_mm": 160, "wall_mm": 6.2,
                                                                  "system": "open"}, [300, 300]),
    ("Kabelbundt i betonvæg", {**WALL150, "thickness_mm": 200}, {"kind": "cable_bundle", "label": "Kabelbundt", "od_mm": 16, "bundle_mm": 80}, [200, 200]),
    ("Ventilationskanal Ø160 i skaktvæg", GYPS, {"kind": "duct", "label": "Ventilationskanal", "od_mm": 160}, [240, 240]),
    ("Alupex 16 i let væg", GYPS, {"kind": "pipe", "label": "Gulvvarme Alupex", "material": "Alupex", "od_mm": 16, "wall_mm": 2.25, "system": "closed"}, [40, 40]),
    ("PVC 125 i dæk, EI 90", {**DECK, "ei_required": 90}, {"kind": "pipe", "label": "Faldstamme PVC-U", "material": "PVC-U", "od_mm": 125, "wall_mm": 3.9,
                                                            "system": "open"}, [220, 220]),
    ("PP 75x2,6 i dæk", DECK, {"kind": "pipe", "label": "Faldstamme PP", "material": "PP", "od_mm": 75, "wall_mm": 2.6, "system": "open"}, [220, 220]),
    ("Rør uden oplysninger", WALL150, {"kind": "pipe", "label": "Rør (ukendt)", "od_mm": 22}, None),
]
CUSTOMERS = ["Nordvest VVS ApS", "Østkyst Isolering A/S", "Byggefirmaet Kronborg", "Jysk Teknik & Rør", "Fyns Installation ApS",
             "Amager Entreprise A/S", "Hovedstadens Boligbyg", "Kolding Klima ApS", "Midtjysk Isolering", "Sjællands Rådgivende Ingeniører"]
STREETS = ["Lindevej", "Skolegade", "Havnevej", "Engvej", "Stationsvej", "Kirkevej", "Parkvej", "Bakkevej"]
TOWNS = [("2750", "Ballerup"), ("2300", "København S"), ("4000", "Roskilde"), ("3400", "Hillerød"), ("6000", "Kolding"), ("8000", "Aarhus C"),
         ("5000", "Odense C"), ("7100", "Vejle"), ("2610", "Rødovre"), ("8700", "Horsens")]
TYPES = ["Bolig / etageejendom", "Institution (skole, plejehjem mv.)", "Erhverv / kontor", "Bolig / etageejendom"]
ARGS = {  # fictitious example arguments, written the way an adviser would, for the demo only
    "godstykkelse:tyndere": "EKSEMPEL. Røret er tyndvægget i forhold til den testede række. Afvigelsen er vurderet på baggrund af nærmeste testede "
                            "dimensioner i samme tabel og manchettens lukkevirkning; løsningen accepteres på de anførte betingelser.",
    "isoleringsfabrikat:andet fabrikat": "EKSEMPEL. Isoleringen er af samme materialetype og tykkelse som testet, men andet fabrikat. Ligeværdighed er "
                                         "dokumenteret med fabrikatets brandklasse; alternativt skiftes til det testede fabrikat.",
    "diameter:større": "EKSEMPEL. Dimensionen ligger over det testede område. Der anvises i stedet den testede løsning med det alternative system.",
    "klassifikation:lavere": "EKSEMPEL. Den testede klassifikation er lavere end kravet; løsningen kan ikke godkendes som projekteret.",
}


def enquiry(rng, n_items):
    zipc, town = rng.choice(TOWNS)
    items = []
    for t in rng.sample(TEMPLATES, n_items):
        name, c, s, ap = t
        it = {"title": name, "construction": copy.deepcopy(c), "service": copy.deepcopy(s), "aperture_mm": ap, "quantity": rng.choice([1, 2, 3, 4, 6, 8])}
        if rng.random() < 0.7:
            it["photos"] = {k: True for k in intake.PHOTOS if rng.random() < 0.85}
        if rng.random() < 0.12 and it["service"].get("wall_mm"):
            it["service"].pop("wall_mm")
        items.append(it)
    return {"customer": {"company": rng.choice(CUSTOMERS), "contact": "Kontaktperson", "email": "kontakt@example.dk", "phone": "00 00 00 00"},
            "project": {"address": f"{rng.choice(STREETS)} {rng.randint(2, 90)}, {zipc} {town}", "building_type": rng.choice(TYPES),
                        "timeline": rng.choice(list(intake.SLA_DAYS))}, "items": items}


def precedent_library(rng):
    lib = []
    for i, (name, c, s, ap) in enumerate(TEMPLATES):
        it = {"construction": c, "service": s, "aperture_mm": ap}
        q = intake.item_query(it)
        v = engine.evaluate(q) if q["host_kind"] and q["service_kind"] else None
        if not v or v["status"] != "AFVIGELSE" or not v["nearest"]:
            continue
        sig = precedents.signature(q, v["nearest"][0])
        k = precedents.key(q, sig)
        param = k["params"][0] if k["params"] else ""
        decision = "AFVIST" if param.startswith("klassifikation") else ("BETINGET" if param in ARGS else "BETINGET")
        lib.append({"id": f"P-2025-{100 + i}", "title": name, "key": k, "signature": sig, "section": v["nearest"][0]["section"],
                    "eta": v["nearest"][0]["eta"], "decision": decision, "argument": ARGS.get(param, ARGS["godstykkelse:tyndere"]),
                    "conditions": ["Udførelse efter producentens monteringsvejledning", "Fotodokumentation pr. gennemføring"],
                    "author": "Rådgiver Øst 1", "date": f"2025-{rng.randint(3, 11):02d}-{rng.randint(1, 28):02d}", "demo": True})
    return lib


def simulate(rng, n=30, start=datetime.datetime(2026, 8, 3, 8, 0)):
    kb = report.kb_version()
    out = []
    for k in range(n):
        t0 = start + datetime.timedelta(days=int(k * 84 / n), hours=rng.randint(0, 8))
        cs = intake.receive(enquiry(rng, rng.choice([1, 1, 2, 2, 3])), now=t0, seq=142 + k)
        cases.log(cs, "kunde", "forespørgsel_modtaget", {"items": len(cs["items"])}, kb, t0)
        adv = intake.REGIONS[cs["region"]]["advisers"]
        a1 = rng.choice(adv)
        a2 = next((a for a in adv if a != a1), "Rådgiver Vest 2" if cs["region"] == "VEST" else "Rådgiver Øst 2")
        cs["assignee"] = a1
        t = t0 + datetime.timedelta(hours=rng.randint(1, 20))
        if cs["status"] == "BESVARET":
            cases.log(cs, "system", "besvaret_testet", {"items": [i["no"] for i in cs["items"]]}, kb, t)
        else:
            if cs["status"] == "MANGLER_INFO":
                cases.log(cs, a1, "spørgsmål_sendt", {"questions": sum(len(i["missing"]) for i in cs["items"])}, kb, t)
                t += datetime.timedelta(days=rng.randint(1, 4))
                cases.move(cs, "TIL_VURDERING", a1, {"svar": "kunde"}, kb, t)
            else:
                cases.move(cs, "TIL_VURDERING", a1, None, kb, t)
            for it in cs["items"]:
                if it["triage"] in ("TIL_VURDERING", "MANGLER_INFO") and it["verdict"]["status"] in ("AFVIGELSE", "IKKE_DAEKKET"):
                    q = intake.item_query(it)
                    hits, sig, kk = precedents.find(q, (it["verdict"]["nearest"] or [None])[0], LIB)
                    param = kk["params"][0] if kk["params"] else ""
                    d = "AFVIST" if param.startswith("klassifikation") or it["verdict"]["status"] == "IKKE_DAEKKET" else "BETINGET"
                    t += datetime.timedelta(hours=rng.randint(4, 30))
                    cases.decide(cs, it["no"], a1, d, ["Udførelse efter monteringsvejledningen", "Fotodokumentation pr. gennemføring"]
                                 if d == "BETINGET" else [], ARGS.get(param, ARGS["godstykkelse:tyndere"]), kb, t)
                    it["decision"]["precedents"] = [h["id"] for h in hits]
            if any(i.get("decision") for i in cs["items"]):
                cases.move(cs, "UDKAST", a1, None, kb, t)
                t += datetime.timedelta(hours=rng.randint(2, 30))
                cases.move(cs, "TIL_KONTROL", a1, None, kb, t)
                t += datetime.timedelta(hours=rng.randint(2, 40))
                cases.review(cs, a2, True, "Kontrolleret mod ETA og præcedens", kb, t)
                cases.move(cs, "UDSENDT", a2, None, kb, t)
        cs["closed"] = t.isoformat() if cs["status"] in ("UDSENDT", "BESVARET") else None
        if k >= n - 4:                       # the latest cases are still open
            cs["closed"] = None
        out.append(cs)
    return out


def dashboard(all_cases):
    items = [i for c in all_cases for i in c["items"]]
    from collections import Counter
    dev = Counter()
    for i in items:
        if i["verdict"].get("nearest") and i["verdict"]["status"] == "AFVIGELSE":
            for p in i["verdict"]["nearest"][0]["deviates"]:
                dev[p] += 1
    lead = []
    for c in all_cases:
        if c.get("closed"):
            lead.append((datetime.datetime.fromisoformat(c["closed"]) - datetime.datetime.fromisoformat(c["created"])).total_seconds() / 86400)
    weeks = Counter(datetime.date.fromisoformat(c["created"][:10]).isocalendar()[1] for c in all_cases)
    return {"cases": len(all_cases), "items": len(items),
            "triage": dict(Counter(i["triage"] for i in items)),
            "status": dict(Counter(c["status"] for c in all_cases)),
            "deflected_pct": round(100 * sum(i["triage"] == "BESVARET_TESTET" for i in items) / max(1, len(items))),
            "missing_info_pct": round(100 * sum(i["triage"] == "MANGLER_INFO" for i in items) / max(1, len(items))),
            "lead_days_median": round(sorted(lead)[len(lead) // 2], 1) if lead else None,
            "lead_days": [round(x, 1) for x in lead],
            "deviations": dict(dev.most_common()), "per_week": dict(sorted(weeks.items())),
            "regions": dict(Counter(c["region"] for c in all_cases)),
            "systems": dict(Counter((i["verdict"]["matches"] or i["verdict"]["nearest"] or [{"system": "-"}])[0].get("system") or "-" for i in items)),
            "chain_ok": all(cases.verify(c) for c in all_cases)}


LIB = []

if __name__ == "__main__":
    rng = random.Random(SEED)
    LIB = precedent_library(rng)
    (ROOT / "data" / "precedents.json").write_text(json.dumps(LIB, indent=1, ensure_ascii=False), encoding="utf-8")
    all_cases = simulate(rng)
    RES.mkdir(exist_ok=True)
    (RES / "cases.json").write_text(json.dumps(all_cases, indent=1, ensure_ascii=False), encoding="utf-8")
    dash = dashboard(all_cases)
    (RES / "dashboard.json").write_text(json.dumps(dash, indent=1, ensure_ascii=False), encoding="utf-8")
    issued = [c for c in all_cases if c["status"] == "UDSENDT"][:3]
    outdir = ROOT / "out" / "udstedte_vurderinger"
    outdir.mkdir(parents=True, exist_ok=True)
    verify = {}
    for c in [c for c in all_cases if c["status"] == "UDSENDT"]:
        for it in c["items"]:
            if it.get("decision"):
                code = report.verification_code(c, it)
                verify[code] = {"case": c["id"], "item": it["no"], "decision": it["decision"]["decision"], "issued": it["decision"]["at"][:10],
                                "valid": True, "kb": report.kb_version(), "title": it["title"]}
    for c in issued:
        for it in c["items"]:
            if it.get("decision"):
                report.build(c, it["no"], outdir / f"{c['id']}-{it['no']}.pdf")
    (RES / "verify.json").write_text(json.dumps(verify, indent=1, ensure_ascii=False), encoding="utf-8")
    print(len(LIB), "precedents;", dash["cases"], "cases;", dash["items"], "items; deflected", dash["deflected_pct"], "%; missing info",
          dash["missing_info_pct"], "%; median lead", dash["lead_days_median"], "d; chain ok", dash["chain_ok"], "; issued pdfs",
          len(list(outdir.glob("*.pdf"))), "; verify codes", len(verify))
