# Gennemført: spec

**One line:** every pipe, duct and cable that crosses a fire separation, found in the IFC model, checked against
the exact tested configurations in the product's ETA ("valid only as tested"), with a page-and-row citation, and
documented from design to site label.

## Buyer and setting
Fire-protection advisers at a passive-fire-protection wholesaler/advisory (penetration seals, brandteknisk
vurdering, product courses), and the contractors, installers and consultants they serve. Their workflow today:
1. An enquiry arrives (wall/floor type, EI, pipe, diameter, insulation, photos), often incomplete.
2. The adviser looks up the tested solution in the ETA / classification report / manufacturer app.
3. If the set-up is not exactly as tested, the adviser writes a brandteknisk vurdering.
4. Since 1 Jan 2025 the building owner must make sure the work was inspected, so documentation matters.

## Gap → improvement → proving test
| Gap today | Improvement | Proving test |
|---|---|---|
| Penetrations are counted by hand from drawings, late | IFC take-off: every service crossing an EI/REI element, with host type, thickness, EI, service, Ø, wall thickness, insulation | planted model: all planted penetrations found, none invented |
| ETA lookups are manual, and "almost the same" slips through | Valid-as-tested engine over records extracted from the public ETA, each with page + table row + crop | golden set of queries hand-derived from ETA pages; planted model statuses match the answer key |
| Deviations are found late, enquiries are incomplete | Every deviation names the parameter that deviates and the nearest tested rows; intake fields pre-filled; missing data turned into questions | answer key: deviating parameter named correctly for each planted deviation |
| Documentation for the owner is assembled at the end | Penetration register (IDs, QR site labels), BCF issues, provision-for-void objects with Psets in the IFC | IFC re-opens with all objects + Psets; BCF parses; register rows = penetrations |
| Knowledge is locked in PDFs | MCP server: ask "is a 110 mm PVC drain through a 200 mm hollow-core slab at EI 60 tested?" and get the row and page | MCP test through the official client; answers carry citations |
| The quick check only lives with the adviser | Browser checker (Danish) running the same rules client-side | JS vs Python parity over a randomised query grid |

## Acceptance
| ID | Criterion |
|---|---|
| A1 | ETA extraction: every Annex A table yields records; each record has page, section, row bbox; garbled rows are overridden by hand and marked as such |
| A2 | Golden queries (hand-derived from the ETA) return the expected status and section |
| A3 | Demo model: every planted penetration found with the expected status (TESTED / VURDERING / ANDET_SYSTEM / MANGLER_DATA), 0 extra |
| A4 | For each planted deviation the engine names the deviating parameter(s) |
| A5 | Write-back: IFC re-opens, one provision-for-void per penetration with Pset_ProvisionForVoid + Gennemfoert pset; BCF zip parses |
| A6 | Register (XLSX + PDF with QR labels) has one row per penetration |
| A7 | MCP: all tools callable through the official client; answers include ETA citation |
| A8 | Browser checker = Python engine on a randomised grid (parity 100 %) |

## Limits (stated everywhere)
- Decision support, not approval. The adviser confirms every match against the source document; a brandteknisk
  vurdering is written and signed by a person.
- The database holds what the public ETA states; manufacturer-specific installation instructions and national
  requirements still apply.
- The demonstration building and its MEP are fictitious.
