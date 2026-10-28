"""Provenance manifest: every delivered file with its SHA-256, the step that produced it, the inputs it was built from (model, knowledge
base, code) and the automated checks that cover it. The verify page hashes a file in the browser and looks it up here.

python -m gennemfoert.manifest  ->  web/data/manifest.json (+ out/MANIFEST.json)
"""
import datetime
import hashlib
import json
from pathlib import Path

from . import report

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
RULES = [  # (pattern in downloads/, producer, what it is, how to verify, tests)
    ("Gennemfoeringsregister.xlsx", "gennemfoert.register", "Gennemføringsregister (Excel)", "Én række pr. gennemføring; hver løsning peger på ETA, afsnit og side", ["test_a6_register"]),
    ("Gennemfoeringsregister.pdf", "gennemfoert.register", "Register med QR-mærkater", "QR på hver mærkat åbner gennemføringen i appen", ["test_a6_register"]),
    ("Gennemfoert_afvigelser.bcfzip", "gennemfoert.writeback", "BCF 2.1-sager for afvigelser", "Åbn i Solibri/BIMcollab; én sag pr. ikke-testet gennemføring", ["test_a5_writeback"]),
    ("blok_c_vvs_gennemfoert.ifc", "gennemfoert.writeback", "IFC med tætninger (PROVISIONFORVOID + psets)", "Åbn i en IFC-viewer; Gennemfoert_Taetning-pset pr. tætning", ["test_a5_writeback"]),
    ("blok_c_vvs.ifc", "gennemfoert.model", "Demonstrationsmodel, revision A", "Kilde; facitliste i models/planted.json", ["test_a3_a4_answer_key", "test_b4_answer_key_both_modes"]),
    ("blok_c_vvs_revB.ifc", "gennemfoert.model", "Demonstrationsmodel, revision B", "Kilde for revisionssammenligningen", ["test_b9_revision"]),
    ("vurderinger/", "gennemfoert.assess", "Udkast til brandteknisk vurdering (.docx)", "Fakta og sammenligning udfyldt; skønnet står tomt til rådgiveren", []),
    ("udstedte/", "gennemfoert.report", "Udstedt brandteknisk vurdering (PDF)", "Verifikationskoden på PDF'en slås op på denne side", ["test_b6b_simulated_cases_verify"]),
    ("Dokumentationspakke_bygherre.pdf", "gennemfoert.sitedoc", "Dokumentationspakke til bygherren", "Tjekliste pr. tætning genereret fra ETA-rækken", ["test_b10_sitedoc", "test_b13_browser_workflow_end_to_end"]),
    ("Dokumentation_brandtaetninger.csv", "gennemfoert.sitedoc", "Udførelsesdata (CSV)", "Samme rækker som pakken", ["test_b10_sitedoc"]),
    ("Tilbud_materialeliste.csv", "gennemfoert.quote", "Materialeliste med varenumre", "Hver linje har sit beregningsgrundlag; browseren regner det samme", ["test_b8_quote_items_and_quantities", "test_b12_browser_quote_and_audit_chain"]),
]
DATA_RULES = {"register.json": ("gennemfoert.pipeline", ["test_a3_a4_answer_key", "test_b11_browser_parity"]),
              "records.json": ("gennemfoert.eta + eta_collar", ["test_a1_extraction", "test_b1_collar_extraction"]),
              "cases.json": ("gennemfoert.demo", ["test_b6b_simulated_cases_verify", "test_b12_browser_quote_and_audit_chain"]),
              "verify.json": ("gennemfoert.demo", ["test_b6b_simulated_cases_verify"]), "quote.json": ("gennemfoert.quote", ["test_b8_quote_items_and_quantities"]),
              "revision.json": ("gennemfoert.revision", ["test_b9_revision"]), "site.json": ("gennemfoert.sitedoc", ["test_b10_sitedoc"]),
              "dashboard.json": ("gennemfoert.demo", []), "precedents.json": ("gennemfoert.demo", ["test_b7_precedents"]), "summary.json": ("gennemfoert.export_web", [])}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def code_version():
    h = hashlib.sha256()
    for p in sorted((ROOT / "src").rglob("*.py")):
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:12]


def build():
    dl = WEB / "downloads"
    inputs = {"model_A": sha(ROOT / "models" / "blok_c_vvs.ifc")[:16], "model_B": sha(ROOT / "models" / "blok_c_vvs_revB.ifc")[:16],
              "knowledge_base": report.kb_version(), "code": code_version()}
    files = []
    for p in sorted(dl.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(dl)).replace("\\", "/")
        rule = next((r for r in RULES if rel == r[0] or (r[0].endswith("/") and rel.startswith(r[0]))), None)
        files.append({"path": "downloads/" + rel, "name": p.name, "bytes": p.stat().st_size, "sha256": sha(p),
                      "producer": rule[1] if rule else None, "what": rule[2] if rule else None, "how": rule[3] if rule else None,
                      "tests": rule[4] if rule else []})
    for p in sorted((WEB / "data").glob("*.json")):
        if p.name in ("manifest.json", "reproduce.json"):
            continue
        prod, tests = DATA_RULES.get(p.name, (None, []))
        files.append({"path": "data/" + p.name, "name": p.name, "bytes": p.stat().st_size, "sha256": sha(p), "producer": prod,
                      "what": "Data bag appen", "how": "Samme tal som filerne; testene sammenligner mod facitliste og Python-motoren", "tests": tests})
    m = {"product": "Gennemført 2.0", "generated": datetime.date.today().isoformat(), "inputs": inputs, "files": files,
         "reproduce": "python -m gennemfoert.reproduce", "results": {
             "answer_key": json.loads((ROOT / "results" / "evaluation.json").read_text(encoding="utf-8"))["correct"],
             "parity": json.loads((ROOT / "results" / "parity_v2.json").read_text(encoding="utf-8"))["identical"]}}
    (WEB / "data" / "manifest.json").write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")
    (ROOT / "out").mkdir(exist_ok=True)
    (ROOT / "out" / "MANIFEST.json").write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")
    return m


if __name__ == "__main__":
    m = build()
    print(len(m["files"]), "files;", m["inputs"])
