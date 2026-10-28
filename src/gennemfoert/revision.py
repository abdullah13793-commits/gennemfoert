"""Revision control: compare the penetrations of two model revisions and say which decisions no longer hold.

A brandteknisk vurdering applies only to the described solution; changes in construction, installation, materials,
products or execution can mean it must be re-assessed. This makes that rule operational: penetrations are matched
across revisions by their IFC GlobalIds (service + host), and every changed parameter is listed. Penetrations whose
verdict or parameters changed invalidate their earlier decisions.
"""

PARAMS = [("host", "kind"), ("host", "thickness_mm"), ("host", "ei_required"), ("service", "material"), ("service", "od_mm"),
          ("service", "wall_mm"), ("service", "open_system"), (None, "aperture_mm"), (None, "separation_mm")]


def _ins(p):
    i = p["service"].get("insulation") or {}
    return (i.get("product"), i.get("thickness_mm"))


def diff(old, new):
    o = {(p["service"]["guid"], p["host"]["guid"]): p for p in old}
    n = {(p["service"]["guid"], p["host"]["guid"]): p for p in new}
    out = {"added": [], "removed": [], "changed": [], "unchanged": 0}
    for k, p in n.items():
        if k not in o:
            out["added"].append({"id": p["id"], "service": p["service"]["name"], "status": p["verdict"]["status"]})
            continue
        q = o[k]
        ch = []
        for grp, f in PARAMS:
            a = (q.get(grp) or {}).get(f) if grp else q.get(f)
            b = (p.get(grp) or {}).get(f) if grp else p.get(f)
            if a != b:
                ch.append({"param": f, "old": a, "new": b})
        if _ins(q) != _ins(p):
            ch.append({"param": "insulation", "old": _ins(q), "new": _ins(p)})
        if q["verdict"]["status"] != p["verdict"]["status"]:
            ch.append({"param": "status", "old": q["verdict"]["status"], "new": p["verdict"]["status"]})
        if ch:
            out["changed"].append({"id": p["id"], "old_id": q["id"], "service": p["service"]["name"], "changes": ch,
                                   "old_status": q["verdict"]["status"], "new_status": p["verdict"]["status"], "reassess": True})
        else:
            out["unchanged"] += 1
    for k, q in o.items():
        if k not in n:
            out["removed"].append({"id": q["id"], "service": q["service"]["name"], "status": q["verdict"]["status"]})
    return out
