"""IFC -> penetrations -> valid-as-tested verdicts -> results/register.json (+ evaluation against the answer key).

python -m gennemfoert.pipeline [model.ifc]
"""
import json
import sys
import time
from collections import Counter
from pathlib import Path

import ifcopenshell

from . import detect, engine

ROOT = Path(__file__).resolve().parents[2]


def run(path=ROOT / "models" / "blok_c_vvs.ifc"):
    t0 = time.time()
    model = ifcopenshell.open(str(path))
    pens, stats = detect.find(model)
    for p in pens:
        p["query"] = engine.query_from_penetration(p)
        p["verdict"] = engine.evaluate(p["query"])
    stats["seconds"] = round(time.time() - t0, 1)
    stats["model"] = Path(path).name
    stats["status"] = dict(Counter(p["verdict"]["status"] for p in pens))
    return pens, stats


def evaluate_against(pens, planted):
    """Answer-key check: every planted penetration found once, statuses and deviating parameters as expected."""
    by_key = {(p["service"]["guid"], p["host"]["guid"]): p for p in pens}
    rows, ok_all = [], True
    for e in planted:
        if e.get("status") == "IKKE_BRANDADSKILLENDE":
            found = any(p["service"]["guid"] == e["service_guid"] for p in pens)
            rows.append({"service": e["service"], "expected": e["status"], "got": "listed" if found else "IKKE_BRANDADSKILLENDE", "ok": not found})
            ok_all &= not found
            continue
        p = by_key.get((e["service_guid"], e["host_guid"]))
        got = p["verdict"]["status"] if p else "NOT FOUND"
        ok = got == e["status"]
        notes = []
        v = p["verdict"] if p else {}
        if ok and e.get("sections"):
            secs = {m["section"] for m in v["matches"]}
            miss = [s for s in e["sections"] if s not in secs]
            ok &= not miss
            if miss:
                notes.append(f"missing sections {miss}")
        if ok and e.get("deviates"):
            dev = set(v["nearest"][0]["deviates"]) if v.get("nearest") else set()
            ok &= set(e["deviates"]) <= dev
            if not set(e["deviates"]) <= dev:
                notes.append(f"deviates {sorted(dev)}")
        if ok and e.get("alternative"):
            alts = {a["section"] for a in v.get("alternatives", [])}
            ok &= e["alternative"] in alts
            if e["alternative"] not in alts:
                notes.append(f"alternatives {sorted(alts)}")
        rows.append({"id": p["id"] if p else None, "service": e["service"], "host": e["host"], "expected": e["status"], "got": got,
                     "ok": ok, "notes": "; ".join(notes)})
        ok_all &= ok
    extra = len(pens) - sum(1 for e in planted if e.get("status") != "IKKE_BRANDADSKILLENDE")
    return {"planted": len(planted), "found": len(pens), "extra": extra, "all_ok": ok_all and extra == 0,
            "correct": sum(r["ok"] for r in rows), "rows": rows}


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "models" / "blok_c_vvs.ifc"
    pens, stats = run(path)
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "register.json").write_text(json.dumps({"stats": stats, "penetrations": pens}, indent=1, ensure_ascii=False),
                                                    encoding="utf-8")
    print(stats)
    planted_path = path.parent / "planted.json"
    if planted_path.exists():
        ev = evaluate_against(pens, json.loads(planted_path.read_text(encoding="utf-8")))
        (ROOT / "results" / "evaluation.json").write_text(json.dumps(ev, indent=1, ensure_ascii=False), encoding="utf-8")
        print("answer key:", ev["correct"], "/", ev["planted"], "correct; found", ev["found"], "extra", ev["extra"], "all_ok", ev["all_ok"])
        for r in ev["rows"]:
            if not r["ok"]:
                print("  MISMATCH", r)
