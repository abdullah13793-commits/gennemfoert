"""Acceptance tests (SPEC.md A1-A6, A8). Run from the product root: python -m pytest tests"""
import functools
import http.server
import json
import random
import sys
import threading
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gennemfoert import engine, pipeline  # noqa: E402

RECS = json.loads((ROOT / "data" / "eta" / "records.json").read_text(encoding="utf-8"))
WEB = ROOT / "web" if (ROOT / "web").exists() else ROOT / "docs" / "app"          # product folder vs published repo
OUT = ROOT / "out" if (ROOT / "out").exists() else WEB / "downloads"


def Q(host, t, ei, kind="pipe", mat=None, od=None, wall=None, open_=None, ins=None, ap=None):
    q = {"host_kind": host, "thickness_mm": t, "ei_required": ei, "service_kind": kind, "material": mat, "od_mm": od, "wall_mm": wall,
         "open_system": open_, "insulation": engine.norm_insulation(ins), "hollow_core": False}
    if ap:
        q["aperture_mm"] = ap
    return q


SW = lambda t: {"category": "stenuld", "thickness_mm": t, "product": "Stenuld rørskål"}
KF = lambda t, p="Kaiflex ST": {"category": "elastomer", "thickness_mm": t, "product": p}

# Hand-derived from ETA-21/0110 Annex A (page numbers in comments)
GOLDEN = [
    ("G1 PVC 110x3.4 in floor", Q("rigid_floor", 200, 60, mat="pvc-u", od=110, wall=3.4, open_=True), "TESTET", {"section": "A.4.5"}),   # p52
    ("G2 PVC 125 in floor", Q("rigid_floor", 200, 60, mat="pvc-u", od=125, wall=3.9, open_=True), "AFVIGELSE", {"deviates": ["diameter"]}),
    ("G3 Cu 28 Kaiflex 13 light wall", Q("flexible_wall", 100, 60, mat="copper", od=28, wall=1.0, open_=False, ins=KF(13)), "TESTET", {"section": "A.1.6.2"}),  # p20
    # two rows one step away (p20): 9-13 mm gives EI 90, 13-25 mm gives EI 60; both must be named
    ("G4 Cu 28 Kaiflex 20 EI90", Q("flexible_wall", 100, 90, mat="copper", od=28, wall=1.0, open_=False, ins=KF(20)), "AFVIGELSE",
     {"named": ["isoleringstykkelse", "klassifikation"]}),
    ("G5 steel 114.3 SW30 EI120", Q("rigid_wall", 150, 120, mat="steel", od=114.3, wall=3.6, open_=False, ins=SW(30)), "TESTET", {"has": "A.3.4"}),  # p33 + graph p34
    ("G6 PVC 32 75 mm wall EI30", Q("flexible_wall", 75, 30, mat="pvc-u", od=32, wall=1.8, open_=True), "TESTET", {"section": "A.2.1"}),  # p25
    ("G7 PVC 32 75 mm wall EI60", Q("flexible_wall", 75, 60, mat="pvc-u", od=32, wall=1.8, open_=True), "AFVIGELSE", {"deviates": ["klassifikation"]}),
    ("G8 cable 25 mm", Q("rigid_wall", 150, 60, kind="cable", od=25), "TESTET", {}),
    ("G9 steel drain open system", Q("rigid_wall", 150, 60, mat="steel", od=60.3, wall=2.9, open_=True, ins=SW(30)), "AFVIGELSE", {"deviates": ["rørende"]}),
    ("G10 Cu 54 SW20 EI90", Q("rigid_wall", 150, 90, mat="copper", od=54, wall=1.2, open_=False, ins=SW(20)), "TESTET", {"has": "A.3.6"}),  # p36
    ("G11 Cu 54 SW20 EI120 big hole", Q("rigid_wall", 150, 120, mat="copper", od=54, wall=1.2, open_=False, ins=SW(20), ap=[200, 200]),
     "AFVIGELSE", {"deviates": ["hulstørrelse"]}),
    ("G12 Cu 54 SW20 EI120", Q("rigid_wall", 150, 120, mat="copper", od=54, wall=1.2, open_=False, ins=SW(20)), "TESTET", {"section": "A.3.6"}),
    ("G13 PP 75 in floor", Q("rigid_floor", 150, 60, mat="pp", od=75, wall=2.6, open_=True), "IKKE_DAEKKET", {}),
    ("G14 duct", Q("flexible_wall", 100, 60, kind="duct", od=160), "ANDET_SYSTEM", {}),
    ("G15 Cu 22 SW20 in floor", Q("rigid_floor", 150, 60, mat="copper", od=22, wall=1.0, open_=False, ins=SW(20)), "AFVIGELSE",
     {"deviates": ["klassifikation"], "alt": "A.4.8"}),
    ("G16 steel 42.4 SW30 in floor", Q("rigid_floor", 150, 60, mat="steel", od=42.4, wall=2.6, open_=False, ins=SW(30)), "TESTET", {"has": "A.4.4.1"}),
    ("G17 PP 50 light wall", Q("flexible_wall", 100, 60, mat="pp", od=50, wall=1.8, open_=True), "AFVIGELSE", {"deviates": ["diameter"]}),
    ("G18 unknown material", Q("flexible_wall", 100, 60, mat=None, od=22, wall=None, open_=False), "MANGLER_DATA", {}),
]


