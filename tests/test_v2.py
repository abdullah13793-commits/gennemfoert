"""Gennemført 2.0 acceptance tests: full product range, intake, case workflow, precedents, quote, revision, site documentation,
browser parity. Run from the product root: python -m pytest tests"""
import copy
import functools
import http.server
import json
import os
import random
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gennemfoert import cases, engine, intake, pipeline, precedents, quote, revision, sitedoc  # noqa: E402

WEB = ROOT / "web" if (ROOT / "web").exists() else ROOT / "docs" / "v2"
COLLAR = json.loads((ROOT / "data" / "kb" / "multicollar.json").read_text(encoding="utf-8")) if (ROOT / "data" / "kb").exists() else None


def Q(host, t, ei, kind="pipe", mat=None, od=None, wall=None, open_=None, ins=None, ap=None, conf="perpendicular"):
    q = {"host_kind": host, "thickness_mm": t, "ei_required": ei, "service_kind": kind, "material": mat, "od_mm": od, "wall_mm": wall,
         "open_system": open_, "insulation": engine.norm_insulation(ins), "hollow_core": False, "configuration": conf}
    if ap:
        q["aperture_mm"] = ap
    return q


AF = lambda t, p="Armaflex AF": {"category": "elastomer", "thickness_mm": t, "product": p}
SW = lambda t: {"category": "stenuld", "thickness_mm": t, "product": "Stenuld rørskål"}

# ---------- B1: fire-collar knowledge base (ETA-20/1322), hand-checked against the source pages ----------


@pytest.mark.skipif(COLLAR is None, reason="knowledge base not shipped in the published repo")
def test_b1_collar_extraction():
    assert len(COLLAR) >= 380
    assert len({r["section"] for r in COLLAR}) >= 90
    p155 = [r for r in COLLAR if r["page"] == 155 and "pvc-u" in r["service"]["materials"]]
    assert any(r["service"]["od_max"] == 110 and r["service"]["wall_min"] == 2.2 and r["classification"]["EI"] == 120 for r in p155)
    assert len({r["service"]["od_max"] for r in p155}) >= 2                    # several diameter steps on the page
    assert {r["configuration"] for r in COLLAR} >= {"perpendicular", "angled", "elbow", "socket", "zero_distance", "corner"}
    assert all(r["hosts"] == ["rigid_floor"] for r in COLLAR if r["section"].startswith("B."))
    assert sum(1 for r in COLLAR if r["row_bbox"]) / len(COLLAR) > 0.97


COLLAR_GOLDEN = [
    # p.155 B.1.1.1: PVC-U <= 110, wall 2.2-8.2, EI 120 U/U, floor >= 150
    ("C1 PVC 110x3.2 floor", Q("rigid_floor", 200, 60, mat="pvc-u", od=110, wall=3.2, open_=True), "TESTET", {"system": "Multicollar Slim"}),
    # p.154: PP <= 110 needs 2.7-6.3 mm -> 2.6 deviates on wall thickness only
    ("C2 PP 75x2.6 floor", Q("rigid_floor", 150, 60, mat="pp", od=75, wall=2.6, open_=True), "AFVIGELSE", {"deviates": ["godstykkelse"]}),
    # collar elastomer brand rule (section 2, item 9)
    ("C3 Cu 28 Kaiflex wall", Q("rigid_wall", 150, 60, mat="copper", od=28, wall=1.5, open_=False, ins=AF(13, "Kaiflex ST")), None, {"brand_ok": True}),
    ("C4 Cu 28 unknown elastomer", Q("rigid_wall", 150, 60, mat="copper", od=28, wall=1.5, open_=False, ins=AF(13, "Gummiskum X")), None,
     {"brand_fail": True}),
    # an angled pipe only matches angled rows
    ("C5 angled PVC 110 floor", Q("rigid_floor", 200, 60, mat="pvc-u", od=110, wall=3.2, open_=True, conf="angled"), None, {"conf": "angled"}),
]


