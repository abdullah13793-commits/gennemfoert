# Gennemført 2.0: spec

**One line:** the fire-protection adviser's operating system for penetration seals. A structured enquiry is pre-checked against every
tested configuration of the ETAs the business carries. The case runs through a documented, four-eyes workflow with precedents. The issued
assessment can be verified, and the same solution drives the material list, the site checklist and the owner's handover package.

v1 (`2026-10-25_gennemfoert`) answered one question well: *is this penetration in the IFC model valid as tested?* v2 keeps that engine and
formalises the rest of the adviser's work around it.

## The work today (from the advisory service's own published process)
1. The customer fills in a free-text form ("Beskriv opgaven"): company, contact, project address, building type, timeline, uploads.
2. The adviser reviews the material and **asks for what is missing**.
3. The adviser finds the tested solution in the ETA / classification report, system by system.
4. If the set-up deviates, the adviser writes a brandteknisk vurdering. The deliverable has six points: description, review of the
   deviation, professional assessment, solution model, assumptions/limitations, written documentation.
5. The PDF is sent. Execution and the owner's documentation (BR18, owner must ensure inspection since 1 Jan 2025) happen elsewhere.

Two offices (east: Ballerup; west: Kolding) handle the enquiries.

## Where the legacy method is inefficient, and what replaces it
| Legacy step | Problem | v2 replacement (module) | Proving test |
|---|---|---|---|
| Free-text enquiry | Missing data found by the adviser days later; tested set-ups still take an adviser's time | **M2** structured intake: one block per penetration type, weighted completeness score, photo checklist, live pre-check; tested answers returned at once; routing east/west by postcode; SLA from timeline | `test_b5_intake`, browser parity of completeness/triage (384 items), e2e `b13` |
| ETA lookup per system | Knowledge in PDFs, one product at a time | **M1** knowledge base across ETAs: ETA-21/0110 board seals (293 rows) + ETA-20/1322 fire collars (385 rows, 12 mounting situations), each row with page and table rectangle; data-quality notes; import queue | `test_b1`, `b2`, `b3`, answer key in both modes `b4` |
| Assessment in Word | Same deviation answered differently by different advisers and offices | **M4** precedents: deviation signature (parameter, direction, magnitude) → earlier decisions with conditions and argument | `test_b7` |
| No visible QA trail | ISO 9001 expects review and traceability | **M3** case states and transitions, decision with argument ≥ 40 chars (written by the adviser), **four-eyes** (reviewer ≠ author), **SHA-256 hash-chained** event log with knowledge-base version, verifiable in the browser | `test_b6`, `b6b`, `b12`, `b13` |
| PDF sent, cannot be checked later | Altered or outdated assessments circulate | **M4** issued PDF in the six-point structure with the ETA excerpt highlighted, verification code + QR → verify page (genuine, still valid) | MCP `verify_assessment`, verify page |
| Revisions not tracked | An assessment applies only to the described solution | **M7** IFC revision diff by GlobalId; changed parameters listed; decisions flagged for re-assessment | `test_b9` |
| Quote assembled by hand | Items, quantities and basis not linked to the tested solution | **M5** material list with the wholesaler's item numbers, geometric quantities with editable factors, basis per line | `test_b8`, browser parity `b12` |
| Execution documented elsewhere | Owner's inspection evidence not tied to the solution | **M6** checklist generated from the ETA row, photo, installer signature, inspector ≠ installer, handover PDF + CSV | `test_b10`, e2e `b13` |
| No overview | Throughput and recurring deviations invisible | **M8** dashboard: deflection, missing-info rate, lead time, recurring deviations, regions, per-adviser load | page smoke test |
| Knowledge only in people | | **M9** MCP server, 14 tools (check, pre-check, precedents, cases with chain check, verify, quote, revision, KB) | `test_mcp` |

## Acceptance (v2)
| ID | Criterion | Result |
|---|---|---|
| B1 | Collar ETA extracted: ≥ 380 rows, ≥ 90 sections, row rectangles ≥ 97 %, spot checks against p. 155 | 385 rows, 93 sections |
| B2–B3 | Collar rules: elastomer brands (s. 2 item 9), annular gap wall ≤ 20 mm / floor Multimortar (s. 1 item 4), clips by Ø, mounting situation | pass |
| B4 | Answer key 59/59 in board-only mode and in full-range mode (with the documented full-range overrides) | pass |
| B5 | Intake: completeness, region, SLA, triage | pass |
| B6 | Workflow: illegal transitions refused, argument rule, conditional needs conditions, author cannot review, quiet edit or deleted event detected; 30 simulated cases verify with four eyes | pass |
| B7–B10 | Precedents, quote, revision (52 unchanged, 1 added, 1 removed, 5 changed), site checklist | pass |
| B11 | Browser engine = Python engine on 1,500 random queries, comparing status, ids, deviations, every check's texts, conditions, questions; 384 intake items | 1,500/1,500, 384/384 |
| B12 | Browser quote = Python quote line for line; browser SHA-256 accepts all 30 case logs and rejects an edited one | pass |
| B13 | End to end in a browser: enquiry → receipt → decision → four-eyes refusal → review → sent → chain intact; site: installer ≠ inspector | pass |
| v1 A1–A6 | v1 acceptance, board-only mode | pass |
| Web | 9 pages × desktop/phone: no console errors, no horizontal scroll | `results/web_smoke_v2.json` |

## Limits
- Decision support, not approval. A brandteknisk vurdering is written and signed by a person; v2 enforces that the argument is the adviser's
  own text and that a second adviser reviews it.
- The knowledge base holds what the public ETAs state. Two further ETAs (Multidisc, Multifoam 2K) are registered, not yet extracted.
- Quantities are geometric; the manufacturer does not publish consumption tables. Prices are not included.
- Cases, customers, advisers, precedents and the building are fictitious demonstration data, labelled as such on every page.
- Browser-side state (new enquiries, decisions, site records) is kept in the viewer's browser only; a production deployment would keep the
  case log server-side (the same hash chain).