def test_a1_extraction():
    assert len(RECS) >= 280
    assert len({r["section"] for r in RECS}) >= 36
    assert all(r["page"] >= 8 and r["section"].startswith("A.") for r in RECS)
    assert sum(1 for r in RECS if r["row_bbox"]) / len(RECS) > 0.97
    assert {r["source"] for r in RECS} == {"pdf", "override"}
    # spot checks against the source pages
    p52 = [r for r in RECS if r["page"] == 52]
    assert p52[0]["service"]["od_max"] == 110 and p52[0]["service"]["wall_min"] == 3.4 and p52[0]["classification"]["EI"] == 90
    p20 = [r for r in RECS if r["page"] == 20 and r["service"].get("material") == "copper"]
    assert [r["classification"]["EI"] for r in p20] == [120, 90, 60]


@pytest.mark.parametrize("name,q,status,exp", GOLDEN, ids=[g[0] for g in GOLDEN])
def test_a2_golden(name, q, status, exp):
    v = engine.evaluate(q)
    assert v["status"] == status, (name, v["status"], v["nearest"][:1])
    if "section" in exp:
        assert v["matches"][0]["section"] == exp["section"]
    if "has" in exp:
        assert exp["has"] in {m["section"] for m in v["matches"]}
    if "deviates" in exp:
        assert set(exp["deviates"]) <= set(v["nearest"][0]["deviates"])
    if "named" in exp:
        for d in exp["named"]:
            assert any(n["deviates"] == [d] for n in v["nearest"]), (d, [n["deviates"] for n in v["nearest"]])
    if "alt" in exp:
        assert exp["alt"] in {a["section"] for a in v["alternatives"]}


@pytest.fixture(scope="module")
def run():
    return pipeline.run()


def test_a3_a4_answer_key(run):
    pens, stats = run
    planted = json.loads((ROOT / "models" / "planted.json").read_text(encoding="utf-8"))
    ev = pipeline.evaluate_against(pens, planted)
    assert ev["extra"] == 0 and ev["all_ok"], [r for r in ev["rows"] if not r["ok"]]


def test_a5_writeback():
    wb = json.loads((ROOT / "results" / "writeback.json").read_text())
    assert wb["seals"] == wb["with_psets"] == wb["fills_opening"] == 58
    with zipfile.ZipFile(OUT / "Gennemfoert_afvigelser.bcfzip") as z:
        assert sum(n.endswith("markup.bcf") for n in z.namelist()) == 22


def test_a6_register():
    from openpyxl import load_workbook
    ws = load_workbook(OUT / "Gennemfoeringsregister.xlsx")["Register"]
    assert ws.max_row - 1 == 58
    assert (OUT / "Gennemfoeringsregister.pdf").stat().st_size > 50_000


