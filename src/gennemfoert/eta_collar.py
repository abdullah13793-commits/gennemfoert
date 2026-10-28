"""Tested configurations of ETA-20/1322 (Mulcol Multicollar Slim, fire collar) as records.

The ETA is a 248-page document: one drawing and one table per configuration, in two annexes (A: flexible or rigid
walls >= 100 mm, B: rigid floors >= 150 mm). Each table row is: pipe material, maximum pipe diameter, wall-thickness
range, insulation (type/extent/thickness/length), number of collars per face and classification. A row covers every
pipe up to its maximum diameter within its wall-thickness range ("Maximum pipe diameter"). Merged cells are filled
down; a row that only carries a classification continues the classification of the row above (e.g. "E 120 C/U" then
"EI 60 C/U").

The section heading sets what the table does not say: the configuration (perpendicular, angled, elbow, socket, zero
distance, corner, conduit, half shell, multiple pipes, flue gas, inside an FB1 board seal, cast in), the pipe family
and the insulation product ("insulated with AF/Armaflex ...").

python -m gennemfoert.eta_collar  ->  data/kb/multicollar.json
"""
import json
import re
from pathlib import Path

import pymupdf

from .eta import parse_class

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "eta" / "source" / "multicollar_eta.pdf"
ETA_ID, PRODUCT, SYSTEM = "ETA-20/1322", "Mulcol Multicollar Slim", "Multicollar Slim"
HEAD = re.compile(r"^([AB])\.(\d+(?:\.\d+)+)\s+(\S.*)$")
ANNEX = {"A": {"hosts": ["flexible_wall", "rigid_wall"], "min_thickness": 100},
         "B": {"hosts": ["rigid_floor"], "min_thickness": 150}}
MATERIAL = [(r"pvc-c", "pvc-c"), (r"pvc-u|(?<!\+)\bpvc\b", "pvc-u"), (r"pe-hd|\bpe\b", "pe"), (r"\babs\b", "abs"), (r"san\+pvc", "san+pvc"),
            (r"pp-r|pp-b|pp-rct", "pp-r"), (r"\bpp\b", "pp"), (r"copper", "copper"), (r"stainless", "steel"), (r"steel|iron", "steel"),
            (r"pe-rt/al|pe-x\w*/al|/al/|alu|composite|multilayer", "composite")]


def _clean(s):
    return re.sub(r"\s+", " ", (s or "").replace(" ", " ")).strip()


def configuration(h):
    t = h.lower()
    for key, val in [("flue gas", "flue"), ("coated board", "in_board"), ("cast into", "cast_in"), ("up to", "multiple"),
                     ("half shell", "half_shell"), ("zero distance", "zero_distance"), ("corner", "corner"),
                     ("angles 45", "angled"), ("elbow", "elbow"), ("socket", "socket"), ("coupling", "socket"),
                     ("pipes in pe conduit", "conduit"), ("in pe conduit", "conduit"), ("conduits containing", "conduit")]:
        if key in t:
            return val
    return "perpendicular"


def family(h):
    t = h.lower()
    if "electrical cable" in t or "cables" in t and "pipes" not in t:
        return "cable"
    if "pvc pipes containing electrical" in t or "conduits containing" in t:
        return "cable"
    if "(silent)" in t:
        return "silent"
    if "pp-r multilayer" in t:
        return "ppr"
    if "aluminium composite" in t:
        return "composite"
    if "metal pipes" in t:
        return "metal"
    if "flue gas" in t:
        return "flue"
    if "mixed pipes" in t:
        return "mixed"
    return "plastic"


def heading_insulation(h):
    t = h.lower()
    if "armaflex" in t:
        return {"type": "elastomeric", "product": "AF/Armaflex"}
    if "pir or pur" in t:
        return {"type": "pir", "product": None}
    if "pe-foam" in t or "pe foam" in t:
        return {"type": "pe_foam", "product": None}
    if "pe-conduit insulation" in t:
        return {"type": "pe_conduit", "product": None}
    return {"type": "none", "product": None}


