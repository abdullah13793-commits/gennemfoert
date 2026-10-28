# Case study: from a free-text enquiry to a verifiable assessment

**Situation.** A fire-protection advisory answers enquiries about penetration seals. Customers describe the task in free text; the adviser
reads it, asks for missing measurements, looks the set-up up in the ETA, and writes a brandteknisk vurdering when it deviates. Advisers sit
in two offices. Since 2025 the building owner must be able to show that the work was inspected.

**What v1 proved.** Valid-as-tested checking with page-and-row citations works on an IFC model: 59/59 planted penetrations right,
deviations named by parameter.

**What v2 changes.**
1. *The enquiry becomes data.* In the demo, a customer enters three penetration types. The PVC-U 110 × 3.2 drain in a hollow-core deck is
   answered immediately as tested with a fire collar (ETA-20/1322 B.1.1.1, p. 155, one collar on the underside, 3 Multiclips, annular gap
   filled with Multimortar). The PP 75 × 2.6 drain is flagged: wall thickness below the tested 2.7 mm. The copper pipe is missing two
   photos, and the customer sees that before sending.
2. *The case gets a trail.* The west office picks it up. The precedent library shows an earlier conditional approval for a thin-walled PP
   drain in the same kind of construction. The adviser writes their own argument (the system refuses copy-paste-short text) and saves the
   draft. The system refuses the adviser's attempt to review it; a colleague approves; it is sent. Every step is hash-chained. Editing any
   line afterwards turns the chain red, in the browser, for anyone.
3. *The answer travels.* The issued PDF carries the ETA excerpt and a verification code. The same solution produces the material list
   (item numbers, quantities, basis) and the installer's checklist on site; the inspector must be a different person; the owner gets
   the handover package.
4. *Revisions don't slip through.* Revision B of the model changes three drains' wall thickness and raises one party wall to EI 90. Five
   penetrations are flagged; their decisions need re-assessment.

**Numbers (simulation, fictitious data).** 35 % of penetrations answered without an adviser, 20 % of missing information caught at intake,
median 2.7 days from receipt to sent, four eyes on every issued assessment, 30/30 audit chains intact.

**Engineering.** One rules engine in Python, ported to the browser and held identical by tests (1,500 random queries, every check's text).
MCP server with 14 tools so an assistant can do the same lookups with the same citations.
