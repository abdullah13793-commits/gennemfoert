"""Turn the Annex A tables of a penetration-seal ETA into tested-configuration records.

Each record is one row of an ETA table: the construction it was tested in, the service (pipe, cable, tray...),
its size, the insulation and wrap, the classification, and the seal limits. Every record keeps its page, section
and the row's rectangle on the page, so a match can always be shown next to its source.

Merged table cells mean "same as the row above", so blank cells are filled down within a table. Rows that the
PDF text layer garbles are replaced by hand-verified rows from data/eta/overrides.json (marked source="override").

python -m gennemfoert.eta  ->  data/eta/records.json
"""
import json
import re
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "eta" / "source" / "ETA-21-0110_Mulcol_Multimastic_C.pdf"
ETA_ID = "ETA-21/0110"
PRODUCT = "Mulcol Multimastic C System"

COLS = {  # header keyword -> field
    "services": "service", "classif": "classification", "position": "position", "insulation": "insulation",
    "multiwrap": "wrap", "seal": "seal", "between": "between", "edge": "edge", "position services": "position_services"}

# Construction per Annex A chapter (ETA section 2 and the chapter headings)
CHAPTER = {
    "1": {"hosts": ["flexible_wall", "rigid_wall"], "min_thickness": 100},
    "2": {"hosts": ["flexible_wall", "rigid_wall"], "min_thickness": 75},
    "3": {"hosts": ["rigid_wall"], "min_thickness": 150},
    "4": {"hosts": ["rigid_floor"], "min_thickness": 150},
}


def _clean(s):
    return re.sub(r"\s+", " ", (s or "").replace(" ", " ")).strip()


def _header_map(rows, start, ncols):
    """Join the header rows (from the 'Services' row until the first data row) per column."""
    texts = [""] * ncols
    i = start
    while i < len(rows):
        r = rows[i]
        if i > start and _clean(r[0]) and not _clean(r[0]).lower().startswith("services"):
            break
        for c in range(ncols):
            texts[c] += " " + _clean(r[c]).lower()
        i += 1
    fields = {}
    for c, t in enumerate(texts):
        t = t.replace("maxium", "maximum").replace("classificatio n", "classification")
        if "services" in t and "position" not in t:
            fields[c] = "service"
        elif "position services" in t or ("position" in t and "services" in t):
            fields[c] = "position_services"
        elif "classif" in t:
            fields[c] = "classification"
        elif "position" in t:
            fields[c] = "position"
        elif "insulation" in t:
            fields[c] = "insulation"
        elif "multiwrap" in t:
            fields[c] = "wrap"
        elif "between" in t:
            fields[c] = "between"
        elif "edge" in t or "minimum" in t:
            fields[c] = "edge"
        elif "seal" in t:
            fields[c] = "seal"
    return fields, i


def extract(pdf=SRC):
    """Raw rows per Annex A table, filled down, with page, section and row rectangle."""
    doc = pymupdf.open(pdf)
    out = []
    for pno in range(8, doc.page_count + 1):
        page = doc[pno - 1]
        tabs = page.find_tables().tables
        if not tabs:
            continue
        t = max(tabs, key=lambda t: t.row_count)
        rows = t.extract()
        title = next((_clean(c) for r in rows for c in r if c and re.search(r"A\s?\d+(\.\d+)+\s+Multimastic", c)), "")
        m = re.search(r"A\s?(\d+(?:\.\d+)+)\s+(Multimastic.*)$", title)
        if not m:
            continue
        section, heading = m.group(1), m.group(2)
        hdr = next((i for i, r in enumerate(rows) if _clean(r[0]).lower().startswith("services")
                    or any(_clean(c).lower().startswith("services") for c in r[:2])), None)
        if hdr is None:
            continue
        fields, first = _header_map(rows, hdr, t.col_count)
        graph = re.search(r"graph on page (\d+)", " ".join(_clean(c) for r in rows for c in r if c))
        prev = {}
        for i in range(first, len(rows)):
            r = rows[i]
            vals = {}
            for c, f in fields.items():
                v = _clean(r[c])
                if v and f not in vals:
                    vals[f] = v
                elif v:
                    vals[f] += " " + v
            if not vals or (vals.get("service", "").lower().startswith("see graph")):
                continue
            if all(not v for v in vals.values()):
                continue
            row = {f: vals.get(f) or prev.get(f, "") for f in set(fields.values())}
            prev = row
            rb = t.rows[i].bbox if i < len(t.rows) else None
            out.append({"page": pno, "section": section, "heading": heading, "graph_page": int(graph.group(1)) if graph else None,
                        "row_bbox": [round(v, 1) for v in rb] if rb else None, "table_bbox": [round(v, 1) for v in t.bbox],
                        "source": "pdf", **row})
    return out