def parse_insulation(cell, base):
    t = _clean(cell)
    if not t or t.lower() in ("none", "-"):
        return {"type": "none", "text": t or "None"} if base["type"] == "none" or t.lower() == "none" else {**base, "text": t or ""}
    d = {**base, "text": t}
    ext = re.findall(r"\b(LS|CS|LI|CI)\b", t)
    if ext:
        d["extent"] = ext
    tl = t.lower()
    if "armaflex" in tl:
        d.update(type="elastomeric", product="AF/Armaflex")
    elif "pe conduit" in tl:
        d.update(type="pe_conduit", product=None)
    elif "pe foam" in tl or "pe-foam" in tl:
        d.update(type="pe_foam", product=None)
    nums = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)", re.sub(r"\(min\.?\)", "", t))]
    m = re.search(r"(\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?\s*/\s*(\d+)", t)
    if m:
        d["t_min"], d["t_max"], d["length"] = float(m.group(1)), float(m.group(2) or m.group(1)), float(m.group(3))
    elif nums:
        m2 = re.search(r"(\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?", t)
        d["t_min"], d["t_max"] = float(m2.group(1)), float(m2.group(2) or m2.group(1))
    if d.get("type") == "none" and ("t_min" in d):
        d["type"] = "unknown"
    return d


def materials(cell):
    t = _clean(cell).lower()
    out = []
    for pat, m in MATERIAL:
        if re.search(pat, t) and m not in out:
            out.append(m)
    return out


def _cols(hdr_rows, ncols):
    texts = [""] * ncols
    for r in hdr_rows:
        for c in range(ncols):
            texts[c] += " " + _clean(r[c]).lower()
    cols = {}
    for c, t in enumerate(texts):
        if not t.strip():
            continue
        if "material" in t or "cable" in t and "type" in t:
            cols.setdefault("material", c)
        elif "diameter" in t:
            cols.setdefault("dmax", c)
        elif "wall" in t:
            cols.setdefault("wall", c)
        elif "insulation" in t:
            cols.setdefault("insulation", c)
        elif "collar" in t:
            cols.setdefault("collars", c)
        elif "classification" in t:
            cols.setdefault("cls", c)
    return cols


def extract(pdf=SRC):
    doc = pymupdf.open(pdf)
    section, heading = None, ""
    rows_out = []
    for pno in range(14, doc.page_count + 1):
        page = doc[pno - 1]
        lines = [l.strip() for l in page.get_text().splitlines()]
        for i, l in enumerate(lines):
            m = HEAD.match(l)
            if m and len(m.group(2).split(".")) >= 3:            # A.1.1.1-level headings carry the configuration
                nxt = lines[i + 1] if i + 1 < len(lines) and not HEAD.match(lines[i + 1]) else ""
                section, heading = f"{m.group(1)}.{m.group(2)}", _clean(m.group(3) + " " + nxt)
        if not section:
            continue
        for t in page.find_tables().tables:
            data = t.extract()
            hdr_end = next((i for i, r in enumerate(data) if any(re.match(r"^\d", _clean(c)) for c in r)), None)
            if hdr_end is None:
                continue
            cols = _cols(data[:hdr_end], t.col_count)
            if "cls" not in cols or "dmax" not in cols:
                continue
            # header x-spans per field (merged cells shift indices between header and body, so map by position)
            spans = {}
            for hi in range(hdr_end):
                for c, bb in enumerate(t.rows[hi].cells):
                    if bb is None:
                        continue
                    key = next((k for k, cc in cols.items() if cc == c), None)
                    if key:
                        x0, x1 = spans.get(key, (bb[0], bb[2]))
                        spans[key] = (min(x0, bb[0]), max(x1, bb[2]))
            order = sorted(spans.items(), key=lambda kv: kv[1][0])

            def field_at(xc):
                for k, (a, b) in order:
                    if a - 1 <= xc <= b + 1:
                        return k
                return min(order, key=lambda kv: min(abs(xc - kv[1][0]), abs(xc - kv[1][1])))[0]
            prev = {}
            for i in range(hdr_end, len(data)):
                r = data[i]
                v = {}
                for c, bb in enumerate(t.rows[i].cells):
                    txt = _clean(r[c]) if c < len(r) else ""
                    if bb is None or not txt:
                        continue
                    k = field_at((bb[0] + bb[2]) / 2)
                    v[k] = (v.get(k, "") + " " + txt).strip()
                others = [k for k in ("material", "dmax", "wall", "insulation", "collars") if v.get(k)]
                rb = t.rows[i].bbox if i < len(t.rows) else None
                if not others and v.get("cls") and rows_out and rows_out[-1]["page"] == pno:
                    rows_out[-1]["cls"] += " , " + v["cls"]               # classification continued on the next line
                    if rb and rows_out[-1]["row_bbox"]:
                        rows_out[-1]["row_bbox"][3] = round(rb[3], 1)
                    continue
                if not v.get("cls") and not others:
                    continue
                row = {k: v.get(k) or prev.get(k, "") for k in ("material", "dmax", "wall", "insulation", "collars", "cls")}
                prev = row
                rows_out.append({"page": pno, "section": section, "heading": heading, **row,
                                 "row_bbox": [round(x, 1) for x in rb] if rb else None, "table_bbox": [round(x, 1) for x in t.bbox]})
    return rows_out