@pytest.mark.parametrize("name,q,status,exp", COLLAR_GOLDEN, ids=[g[0] for g in COLLAR_GOLDEN])
def test_b2_collar_golden(name, q, status, exp):
    v = engine.evaluate(q)
    if status:
        assert v["status"] == status, (name, v["status"], v["nearest"][:1])
    if "system" in exp:
        assert v["matches"][0]["system"] == exp["system"]
        assert any("Multiclips" in c for c in v["conditions"]) and any("450 mm" in c for c in v["conditions"])
    if "deviates" in exp:
        assert v["nearest"][0]["deviates"] == exp["deviates"] and v["nearest"][0]["system"] == "Multicollar Slim"
    rows = v["matches"] + v["nearest"]
    brand = [c for r in rows if r["system"] == "Multicollar Slim" for c in r["checks"] if c["check"] == "isoleringsfabrikat"]
    if exp.get("brand_ok"):
        assert brand and all(c["ok"] for c in brand)
    if exp.get("brand_fail"):
        assert v["status"] != "TESTET" or v["matches"][0]["system"] != "Multicollar Slim"
        assert all(not c["ok"] for c in brand)
    if "conf" in exp:
        assert all(r["configuration"] == exp["conf"] for r in v["matches"]) and v["status"] in ("TESTET", "AFVIGELSE")


def test_b3_ringspalte_wall_vs_floor():
    wall = engine.evaluate(Q("rigid_wall", 150, 60, mat="pvc-u", od=110, wall=3.2, open_=True, ap=[180, 180]))
    floor = engine.evaluate(Q("rigid_floor", 200, 60, mat="pvc-u", od=110, wall=3.2, open_=True, ap=[180, 180]))
    rows = lambda v: [r for r in v["matches"] + v["nearest"] + v["alternatives"] if r["system"] == "Multicollar Slim"]
    gap = lambda r: next(c for c in r["checks"] if c["check"] == "ringspalte")
    assert all(not gap(r)["ok"] for r in rows(wall))                 # 35 mm annular gap in a wall: > 20 mm
    assert floor["status"] == "TESTET" and gap(floor["matches"][0])["ok"] and "Multimortar" in gap(floor["matches"][0])["note"]


def test_b4_answer_key_both_modes():
    planted = json.loads((ROOT / "models" / "planted.json").read_text(encoding="utf-8"))
    ov = json.loads((ROOT / "models" / "planted_fullrange.json").read_text(encoding="utf-8"))["overrides"]
    try:
        engine.use_systems(["Multimastic C"])
        pens, _ = pipeline.run()
        ev = pipeline.evaluate_against(pens, planted)
        assert ev["all_ok"], [r for r in ev["rows"] if not r["ok"]]
    finally:
        engine.use_systems()
    pens, _ = pipeline.run()
    ev = pipeline.evaluate_against(pens, planted, ov)
    assert ev["all_ok"], [r for r in ev["rows"] if not r["ok"]]


# ---------- B5: intake ----------

ITEM = {"construction": {"kind": "rigid_floor", "thickness_mm": 200, "ei_required": 60},
        "service": {"kind": "pipe", "material": "PVC-U", "od_mm": 110, "wall_mm": 3.2, "system": "open", "insulation": "none"},
        "aperture_mm": [150, 150], "photos": {"hul": True, "installation": True, "konstruktion": True, "oversigt": True}}


def test_b5_intake():
    assert intake.completeness(ITEM) == (100, [])
    s, miss = intake.completeness({"construction": {"kind": "rigid_wall"}, "service": {"kind": "pipe"}})
    assert s < 40 and "Krævet brandmodstand (fx EI 60)?" in miss and any(m.startswith("Foto") for m in miss)
    assert intake.region_for("Vestergade 3, 6000 Kolding") == "VEST" and intake.region_for("Ballerupvej 1, 2750 Ballerup") == "ØST"
    case = intake.receive({"project": {"address": "Havnegade 2, 8000 Aarhus C", "timeline": "Snarest muligt"},
                           "items": [ITEM, {**ITEM, "service": {**ITEM["service"], "material": "PP", "od_mm": 75, "wall_mm": 2.6}}]},
                          now=__import__("datetime").datetime(2026, 10, 28, 9), seq=7)
    assert case["id"] == "BV-2026-0007" and case["region"] == "VEST" and case["due"] == "2026-10-31"
    assert [i["triage"] for i in case["items"]] == ["BESVARET_TESTET", "TIL_VURDERING"] and case["status"] == "MODTAGET"


# ---------- B6: case workflow, audit chain, four eyes ----------