def _random_queries(n=600, seed=7):
    rng = random.Random(seed)
    mats = {"pvc-u": [(32, 1.8), (110, 3.4), (110, 3.2), (125, 3.9), (160, 6.2), (40, 2.0)], "pe": [(32, 3.0), (110, 4.2), (160, 6.2)],
            "pp": [(20, 2.2), (32, 1.8), (50, 1.8), (75, 2.6)], "copper": [(12, 1.0), (15, 1.0), (22, 1.0), (28, 1.0), (54, 1.2)],
            "steel": [(26.9, 2.3), (42.4, 2.6), (60.3, 2.9), (88.9, 3.2), (114.3, 3.6), (168.3, 4.5), (219.1, 5.9)], "composite": [(16, 2.25), (75, 7.5)]}
    out = []
    for _ in range(n):
        host = rng.choice(["rigid_floor", "rigid_wall", "flexible_wall"])
        kind = rng.choice(["pipe"] * 6 + ["cable", "cable_bundle", "cable_tray", "duct"])
        q = {"host_kind": host, "thickness_mm": rng.choice([75, 100, 150, 200]), "ei_required": rng.choice([30, 45, 60, 90, 120]),
             "service_kind": kind, "hollow_core": rng.random() < 0.3}
        if kind == "pipe":
            mat = rng.choice(list(mats))
            od, wall = rng.choice(mats[mat])
            ins = rng.choice([None, SW(20), SW(30), SW(50), KF(9), KF(13), KF(13, "Armaflex AF"), KF(19), KF(25)])
            q.update(material=mat, od_mm=od, wall_mm=wall, open_system=rng.random() < 0.5, insulation=engine.norm_insulation(ins))
            if rng.random() < 0.05:
                q["material"] = None
        elif kind in ("cable", "cable_bundle"):
            q.update(od_mm=rng.choice([10, 16, 21, 25, 50, 80, 90]), bundle_mm=rng.choice([None, 60, 100, 120]), insulation={"type": "none"})
        else:
            q.update(od_mm=160, insulation={"type": "none"})
        if rng.random() < 0.6:
            q["aperture_mm"] = rng.choice([[160, 160], [220, 220], [300, 300], [600, 600], [1300, 700]])
            q["edge_mm"] = rng.choice([10, 30, 60])
            q["fill"] = round(rng.uniform(0.05, 0.8), 3)
        if rng.random() < 0.3:
            q["separation_mm"] = rng.choice([80, 150, 230, 400])
        out.append(q)
    return out


def _sig(v):
    def ids(rows):
        return [(r["id"], sorted(r.get("deviates", []))) for r in rows]
    return {"status": v["status"], "matches": ids(v["matches"]), "nearest": ids(v["nearest"]), "alternatives": ids(v["alternatives"]),
            "conditions": v["conditions"], "questions": v["questions"],
            "checks": [[(c.get("check") or c.get("c"), c["ok"]) for c in (r["checks"])] for r in (v["matches"][:1] + v["nearest"][:1])]}


def test_a8_browser_parity():
    from playwright.sync_api import sync_playwright
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(WEB))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    qs = _random_queries()
    py = [_sig(engine.evaluate(q)) for q in qs]
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="msedge", headless=True)
            pg = b.new_page()
            pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/index.html")
            pg.wait_for_function("window.GEngine")
            pg.evaluate("fetch('data/records.json').then(r => r.json()).then(r => { GEngine.load(r); window._ld = 1; })")
            pg.wait_for_function("window._ld === 1")
            js = pg.evaluate("qs => qs.map(q => GEngine.evaluate(q))", qs)
            b.close()
    finally:
        srv.shutdown()
    js = [_sig(v) for v in js]
    diff = [(i, qs[i], py[i], js[i]) for i in range(len(qs)) if py[i] != js[i]]
    stats = {"queries": len(qs), "identical": len(qs) - len(diff), "status_mix": {}}
    for s in py:
        stats["status_mix"][s["status"]] = stats["status_mix"].get(s["status"], 0) + 1
    (ROOT / "results" / "parity.json").write_text(json.dumps({**stats, "first_diffs": diff[:3]}, indent=1, ensure_ascii=False, default=str),
                                                  encoding="utf-8")
    assert not diff, diff[:2]
