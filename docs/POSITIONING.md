# Positioning: where Gennemført sits next to existing tools

**Short version:** Gennemført is not a new platform. It is the step between three things a project already has: the
MEP/IFC model, the manufacturer's ETA, and the documentation the building owner must now be able to rely on. It
finds the penetrations, checks each one against the exact tested configurations ("valid only as tested") with a
page-and-row citation, and writes the answer back into IFC, BCF, an Excel register and site labels.

## What incumbents already do well (and Gennemført does not try to replace)
| Tool | Strong at | Source |
|---|---|---|
| **Hilti Firestop plug-in for Revit / Navisworks / AutoCAD MEP** | Detects penetrations through fire-rated walls in the authoring model, selects and places Hilti firestops, bill of materials, submittal document | hilti.com (Firestop BIM software); ENR, "Hilti launches BIM plug-in" |
| **Hilti Documentation Manager** | Cloud documentation of installed firestops: photos, plan locations, QR-coded labels per penetration | RIBA Journal (Hilti, Building Safety Act) |
| **Manufacturer selectors** (Mulcol Fire Protection app, Promat Selector, Quelfire QuelSelector) | Pick wall, service and EI, get the tested solution and its documents, for that manufacturer's range | App Store listing (Mulcol International); promat.com; quelfire.co.uk |
| **Solibri** (rule SUK/1002 "No fire seal present for service penetration") | Model checking: flags service penetrations of compartment walls/floors without a fire-seal object | help.solibri.com |
| **Documentation tools** (e.g. Datamanager-type QA logging) | Logging what was installed, with photos, per penetration | vendor documentation |

Gennemført does **not** claim to be first with: penetration detection in BIM (Hilti does it in Revit), QR labels and
photo documentation (Hilti Documentation Manager), or a tested-solution selector (every manufacturer has one).

## Where Gennemført differs
1. **Open IFC, any authoring tool.** It reads the IFC model (walls, decks, pipes, ducts, cables, insulation coverings,
   systems, the architect's openings). No Revit licence, no plug-in, runs where the adviser is.
2. **The wholesaler's view, not one manufacturer's.** The tested-solution database is built from the ETA itself, so the
   same engine takes the ETAs of every brand a wholesaler carries. The demo holds ETA-21/0110 (Mulcol Multimastic C
   System, 293 tested rows from 38 tables).
3. **Citation first.** Every answer shows the ETA section, page and the highlighted table row it rests on, and every
   parameter as designed vs as tested. An adviser confirms in seconds instead of re-reading the ETA.
4. **Deviations are named, not just flagged.** "Godstykkelse 3,2 mm vs testet 3,4 mm", "Armaflex vs Kaiflex",
   "120 mm between seals vs ≥ 200 mm": the parameter, the nearest tested row, and a tested alternative when changing
   one parameter (e.g. the insulation) would make it compliant.
5. **Danish practice built in.** Brandteknisk vurdering drafts (facts and comparison filled in, the judgement left to
   the adviser), BR18 vocabulary, and documentation that fits the building owner's responsibility since 1 Jan 2025.
6. **You can ask it.** An MCP server lets any AI assistant answer an enquiry ("110 mm PVC through a 220 mm hollow-core
   deck at EI 60?") from the same engine, with the same citations.

## Honest gaps (and roadmap)
| Gap | Plan |
|---|---|
| One ETA in the database | Add the brands carried (collars, sealants, duct and steel protection); each new ETA is extracted, then every row checked on a proof sheet |
| Fictitious demonstration model | Pilot on a real project IFC (MEP consultant's model with openings) |
| ETA tables need human verification after extraction (merged cells) | Proof sheet per page; rows that the PDF text layer garbles are typed by hand and marked |
| No field app back-end (photo upload, sign-off) | The IFC pset already has the inspection fields; connect to an existing documentation tool rather than building one |
| Field of direct application (EN 1366-3) not encoded | Encode the standard's rules for pipe diameter/wall thickness extensions as a second layer, clearly separated from "as tested" |
| Decision support, not approval | By design: the adviser confirms; a person writes and signs every brandteknisk vurdering |

## One-line pitches
- *Fire-protection adviser:* "Every penetration in the model, checked against the exact ETA row, with the page to prove it,
  and a vurdering draft for the ones that deviate."
- *Contractor / installer:* "Know before the first hole is cut which seals are tested and which need an assessment."
- *Building owner:* "A penetration register with IDs, labels and the evidence for each seal: documentation you can rely on."