def test_b6_workflow_chain_four_eyes():
    c = {"status": "MODTAGET", "events": [], "items": [{"no": 1}]}
    cases.move(c, "TIL_VURDERING", "A")
    with pytest.raises(cases.WorkflowError):
        cases.move(c, "UDSENDT", "A")                                            # illegal jump
    with pytest.raises(cases.WorkflowError):
        cases.decide(c, 1, "A", "GODKENDT", [], "for kort")                      # argument must be the adviser's own
    with pytest.raises(cases.WorkflowError):
        cases.decide(c, 1, "A", "BETINGET", [], "x" * 50)                        # conditional needs conditions
    cases.decide(c, 1, "A", "BETINGET", ["Fotodokumentation"], "Begrundelse skrevet af rådgiveren, mindst fyrre tegn lang.")
    cases.move(c, "UDKAST", "A")
    cases.move(c, "TIL_KONTROL", "A")
    with pytest.raises(cases.WorkflowError):
        cases.review(c, "A", True, "ok")                                         # author cannot review own draft
    cases.review(c, "B", True, "ok")
    cases.move(c, "UDSENDT", "B")
    assert cases.verify(c)
    t = copy.deepcopy(c)
    t["events"][2]["detail"]["decision"] = "GODKENDT"                            # quiet edit
    assert not cases.verify(t)
    t = copy.deepcopy(c)
    del t["events"][1]                                                          # deleted entry
    assert not cases.verify(t)


def test_b6b_simulated_cases_verify():
    cs = json.loads((ROOT / "results" / "cases.json").read_text(encoding="utf-8")) if (ROOT / "results").exists() else \
        json.loads((WEB / "data" / "cases.json").read_text(encoding="utf-8"))
    assert len(cs) == 30 and all(cases.verify(c) for c in cs)
    for c in cs:
        if c["status"] == "UDSENDT":
            authors = {e["actor"] for e in c["events"] if e["action"] == "udkast_gemt"}
            reviewers = {e["actor"] for e in c["events"] if e["action"] == "kontrol_godkendt"}
            assert reviewers and not (authors & reviewers)


# ---------- B7: precedents ----------

def test_b7_precedents():
    q = Q("flexible_wall", 100, 60, mat="pp", od=50, wall=1.2, open_=True)
    v = engine.evaluate(q)
    assert v["status"] == "AFVIGELSE"
    lib = [{"id": "P1", "key": {"host": "flexible_wall", "family": "plast", "params": ["godstykkelse:tyndere"]},
            "signature": [{"param": "godstykkelse", "direction": "tyndere", "magnitude": -33}], "section": "X"},
           {"id": "P2", "key": {"host": "rigid_floor", "family": "plast", "params": ["godstykkelse:tyndere"]},
            "signature": [{"param": "godstykkelse", "direction": "tyndere", "magnitude": -33}], "section": "X"}]
    near = next(n for n in v["nearest"] if n["deviates"] == ["godstykkelse"])
    hits, sig, key = precedents.find(q, near, lib)
    assert sig[0]["direction"] == "tyndere" and sig[0]["magnitude"] < 0
    assert [h["id"] for h in hits] == ["P1"]


# ---------- B8: quote ----------

