# How to verify every output

Nothing here has to be taken on trust. Each output has a manual check that a person can do in minutes and an automated check that
runs on every change (`python -m pytest tests`, and `python -m gennemfoert.reproduce` for a full rebuild-and-compare).

## Three levels

1. **The file:** is it the one that was delivered, unchanged? Every delivered file is listed in `MANIFEST.json` (in the app at
   `data/manifest.json`) with its SHA-256, the step that produced it, the model, knowledge-base and code versions it was built from, and the
   tests that cover it. Drag the file onto **Verificér** in the app; it is hashed in the browser and never uploaded.
2. **The answer:** is it right? Every verdict shows the ETA, the section, the page image with the tested row highlighted, a link to the
   official PDF at that page, and every parameter as designed vs tested.
3. **The method:** does it reproduce? `python -m gennemfoert.reproduce` re-runs the chain from the source IFC and the ETA knowledge base,
   and compares every result with the published files (latest result on the Verificér page).

## Output by output

| Output | Check it yourself | Automated check |
|---|---|---|
| Verdict per penetration (TESTET / AFVIGELSE / …) | Open the cited ETA page ("åbn kilden ↗") and compare the highlighted row with the designed values in the table | Answer key 59/59 hand-derived from the ETA pages (`test_a3_a4_answer_key`, `test_b4_answer_key_both_modes`); 23 golden enquiries (`test_a2_golden`, `test_b2_collar_golden`) |
| Knowledge base (678 rows) | Search a row on **Viden**, compare with the page image | Row counts, rectangles and spot checks against named pages (`test_a1_extraction`, `test_b1_collar_extraction`); known source errors listed on Viden |
| Browser answers | The same engine runs in Python and in the browser | 1,500 random enquiries identical, every check's text (`test_b11_browser_parity`) |
| Register XLSX / PDF with QR labels | Count rows = penetrations; scan a label | `test_a6_register`, manifest hash |
| BCF issues, IFC with seals | Open in Solibri / BIMcollab / any IFC viewer | Parsed and counted (`test_a5_writeback`), manifest hash |
| Case log | Verificér → chain status; "Simulér en stille rettelse" shows a broken link | SHA-256 chain for all cases, four-eyes rule (`test_b6_workflow_chain_four_eyes`, `test_b6b_simulated_cases_verify`), browser = server hash (`test_b12_browser_quote_and_audit_chain`) |
| Issued assessment PDF | Type or scan the verification code on Verificér | Codes recomputed from case, decision, cited rows and KB version (`reproduce`) |
| Material list / quote | Each line states its basis (area, joint length, segments); factors are editable | Browser = Python line for line (`test_b12`), item numbers present (`test_b8`) |
| Revision A → B | Compare the listed parameters in the two IFC files (downloads) | `test_b9_revision`, `reproduce` |
| Site documentation and owner package | Checklist lines come from the cited ETA row | `test_b10_sitedoc`, end-to-end browser run (`test_b13_browser_workflow_end_to_end`) |
| Dashboard numbers | Computed from the case log shown on Sager | Simulation is seeded (reproducible) |
| Every delivered file | Drag onto Verificér | `MANIFEST.json` + `reproduce` re-hash (`test_b14_reproduce_and_manifest`) |

## What verification does not cover
The demo building, cases, customers and precedents are fictitious. Matching an ETA row is decision support; a brandteknisk vurdering is
written and signed by a person.
