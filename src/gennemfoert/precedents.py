"""Precedents: find earlier decided assessments with the same kind of deviation, so the same question gets the same
answer from every adviser and every office.

A deviation signature is computed from the enquiry and the nearest tested row: which parameter differs, in which
direction and by how much (e.g. godstykkelse, tyndere, -6 %). Two cases are similar when the construction kind, the
material family and the set of deviating parameters with their directions agree; magnitude and system rank them.
"""
import json
from pathlib import Path

from . import engine

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "data" / "precedents.json"
FAMILY = {"pvc-u": "plast", "pvc-c": "plast", "pe": "plast", "pp": "plast", "abs": "plast", "pp-r": "plast", "composite": "komposit",
          "copper": "metal", "steel": "metal"}


def _rec(rid):
    return next((r for r in engine.RECORDS if r["id"] == rid), None)


def signature(q, nearest):
    """nearest: a brief from engine.evaluate (with id and deviates). Returns a list of (param, direction, magnitude)."""
    rec = _rec(nearest["id"]) if nearest else None
    out = []
    for p in (nearest or {}).get("deviates", []):
        d, m = "anden", None
        if rec:
            s, ins = rec["service"], rec["insulation"]
            if p == "diameter" and q.get("od_mm") and s.get("od_max"):
                d = "større" if q["od_mm"] > s["od_max"] else "mindre"
                m = round(100 * (q["od_mm"] - s["od_max"]) / s["od_max"]) if q["od_mm"] > s["od_max"] else round(100 * (q["od_mm"] - (s.get("od_min") or 0)) / max(q["od_mm"], 1))
            elif p == "godstykkelse" and q.get("wall_mm") is not None and s.get("wall_min") is not None:
                d = "tyndere" if q["wall_mm"] < s["wall_min"] else "tykkere"
                ref = s["wall_min"] if d == "tyndere" else s["wall_max"]
                m = round(100 * (q["wall_mm"] - ref) / ref)
            elif p == "isoleringstykkelse" and ins.get("t_min") is not None:
                t = (q.get("insulation") or {}).get("thickness_mm") or 0
                d = "tykkere" if t > ins["t_max"] else "tyndere"
                ref = ins["t_max"] if d == "tykkere" else ins["t_min"]
                m = round(100 * (t - ref) / max(ref, 1))
            elif p == "klassifikation":
                d, m = "lavere", (rec["classification"].get("EI") or 0) - (q.get("ei_required") or 0)
            elif p == "isoleringsfabrikat":
                d = "andet fabrikat"
            elif p == "isoleringstype":
                d = f"{(q.get('insulation') or {}).get('type')} i stedet for {ins.get('type')}"
            elif p in ("afstand mellem tætninger", "ringspalte", "hulstørrelse", "kantafstand"):
                d = "geometri"
        out.append({"param": p, "direction": d, "magnitude": m})
    return out


def key(q, sig):
    return {"host": q.get("host_kind"), "family": FAMILY.get(q.get("material"), q.get("service_kind")),
            "params": sorted(f"{s['param']}:{s['direction']}" for s in sig)}


def find(q, nearest, library=None, limit=3):
    lib = library if library is not None else (json.loads(LIB.read_text(encoding="utf-8")) if LIB.exists() else [])
    sig = signature(q, nearest)
    k = key(q, sig)
    hits = []
    for p in lib:
        pk = p["key"]
        if pk["params"] != k["params"] or pk["host"] != k["host"]:
            continue
        score = 3 + (pk["family"] == k["family"]) * 2
        if nearest and p.get("section") == nearest.get("section"):
            score += 2
        mags = [s["magnitude"] for s in sig if s["magnitude"] is not None]
        pm = [s["magnitude"] for s in p["signature"] if s["magnitude"] is not None]
        if mags and pm:
            score -= min(2, abs(mags[0] - pm[0]) / 10)
        hits.append({**p, "score": round(score, 2)})
    return sorted(hits, key=lambda h: -h["score"])[:limit], sig, k
