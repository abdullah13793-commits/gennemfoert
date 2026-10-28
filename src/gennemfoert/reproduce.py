"""Reproduce and compare: re-run the deterministic chain from the source model and the ETA knowledge base, and compare every result
with the published files. Also re-hashes every file in the manifest and re-verifies every case log and verification code.

python -m gennemfoert.reproduce   (exit code 1 on any mismatch)  ->  results/reproduce.json
"""
import json
import sys
from pathlib import Path

from . import cases, manifest, pipeline, quote, report, revision

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web" if (ROOT / "web").exists() else ROOT / "docs" / "v2"


def _sig(p):
    v = p["verdict"]
    return (p["id"], v["status"], [m["id"] for m in v["matches"][:4]], [n["id"] for n in v["nearest"][:3]])


def run():
    checks = []
    add = lambda name, ok, detail="": checks.append({"check": name, "ok": bool(ok), "detail": detail})
    pens, stats = pipeline.run(ROOT / "models" / "blok_c_vvs.ifc")
    pub = json.loads((WEB / "data" / "register.json").read_text(encoding="utf-8"))
    pub_sig = [(p["id"], p["status"], [m["id"] for m in p["matches"][:4]], [n["id"] for n in p["nearest"][:3]]) for p in pub]
    new_sig = [_sig(p) for p in pens]
    diff = [a[0] for a, b in zip(new_sig, pub_sig) if a != b]
    add("Register: status og citerede ETA-rækker for hver gennemføring", len(new_sig) == len(pub_sig) and not diff, f"{len(new_sig)} gennemføringer, {len(diff)} forskelle {diff[:3]}")
    planted = json.loads((ROOT / "models" / "planted.json").read_text(encoding="utf-8"))
    ov = json.loads((ROOT / "models" / "planted_fullrange.json").read_text(encoding="utf-8"))["overrides"]
    ev = pipeline.evaluate_against(pens, planted, ov)
    add("Facitliste (håndudledt fra ETA-siderne)", ev["all_ok"], f"{ev['correct']}/{ev['planted']}")
    q = quote.project_quote(pens)
    pq = json.loads((WEB / "data" / "quote.json").read_text(encoding="utf-8"))
    add("Materialeliste: varenumre, antal, grundlag", [(l["no"], l["qty"], l["basis"]) for l in q["lines"]] == [(l["no"], l["qty"], l["basis"]) for l in pq["lines"]], f"{len(q['lines'])} linjer")
    revb, _ = pipeline.run(ROOT / "models" / "blok_c_vvs_revB.ifc")
    rv = revision.diff(pens, revb)
    prv = json.loads((WEB / "data" / "revision.json").read_text(encoding="utf-8"))
    add("Revision A→B", json.dumps(rv, sort_keys=True, ensure_ascii=False) == json.dumps(prv, sort_keys=True, ensure_ascii=False),
        f"{len(rv['changed'])} ændret, {len(rv['added'])} ny, {len(rv['removed'])} fjernet")
    cs = json.loads((WEB / "data" / "cases.json").read_text(encoding="utf-8"))
    add("Sagslog: SHA-256-kæde for alle sager", all(cases.verify(c) for c in cs), f"{len(cs)} sager")
    four = all(not ({e['actor'] for e in c['events'] if e['action'] == 'udkast_gemt'} & {e['actor'] for e in c['events'] if e['action'] == 'kontrol_godkendt'})
               for c in cs if c["status"] == "UDSENDT")
    add("4-øjne-princip på alle udsendte vurderinger", four)
    ver = json.loads((WEB / "data" / "verify.json").read_text(encoding="utf-8"))
    by = {c["id"]: c for c in cs}
    bad = [code for code, v in ver.items() if report.verification_code(by[v["case"]], next(i for i in by[v["case"]]["items"] if i["no"] == v["item"])) != code]
    add("Verifikationskoder genberegnet fra sag, afgørelse, citerede rækker og vidensbase", not bad, f"{len(ver)} koder, {len(bad)} afvigende")
    m = json.loads((WEB / "data" / "manifest.json").read_text(encoding="utf-8"))
    changed = [f["path"] for f in m["files"] if not (WEB / f["path"]).exists() or manifest.sha(WEB / f["path"]) != f["sha256"]]
    add("Manifest: SHA-256 for hver leveret fil", not changed, f"{len(m['files'])} filer, {len(changed)} ændret {changed[:3]}")
    add("Vidensbase-version som i manifestet", report.kb_version() == m["inputs"]["knowledge_base"], report.kb_version())
    out = {"ok": all(c["ok"] for c in checks), "checks": checks}
    if (ROOT / "results").exists():
        (ROOT / "results" / "reproduce.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    out["inputs"] = m["inputs"]
    (WEB / "data" / "reproduce.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    o = run()
    for c in o["checks"]:
        print("PASS" if c["ok"] else "FAIL", "|", c["check"], "|", c["detail"])
    sys.exit(0 if o["ok"] else 1)