def to_record(i, r):
    annex = r["section"][0]
    fam = family(r["heading"])
    base_ins = heading_insulation(r["heading"])
    mats = materials(r["material"])
    if fam == "composite" and "composite" not in mats:
        mats.append("composite")
    if fam == "ppr":
        mats = ["pp-r"]
    dmax = re.search(r"(\d+(?:\.\d+)?)", r["dmax"] or "")
    wall = re.search(r"(\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?", r["wall"] or "")
    cls = parse_class(r["cls"])
    collars = {"one": 1, "two": 2}.get((r["collars"] or "").lower().split(" ")[0], None)
    # collar cable tables list specific cable types (UTP Cat. 5/6, YMVK ...), not diameters: kept for lookup, not auto-matched
    kind = "cable_typed" if fam == "cable" else "pipe"
    rec = {
        "id": f"{ETA_ID}/{r['section']}/{i:03d}", "eta": ETA_ID, "product": PRODUCT, "system": SYSTEM, "section": r["section"],
        "heading": r["heading"], "page": r["page"], "graph_page": None, "source": "pdf", "row_bbox": r["row_bbox"],
        "table_bbox": r["table_bbox"], "hosts": ANNEX[annex]["hosts"], "min_thickness": ANNEX[annex]["min_thickness"],
        "board": None, "configuration": configuration(r["heading"]), "family": fam, "collars_per_face": collars,
        "service": {"kind": kind, "text": f"{r['material']} Ø ≤ {r['dmax']} mm / {r['wall']} mm", "material": mats[0] if mats else None,
                    "materials": mats, "pipe_product": r["material"] if fam == "silent" else None,
                    "od_min": 0.0, "od_max": float(dmax.group(1)) if dmax else None,
                    "wall_min": float(wall.group(1)) if wall else None, "wall_max": float(wall.group(2) or wall.group(1)) if wall else None},
        "classification": cls, "insulation": parse_insulation(r["insulation"], base_ins),
        "wrap": None, "position": None, "seal_max": None, "edge_min": None, "between_min": None,
    }
    return rec


def build():
    raw = extract()
    recs = [to_record(i, r) for i, r in enumerate(raw)]
    recs = [r for r in recs if r["service"]["od_max"] and r["classification"]["E"]]
    return recs


if __name__ == "__main__":
    recs = build()
    out = ROOT / "data" / "kb" / "multicollar.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(recs, indent=1, ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    print(len(recs), "records;", Counter(r["configuration"] for r in recs), Counter(r["family"] for r in recs),
          "sections", len({r["section"] for r in recs}))