def test_b8_quote_items_and_quantities():
    reg = json.loads((ROOT / "results" / "register.json").read_text(encoding="utf-8")) if (ROOT / "results").exists() else None
    if reg is None:
        pytest.skip("register not shipped")
    pq = quote.project_quote(reg["penetrations"])
    nos = {ln["no"] for ln in pq["lines"]}
    assert {"6476478014", "6476477918", "6476478010"} <= nos
    assert all(ln["qty"] > 0 and (len(ln["no"]) == 10 or "Multimortar" in ln["name"]) for ln in pq["lines"])
    roll = next(ln for ln in pq["lines"] if ln["no"] == "6476477918")
    assert roll["qty"] == -(-int(roll["basis"].split()[0]) // 174)              # whole rolls of 174 segments


# ---------- B9: revision diff ----------

def test_b9_revision():
    if not (ROOT / "models" / "blok_c_vvs_revB.ifc").exists():
        pytest.skip()
    a, _ = pipeline.run()
    b, _ = pipeline.run(ROOT / "models" / "blok_c_vvs_revB.ifc")
    d = revision.diff(a, b)
    assert len(d["added"]) == 1 and len(d["removed"]) == 1 and len(d["changed"]) == 5 and d["unchanged"] == 52
    params = sorted(ch["param"] for c in d["changed"] for ch in c["changes"])
    assert params.count("wall_mm") == 3 and params.count("ei_required") == 2


# ---------- B10: site documentation ----------

def test_b10_sitedoc():
    p = {"host": {"kind": "rigid_floor"}, "verdict": {"matches": [{"system": "Multicollar Slim", "collars_per_face": 1, "board": None}]}}
    cl = sitedoc.checklist(p)
    assert any("dækkets underside" in c for c in cl) and any("Multimortar" in c for c in cl)
    p["host"]["kind"] = "rigid_wall"
    assert any("pr. side af væggen" in sitedoc.checklist(p)[2] for _ in [0])


# ---------- B11: browser parity (web/engine.js vs engine.py), full range ----------

def _random_queries(n=1500, seed=11):
    rng = random.Random(seed)
    mats = {"pvc-u": [(32, 1.8), (50, 1.8), (110, 3.2), (110, 3.4), (125, 3.9), (160, 4.0), (160, 6.2), (40, 2.0)],
            "pe": [(32, 3.0), (56, 3.0), (110, 4.2), (160, 6.2)], "pp": [(20, 2.2), (32, 1.8), (50, 1.8), (75, 2.6), (75, 3.0), (110, 3.4)],
            "copper": [(12, 1.0), (15, 1.0), (22, 1.0), (22, 1.5), (28, 1.0), (28, 1.5), (54, 1.2), (54, 2.0)],
            "steel": [(26.9, 2.3), (42.4, 2.6), (60.3, 2.9), (88.9, 3.2), (114.3, 3.6), (168.3, 4.5), (219.1, 5.9)],
            "composite": [(16, 2.0), (20, 2.25), (32, 3.0), (75, 7.5)], "pp-r": [(32, 2.9), (63, 5.8)], "abs": [(50, 3.0)]}
    confs = ["perpendicular"] * 8 + ["angled", "elbow", "socket", "zero_distance", "corner", "half_shell"]
    out = []
    for _ in range(n):
        host = rng.choice(["rigid_floor", "rigid_wall", "flexible_wall"])
        kind = rng.choice(["pipe"] * 7 + ["cable", "cable_bundle", "cable_tray", "duct"])
        q = {"host_kind": host, "thickness_mm": rng.choice([75, 100, 150, 200]), "ei_required": rng.choice([30, 45, 60, 90, 120]),
             "service_kind": kind, "hollow_core": rng.random() < 0.3, "configuration": rng.choice(confs)}
        if kind == "pipe":
            mat = rng.choice(list(mats))
            od, wall = rng.choice(mats[mat])
            ins = rng.choice([None, None, SW(20), SW(30), SW(50), AF(9), AF(13, "Kaiflex ST"), AF(13), AF(19, "K-Flex ST"), AF(25, "Gummi X"),
                              {"category": "PE-skum", "thickness_mm": 9, "product": "Climaflex"}])
            q.update(material=mat, od_mm=od, wall_mm=wall, open_system=rng.random() < 0.5, insulation=engine.norm_insulation(ins))
            if rng.random() < 0.04:
                q["material"] = None
        elif kind in ("cable", "cable_bundle"):
            q.update(od_mm=rng.choice([10, 16, 21, 25, 50, 80, 90]), bundle_mm=rng.choice([None, 60, 100, 120]), insulation={"type": "none"})
        else:
            q.update(od_mm=160, insulation={"type": "none"})
        if rng.random() < 0.6:
            q["aperture_mm"] = rng.choice([[130, 130], [160, 160], [220, 220], [300, 300], [600, 600], [1300, 700]])
            q["edge_mm"] = rng.choice([10, 30, 60])
            q["fill"] = round(rng.uniform(0.05, 0.8), 3)
        if rng.random() < 0.3:
            q["separation_mm"] = rng.choice([80, 150, 230, 400])
        out.append(q)
    return out


def _full(v):
    """Everything the user sees: ids, deviations, every check with its texts, conditions, questions."""
    keep = ("id", "system", "section", "page", "board", "seal", "insulation_length", "configuration", "collars_per_face", "deviates")
    rows = lambda rs: [{**{k: r.get(k) for k in keep}, "checks": [(c["check"], c["ok"], c["actual"], c["tested"], c["note"]) for c in r["checks"]]}
                       for r in rs]
    return {"status": v["status"], "matches": rows(v["matches"]), "nearest": rows(v["nearest"]), "alternatives": rows(v["alternatives"]),
            "conditions": v["conditions"], "questions": v["questions"]}


def _norm(x):
    return json.loads(json.dumps(x, ensure_ascii=False), parse_float=lambda s: float(s))


def _serve():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(WEB))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_b11_browser_parity():
    from playwright.sync_api import sync_playwright
    qs = _random_queries()
    items = [{"construction": {"kind": h, "thickness_mm": t, "ei_required": ei},
              "service": {"kind": "pipe", "material": m, "od_mm": od, "wall_mm": w, "system": s, "insulation": ins},
              "aperture_mm": ap, "photos": {"hul": True, "oversigt": ph}}
             for h in ("rigid_floor", "rigid_wall", "flexible_wall") for t in (100, 150) for ei in (60, 120)
             for m, od, w in (("PVC-U", 110, 3.2), ("Kobber", 28, 1.0), ("Alupex", 16, 2.0), ("PP", 75, None))
             for s in ("open", None) for ins in ("none", {"category": "elastomer", "product": "Armaflex AF", "thickness_mm": 13})
             for ap in (None, [160, 160]) for ph in (True,)]
    py = [_full(engine.evaluate(q)) for q in qs]
    py_items = [[*intake.completeness(i), intake.precheck(i)["status"]] for i in items]
    srv = _serve()
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel=os.environ.get("PW_CHANNEL", "msedge") or None, headless=True)
            pg = b.new_page()
            pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/engine.js")
            pg.set_content('<html><head><meta charset="utf-8"></head><body></body></html>')
            pg.add_script_tag(content=(WEB / "engine.js").read_text(encoding="utf-8"))
            pg.evaluate(f"fetch('http://127.0.0.1:{srv.server_address[1]}/data/records.json').then(r => r.json()).then(r => {{ GEngine.load(r); window._ld = 1; }})")
            pg.wait_for_function("window._ld === 1")
            js = pg.evaluate("qs => qs.map(q => GEngine.evaluate(q))", qs)
            js_items = pg.evaluate("its => its.map(i => [...GEngine.completeness(i), GEngine.precheck(i).status])", items)
            b.close()
    finally:
        srv.shutdown()
    js = [_full(v) for v in js]
    diff = [(i, qs[i], py[i], js[i]) for i in range(len(qs)) if _norm(py[i]) != _norm(js[i])]
    idiff = [(i, items[i], py_items[i], js_items[i]) for i in range(len(items)) if list(py_items[i][:1]) + [py_items[i][2]] != [js_items[i][0], js_items[i][2]]
             or py_items[i][1] != js_items[i][1]]
    mix = {}
    for s in py:
        mix[s["status"]] = mix.get(s["status"], 0) + 1
    sysmix = {}
    for s in py:
        for r in s["matches"][:1]:
            sysmix[r["system"]] = sysmix.get(r["system"], 0) + 1
    if (ROOT / "results").exists():
        (ROOT / "results" / "parity_v2.json").write_text(json.dumps(
            {"queries": len(qs), "identical": len(qs) - len(diff), "compared": "status, ids, deviations, every check (name, ok, actual, tested, note), conditions, questions",
             "status_mix": mix, "first_match_system": sysmix, "intake_items": len(items), "intake_identical": len(items) - len(idiff),
             "first_diffs": diff[:3]}, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    assert not diff, diff[:1]
    assert not idiff, idiff[:2]


def test_b12_browser_quote_and_audit_chain():
    """web/assets/quote.js reproduces quote.py line for line, and the browser's SHA-256 chain check accepts every logged case
    and rejects a quietly edited one (same hash as cases.py)."""
    from playwright.sync_api import sync_playwright
    from gennemfoert import quote as Q
    reg = json.loads((WEB / "data" / "register.json").read_text(encoding="utf-8"))
    py = Q.project_quote(json.loads((ROOT / "results" / "register.json").read_text(encoding="utf-8"))["penetrations"])["lines"] \
        if (ROOT / "results").exists() else json.loads((WEB / "data" / "quote.json").read_text(encoding="utf-8"))["lines"]
    cs = json.loads((WEB / "data" / "cases.json").read_text(encoding="utf-8"))
    srv = _serve()
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel=os.environ.get("PW_CHANNEL", "msedge") or None, headless=True)
            pg = b.new_page()
            pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/verify.html")
            pg.wait_for_function("window.GF && window.GEngine")
            pg.add_script_tag(content=(WEB / "assets" / "quote.js").read_text(encoding="utf-8"))
            recs = json.loads((WEB / "data" / "records.json").read_text(encoding="utf-8"))
            pg.evaluate("r => GEngine.load(r)", recs)
            js = pg.evaluate("reg => GQuote.materialList(GQuote.solvedFromRegister(reg))", reg)
            chains = pg.evaluate("cs => Promise.all(cs.map(c => GF.verifyChain(c.events).then(r => r.ok)))", cs)
            tampered = pg.evaluate("c => { const e = JSON.parse(JSON.stringify(c.events)); e[0].actor = 'x'; return GF.verifyChain(e).then(r => r.ok); }", cs[0])
            b.close()
    finally:
        srv.shutdown()
    assert [(l["no"], l["qty"], l["basis"]) for l in js] == [(l["no"], l["qty"], l["basis"]) for l in py]
    assert all(chains) and len(chains) == 30 and tampered is False


def test_b13_browser_workflow_end_to_end():
    """Customer submits an enquiry -> receipt -> adviser drafts a decision -> the author cannot review it -> a second adviser
    approves -> sent; the browser chain still verifies. Site page: installer and inspector must differ."""
    from playwright.sync_api import sync_playwright
    srv = _serve()
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel=os.environ.get("PW_CHANNEL", "msedge") or None, headless=True)
            pg = b.new_page()
            pg.goto(base + "forespoergsel.html")
            pg.wait_for_function("window.F")
            pg.click("#example")
            assert pg.locator(".item").count() == 3
            pg.click("#submit")
            pg.wait_for_selector("#receipt[style*=flex]")
            text = pg.inner_text("#rc")
            assert "Besvaret: testet" in text and "Til vurdering" in text and "VEST" in text
            cid = pg.inner_text("#rc h2").split()[1]
            pg.goto(base + "sager.html#" + cid)
            pg.wait_for_selector("[data-editor]")
            ed = pg.locator("[data-editor]").first
            ed.locator("[data-f=actor]").select_option("Rådgiver Vest")
            ed.locator("[data-f=conditions]").fill("Fotodokumentation pr. gennemføring")
            ed.locator("[data-f=argument]").fill("Kort")
            ed.locator("[data-save]").click()
            assert "min. 40 tegn" in ed.locator("[data-err]").inner_text()
            ed.locator("[data-f=argument]").fill("Godstykkelsen ligger tæt på den testede række; vurderet ud fra nærmeste testede dimension i samme tabel.")
            ed.locator("[data-save]").click()
            pg.wait_for_selector("[data-move=UDKAST]")
            pg.click("[data-move=UDKAST]")
            pg.wait_for_selector("[data-move=TIL_KONTROL]")
            pg.click("[data-move=TIL_KONTROL]")
            pg.wait_for_selector("#rv_actor")
            pg.select_option("#rv_actor", "Rådgiver Vest")
            pg.click("#rv_ok")
            assert "4-øjne" in pg.inner_text("#rv_err")
            pg.select_option("#rv_actor", "Rådgiver Vest 2")
            pg.click("#rv_ok")
            pg.wait_for_selector("[data-move=UDSENDT]")
            pg.click("[data-move=UDSENDT]")
            pg.wait_for_selector(".okline")
            assert "Kæden er intakt" in pg.inner_text("#chainbox")
            pg.click("#tamper")
            pg.wait_for_selector(".badline")
            pg.goto(base + "udfoerelse.html#G-1-01")
            pg.wait_for_selector(".cl input")
            for cb in pg.locator(".cl input").all():
                cb.check()
            pg.fill("#inst", "Montør X")
            pg.locator("#sign").scroll_into_view_if_needed()
            box = pg.locator("#sign").bounding_box()
            pg.mouse.move(box["x"] + 20, box["y"] + 40); pg.mouse.down(); pg.mouse.move(box["x"] + 160, box["y"] + 70, steps=8); pg.mouse.up()
            pg.click("#done")
            pg.wait_for_timeout(300)
            assert pg.locator("#insp").count(), pg.inner_text("#err")
            pg.fill("#insp", "Montør X")
            pg.click("#approve")
            assert "anden end montøren" in pg.inner_text("#err")
            pg.fill("#insp", "Kontrollant Y")
            pg.click("#approve")
            pg.wait_for_selector(".done")
            b.close()
    finally:
        srv.shutdown()


def test_b14_reproduce_and_manifest():
    """Re-run the chain from the source model and compare with every published result; re-hash every delivered file."""
    from gennemfoert import reproduce
    o = reproduce.run()
    assert o["ok"], [c for c in o["checks"] if not c["ok"]]