# ------------------------------------------------------------------ parsing into structured records
MATERIALS = [(r"stainless steel|steel pipe", "steel"), (r"copper pipe", "copper"), (r"pvc-u|upvc", "pvc-u"),
             (r"\bpe pipe", "pe"), (r"\bpp pipe", "pp"), (r"alupex|composite pipe", "composite"),
             (r"pvc conduit", "pvc_conduit"), (r"steel conduit", "steel_conduit"), (r"copper conduit", "copper_conduit")]


def parse_service(s):
    t = s.lower()
    d = {"text": s}
    if t.startswith("blank"):
        d.update(kind="blank")
        return d
    if t.startswith("steel cable tray") or "& ladder" in t:
        d.update(kind="cable_tray")
        return d
    if "wire" in t:
        m = re.search(r"up to (\d+(?:\.\d+)?)\s*mm", t)
        d.update(kind="wires", od_max=float(m.group(1)) if m else None)
        return d
    if "cable" in t and "conduit" not in t:
        m = re.search(r"up to (\d+(?:\.\d+)?)\s*mm", t)
        if "tied bundles" in t:
            b = re.search(r"bundles up to (\d+)", t)
            d.update(kind="cable_bundle", od_max=float(m.group(1)) if m else None, bundle_max=float(b.group(1)) if b else None)
        else:
            if m is None:
                m = re.search(r"(\d+(?:\.\d+)?)\s*mm\s*$", t) or re.search(r"and (\d+(?:\.\d+)?)", t)
            d.update(kind="cable", od_max=float(m.group(1)) if m else 14.0)
        return d
    for pat, mat in MATERIALS:
        if re.search(pat, t):
            d["material"] = mat
            break
    d["kind"] = "conduit" if "conduit" in t else "pipe"
    m = re.search(r"(?:up to\s*)?(?:Ø\s*)?(\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?\s*mm\s*/\s*(\d+(?:\.\d+)?)\.?(?:\s*-\s*(\d+(?:\.\d+)?))?\s*mm", s, re.I)
    if m:
        a, b, w1, w2 = m.groups()
        up_to = "up to" in t
        d["od_min"] = 0.0 if up_to else float(a) if b else float(a)
        d["od_max"] = float(b) if b else float(a)
        if b and not up_to:
            d["od_min"] = float(a)
        d["wall_min"] = float(w1)
        d["wall_max"] = float(w2) if w2 else float(w1)
    else:
        m = re.search(r"up to (\d+(?:\.\d+)?)\s*mm", t)
        if m:
            d.update(od_min=0.0, od_max=float(m.group(1)))
    return d


def parse_class(s):
    """'E 90 C/U, EI 60 C/U' -> {'E': 90, 'EI': 60, 'config': 'C/U'}  ('EI 120' implies E 120)."""
    s = s.replace(",", " , ")
    e = [int(x) for x in re.findall(r"(?<![I\w])E\s*(\d+)", s)]
    ei = [int(x) for x in re.findall(r"EI\s*(\d+)", s)]
    cfg = re.search(r"\b([UC]/[UC])\b", s)
    E = max(e + ei) if (e or ei) else None
    return {"E": E, "EI": max(ei) if ei else None, "config": cfg.group(1) if cfg else None, "text": _clean(s.replace(" , ", ", "))}


