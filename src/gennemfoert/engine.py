"""Valid-as-tested engine: compare one penetration with every tested configuration in the ETA records.

Result statuses (Danish, as used in the register):
  TESTET          an ETA row matches every parameter: the seal is valid as tested (with the conditions listed)
  AFVIGELSE       the nearest tested row differs in one or two parameters: needs a brandteknisk vurdering
                  or a change; the deviating parameters and the nearest rows are named
  IKKE_DAEKKET    no tested row for this service in this construction: choose another system or assess
  ANDET_SYSTEM    the service is outside the scope of a penetration-seal ETA (ventilation ducts: fire damper or
                  duct fire insulation)
  MANGLER_DATA    the model does not say enough to decide; the missing items are returned as questions

Every check carries the ETA page, so a person can confirm it against the source in seconds.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECORDS = json.loads((ROOT / "data" / "eta" / "records.json").read_text(encoding="utf-8"))

MAT = {"pvc-u": "pvc-u", "pvc": "pvc-u", "upvc": "pvc-u", "pp": "pp", "pe": "pe", "pe-hd": "pe", "kobber": "copper",
       "copper": "copper", "cu": "copper", "stål": "steel", "steel": "steel", "rustfrit stål": "steel", "stainless steel": "steel",
       "alupex": "composite", "pex-al-pex": "composite", "composite": "composite"}
PLASTIC = {"pvc-u", "pe", "pp", "composite"}
COVERS = {"U/U": {"U/U", "C/U", "U/C", "C/C"}, "C/U": {"C/U", "C/C"}, "U/C": {"U/C", "C/C"}, "C/C": {"C/C"}}
CHANGEABLE = {"isoleringstype", "isoleringstykkelse", "isoleringsfabrikat", "hulstørrelse", "kantafstand", "fyldningsgrad"}
SEPARATION_MIN = 200.0     # ETA-21/0110 section 2, item 5
FILL_MAX = 0.60            # ETA-21/0110 section 2, item 4
BRANDS = ("kaiflex", "multitherm")
HOST_DA = {"rigid_wall": "massiv væg", "flexible_wall": "let væg", "rigid_floor": "massivt dæk"}
INS_DA = {"none": "ingen", "stone_wool": "stenuld", "elastomeric": "elastomer", "multitherm": "Multitherm", "other": "anden"}


def norm_material(name):
    if not name:
        return None
    n = name.lower()
    for k in sorted(MAT, key=len, reverse=True):
        if k in n:
            return MAT[k]
    return None


def norm_insulation(ins):
    """None -> none; {'product','category','thickness_mm'} -> type/thickness/product."""
    if not ins:
        return {"type": "none"}
    cat = (ins.get("category") or ins.get("type") or ins.get("product") or "").lower()
    if "sten" in cat or "stone" in cat or "mineral" in cat:
        t = "stone_wool"
    elif "elast" in cat or "kaiflex" in cat or "armaflex" in cat or "gummi" in cat:
        t = "elastomeric"
    elif "multitherm" in cat:
        t = "multitherm"
    elif cat in ("none", "ingen"):
        t = "none"
    else:
        t = "other"
    return {"type": t, "thickness_mm": ins.get("thickness_mm"), "product": ins.get("product"), "extent": ins.get("extent", "continuous")}


def required_config(material, open_system):
    if open_system is None or material is None:
        return None
    if material in PLASTIC:
        return "U/C" if open_system else "C/C"
    return "U/U" if open_system else "C/U"


def _graph_neighbours():
    """For steel tables with an intermediate-size graph: the next listed Ø in the same group."""
    groups = {}
    for r in RECORDS:
        s = r["service"]
        if r.get("graph_page") and s.get("material") == "steel" and s.get("od_min") == s.get("od_max"):
            key = (r["section"], r["classification"]["text"], r["insulation"]["text"])
            groups.setdefault(key, []).append(r)
    nxt = {}
    for rows in groups.values():
        rows = sorted({r["service"]["od_max"]: r for r in rows}.values(), key=lambda r: r["service"]["od_max"])
        for a, b in zip(rows, rows[1:]):
            nxt[a["id"]] = b
    return nxt


NEXT = _graph_neighbours()


def _fmt(v):
    return "–" if v is None else (f"{v:g}" if isinstance(v, (int, float)) else str(v))


def check(rec, q):
    """All checks of one record against one query. Returns a list of (name, ok, actual, tested, note)."""
    s, c, ins = rec["service"], rec["classification"], rec["insulation"]
    out = []

    def add(name, ok, actual, tested, note=None):
        out.append({"check": name, "ok": ok, "actual": actual, "tested": tested, "note": note})

    add("konstruktion", q["host_kind"] in rec["hosts"], HOST_DA.get(q["host_kind"], q["host_kind"]),
        " / ".join(HOST_DA[h] for h in rec["hosts"]))
    add("tykkelse", (q.get("thickness_mm") or 0) >= rec["min_thickness"], f"{_fmt(q.get('thickness_mm'))} mm", f"≥ {rec['min_thickness']} mm")
    kind = q["service_kind"]
    if kind in ("pipe", "conduit"):
        od, lo, hi = q.get("od_mm"), s.get("od_min"), s.get("od_max")
        note, wall_min = None, s.get("wall_min")
        ok = od is not None and lo is not None and lo - 0.05 <= od <= hi + 0.05
        nb = NEXT.get(rec["id"])
        if not ok and od is not None and nb and hi < od < nb["service"]["od_max"]:
            f_ = (od - hi) / (nb["service"]["od_max"] - hi)
            wall_min = round(s["wall_min"] + f_ * (nb["service"]["wall_min"] - s["wall_min"]), 2)
            ok, note = True, f"mellemstørrelse via grafen s. {rec['graph_page']} (min. godstykkelse {wall_min:g} mm)"
        tested = f"Ø {_fmt(hi)}" if lo == hi else (f"Ø ≤ {_fmt(hi)}" if not lo else f"Ø {_fmt(lo)}-{_fmt(hi)}")
        add("diameter", ok, f"Ø {_fmt(od)} mm", tested + " mm", note)
        if s.get("wall_min") is not None:
            w = q.get("wall_mm")
            wmax = s.get("wall_max")
            okw = w is not None and wall_min - 0.05 <= w <= wmax + 0.05
            add("godstykkelse", okw, f"{_fmt(w)} mm", f"{_fmt(wall_min)}" + (f"-{_fmt(wmax)}" if wmax != wall_min else "") + " mm")
    elif kind in ("cable", "cable_bundle", "wires"):
        od = q.get("od_mm")
        add("diameter", od is not None and s.get("od_max") is not None and od <= s["od_max"], f"Ø {_fmt(od)} mm", f"≤ {_fmt(s.get('od_max'))} mm")
        if kind == "cable_bundle" and s.get("bundle_max"):
            b = q.get("bundle_mm")
            add("bundtdiameter", b is not None and b <= s["bundle_max"], f"Ø {_fmt(b)} mm", f"≤ {_fmt(s['bundle_max'])} mm")
    # insulation
    qi = q.get("insulation") or {"type": "none"}
    if kind in ("pipe", "conduit"):
        add("isoleringstype", qi["type"] == ins["type"], INS_DA.get(qi["type"], qi["type"]), INS_DA.get(ins["type"], ins["type"]))
        if ins["type"] != "none":
            t = qi.get("thickness_mm")
            add("isoleringstykkelse", t is not None and ins.get("t_min", 0) - 0.5 <= t <= ins.get("t_max", 0) + 0.5,
                f"{_fmt(t)} mm", f"{_fmt(ins.get('t_min'))}" + (f"-{_fmt(ins.get('t_max'))}" if ins.get("t_max") != ins.get("t_min") else "") + " mm")
            brand = next((b for b in BRANDS if b in ins["text"].lower()), None)
            if brand:
                prod = (qi.get("product") or "")
                add("isoleringsfabrikat", brand in prod.lower(), prod or "ukendt", ins["text"])
    # classification and pipe ends
    ei = c.get("EI")
    add("klassifikation", ei is not None and ei >= (q.get("ei_required") or 0), f"EI {_fmt(q.get('ei_required'))} krævet", c["text"])
    if c.get("config") and kind in ("pipe", "conduit"):
        need = required_config(q.get("material"), q.get("open_system"))
        add("rørende", need is not None and need in COVERS[c["config"]], need or "ukendt (åbent/lukket system?)", c["config"],
            "åbent system (afløb/ventilation)" if q.get("open_system") else "lukket system (brugsvand/varme)" if q.get("open_system") is not None else None)
    # installation geometry
    ap = q.get("aperture_mm")
    seal = rec.get("seal_max") or {}
    if ap and seal.get("h"):
        big, small = max(ap), min(ap)
        sw, sh = seal.get("w") or 1e9, seal["h"]
        add("hulstørrelse", big <= max(sw, sh) + 1 and small <= min(sw, sh) + 1, f"{ap[0]} x {ap[1]} mm", seal.get("text"))
    if q.get("edge_mm") is not None and rec.get("edge_min"):
        add("kantafstand", q["edge_mm"] >= rec["edge_min"], f"{_fmt(q['edge_mm'])} mm", f"≥ {_fmt(rec['edge_min'])} mm")
    if q.get("separation_mm") is not None:
        need = rec.get("between_min") or SEPARATION_MIN
        add("afstand mellem tætninger", q["separation_mm"] >= need, f"{_fmt(q['separation_mm'])} mm", f"≥ {need:g} mm (ETA afsnit 2, pkt. 5)")
    if q.get("fill") is not None:
        add("fyldningsgrad", q["fill"] <= FILL_MAX, f"{q['fill'] * 100:.0f} %", "≤ 60 % (ETA afsnit 2, pkt. 4)")
    return out


def candidates(q):
    kind = q["service_kind"]
    kinds = {kind}
    if kind == "cable_bundle":
        kinds |= {"cable"}
    out = []
    for r in RECORDS:
        s = r["service"]
        if s["kind"] not in kinds:
            continue
        if kind == "cable_bundle" and s["kind"] == "cable" and "bundled" not in s["text"].lower():
            continue
        if kind in ("pipe", "conduit"):
            if norm_material(s.get("material") or "") != q.get("material") and s.get("material") != q.get("material"):
                continue
        out.append(r)
    return out


def missing(q):
    m = []
    if q["service_kind"] in ("pipe", "conduit"):
        if not q.get("material"):
            m.append("Hvilket rørmateriale (fx PVC-U, PP, PE, kobber, stål, Alupex)?")
        if not q.get("od_mm"):
            m.append("Rørets udvendige diameter (mm)?")
        if q.get("wall_mm") is None:
            m.append("Rørets godstykkelse (mm)?")
        if q.get("open_system") is None:
            m.append("Er systemet åbent (afløb) eller lukket (brugsvand/varme)?")
        if q.get("insulation_unknown"):
            m.append("Er røret isoleret? Type, fabrikat og tykkelse?")
    if not q.get("ei_required"):
        m.append("Hvilken brandmodstand kræves for væggen/dækket (fx EI 60)?")
    if not q.get("thickness_mm"):
        m.append("Væggens/dækkets tykkelse og opbygning?")
    return m


def evaluate(q):
    """Main entry: one penetration (as a query dict) -> verdict with checks and citations."""
    res = {"status": None, "matches": [], "nearest": [], "alternatives": [], "conditions": [], "questions": []}
    if q["service_kind"] in ("duct",):
        res["status"] = "ANDET_SYSTEM"
        res["conditions"].append("Ventilationskanal: brandspjæld eller brandisolering af kanalen (fx ROCKWOOL Conlit) efter dennes "
                                 "dokumentation. Ikke omfattet af en gennemføringstætning efter ETA-21/0110.")
        return res
    miss = missing(q)
    if miss:
        res["status"] = "MANGLER_DATA"
        res["questions"] = miss
        return res
    scored = []
    for r in candidates(q):
        ch = check(r, q)
        fails = [c["check"] for c in ch if not c["ok"]]
        scored.append((r, ch, fails))
    full = [x for x in scored if not x[2]]

    def size_gap(r):
        od, s = q.get("od_mm"), r["service"]
        if od is None or s.get("od_max") is None:
            return 0.0
        lo = s.get("od_min") or 0.0
        return 0.0 if lo <= od <= s["od_max"] else min(abs(od - lo), abs(od - s["od_max"])) / od

    rank = lambda x: (len(x[2]), round(size_gap(x[0]), 3), (x[0]["board"] or {}).get("layers", 9),
                      -(x[0]["classification"].get("EI") or 0), x[0]["page"])
    if full:
        res["status"] = "TESTET"
        res["matches"] = [_brief(r, ch) for r, ch, _ in sorted(full, key=rank)]
    else:
        close = [x for x in scored if "konstruktion" not in x[2] and "tykkelse" not in x[2] and len(x[2]) <= 2]
        if close:
            res["status"] = "AFVIGELSE"
            res["nearest"] = [_brief(r, ch, fails) for r, ch, fails in sorted(close, key=rank)[:3]]
        else:
            res["status"] = "IKKE_DAEKKET"
            same_host = [x for x in scored if "konstruktion" not in x[2] and "tykkelse" not in x[2]]
            res["nearest"] = [_brief(r, ch, fails) for r, ch, fails in sorted(same_host, key=rank)[:2]]
        alt = [x for x in scored if x[2] and set(x[2]) <= CHANGEABLE and "konstruktion" not in x[2]]
        res["alternatives"] = [_brief(r, ch, fails) for r, ch, fails in sorted(alt, key=rank)[:2]]
    # standing conditions
    best = res["matches"][0] if res["matches"] else None
    if best and best.get("insulation_length"):
        res["conditions"].append(f"Testet med lokal isolering: min. {best['insulation_length']:g} mm længde ({best['section']}).")
    if best and best.get("wrap"):
        res["conditions"].append(f"Mulcol Multiwrap: {best['wrap']} ({best['section']}).")
    if best and best.get("board"):
        res["conditions"].append(f"Tætning: Multimastic {best['board']}, Multimastic C (≤ 1 mm) og Multimastic SP i kanten ({best['section']}, s. {best['page']}).")
    if q.get("hollow_core"):
        res["conditions"].append("Huldæk: ETA'en forudsætter dæk af beton/letbeton ≥ 150 mm og ≥ 650 kg/m³. Kontrollér placering i forhold "
                                 "til huldækkets kanaler og ribber.")
    if q["host_kind"] == "rigid_floor":
        res["conditions"].append("Installationer i dæk understøttes 250 mm og 400 mm fra dækkets overside (ETA afsnit 2, pkt. 6).")
    elif q["service_kind"] in ("pipe", "conduit", "cable", "cable_bundle"):
        res["conditions"].append("Installationer i væg understøttes 270 mm og 470 mm fra begge sider af væggen (ETA afsnit 2, pkt. 6).")
    return res


def _brief(r, checks, fails=None):
    b = r["board"]
    return {"id": r["id"], "eta": r["eta"], "section": r["section"], "page": r["page"], "heading": r["heading"],
            "service": r["service"]["text"], "classification": r["classification"]["text"], "insulation": r["insulation"]["text"],
            "insulation_length": r["insulation"].get("length"), "wrap": r.get("wrap") if r.get("wrap") not in ("Not required",) else None,
            "board": f"{b['type']} {b['layers']}x{b['thickness']} mm" if b else None, "seal": (r.get("seal_max") or {}).get("text"),
            "row_bbox": r.get("row_bbox"), "source": r["source"], "checks": checks, "deviates": fails or []}


def query_from_penetration(p):
    s, h = p["service"], p["host"]
    od = s.get("od_mm")
    ins = s.get("insulation")
    q = {"host_kind": h["kind"], "thickness_mm": h["thickness_mm"], "ei_required": h["ei_required"], "hollow_core": h.get("hollow_core"),
         "service_kind": s["kind"], "material": norm_material(s.get("material")), "od_mm": od, "wall_mm": s.get("wall_mm"),
         "bundle_mm": s.get("bundle_mm"), "open_system": s.get("open_system"), "insulation": norm_insulation(ins),
         "aperture_mm": p.get("aperture_mm"), "separation_mm": p.get("separation_mm")}
    if s["kind"] == "cable_tray":
        tot_w, tot_h = s.get("width_mm") or 0, s.get("height_mm") or 0
        area = tot_w * tot_h
        dia = max(tot_w, tot_h)
    else:
        t = (ins or {}).get("thickness_mm") or 0
        dia = (s.get("bundle_mm") or od or 0) + 2 * t
        area = math.pi * dia * dia / 4
    if p.get("aperture_mm"):
        w, h2 = p["aperture_mm"]
        q["edge_mm"] = round((min(w, h2) - (min(tot_w, tot_h) if s["kind"] == "cable_tray" else dia)) / 2)
        q["fill"] = round(area / (w * h2), 3) if w * h2 else None
    return q