def parse_insulation(s, heading):
    t = (s or "").lower()
    if not t or t in ("none", "not required"):
        return {"type": "none", "text": s or "None"}
    d = {"text": s}
    if "stone wool" in t or "stone" in t:
        d["type"] = "stone_wool"
    elif "kaiflex" in t or "elastomeric" in t or "pe foam" in t:
        d["type"] = "elastomeric"
    elif "multitherm" in t:
        d["type"] = "multitherm"
    else:
        d["type"] = "other"
    m = re.search(r"(\d+(?:\.\d+)?)\s*mm length of", t)
    if m:
        d["length"] = float(m.group(1))
        t = t[m.end():]
    m = re.search(r"(\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?\s*mm", t)
    if m:
        d["t_min"] = float(m.group(1))
        d["t_max"] = float(m.group(2) or m.group(1))
    h = heading.lower()
    d["extent"] = "local" if "length" in d else ("CS" if "(cs)" in h or "insulated cs" in h else "CS")
    return d


def parse_seal(s):
    t = (s or "").lower()
    if not t:
        return None
    m = re.search(r"(\d+)\s*x\s*(\d+)", t)
    if "unlimited" in t:
        h = re.search(r"x\s*(\d+)", t)
        return {"w": None, "h": float(h.group(1)) if h else 1200.0, "text": s}
    if m:
        return {"w": float(m.group(1)), "h": float(m.group(2)), "text": s}
    return {"text": s}


def parse_mm(s):
    m = re.search(r"(\d+(?:\.\d+)?)", s or "")
    return float(m.group(1)) if m else None


def board_of(heading):
    m = re.search(r"(FB[12])\s*-\s*(\d)x(\d+)\s*mm", heading)
    return {"type": m.group(1), "layers": int(m.group(2)), "thickness": int(m.group(3))} if m else None


def to_record(i, r):
    chap = CHAPTER[r["section"].split(".")[0]]
    rec = {
        "id": f"{ETA_ID}/A{r['section']}/{i:03d}", "eta": ETA_ID, "product": PRODUCT, "section": "A." + r["section"],
        "heading": r["heading"], "page": r["page"], "graph_page": r.get("graph_page"), "source": r.get("source", "pdf"),
        "row_bbox": r.get("row_bbox"), "table_bbox": r.get("table_bbox"),
        "hosts": chap["hosts"], "min_thickness": chap["min_thickness"], "board": board_of(r["heading"]),
        "service": parse_service(r["service"]), "classification": parse_class(r["classification"]),
        "insulation": parse_insulation(r.get("insulation"), r["heading"]),
        "wrap": r.get("wrap") or None, "position": r.get("position") or r.get("position_services") or None,
        "seal_max": parse_seal(r.get("seal")), "edge_min": parse_mm(r.get("edge") or r.get("position_services")),
        "between_min": parse_mm(r.get("between")),
    }
    return rec


def build():
    raw = extract()
    ov = json.loads((ROOT / "data" / "eta" / "overrides.json").read_text(encoding="utf-8"))
    pages_over = {int(p) for p in ov["pages"]}
    raw = [r for r in raw if r["page"] not in pages_over]
    doc = pymupdf.open(SRC)
    for p, spec in ov["pages"].items():
        prev = {}
        for row in spec["rows"]:
            row = {**prev, **row}
            prev = row
            hits = doc[int(p) - 1].search_for(row["find"]) if row.get("find") else []
            n = row.get("nth", 0)
            rb = None
            if len(hits) > n:
                h = hits[n]
                tb = doc[int(p) - 1].find_tables().tables
                x1 = max(t.bbox[2] for t in tb) if tb else h.x1
                rb = [round(h.x0 - 60, 1), round(h.y0 - 2, 1), round(x1, 1), round(h.y1 + 2, 1)]
            raw.append({"page": int(p), "section": spec["section"], "heading": spec["heading"], "graph_page": spec.get("graph_page"),
                        "row_bbox": rb, "table_bbox": None, "source": "override",
                        **{k: v for k, v in row.items() if k not in ("find", "nth")}})
            prev.pop("find", None), prev.pop("nth", None)
    raw.sort(key=lambda r: (r["page"], (r["row_bbox"] or [0, 0])[1]))
    recs = [to_record(i, r) for i, r in enumerate(raw)]
    return recs


if __name__ == "__main__":
    recs = build()
    out = ROOT / "data" / "eta" / "records.json"
    out.write_text(json.dumps(recs, indent=1, ensure_ascii=False), encoding="utf-8")
    kinds = {}
    for r in recs:
        kinds[r["service"]["kind"]] = kinds.get(r["service"]["kind"], 0) + 1
    print(len(recs), "records;", kinds, "; sections:", len({r["section"] for r in recs}))
