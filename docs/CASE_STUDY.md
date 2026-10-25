# Case study: Gennemført on a demonstration apartment block

## The problem
A penetration seal is only approved for the exact set-up that was fire-tested: the construction and its thickness,
the pipe material, diameter and wall thickness, the insulation (type, thickness, even the product), the pipe-end
configuration and the seal geometry. Projects drift away from the tested set-up in small ways (a 110 mm drain with
3.2 mm wall instead of 3.4 mm, Armaflex instead of the tested Kaiflex, two seals 120 mm apart), and those drifts are
usually found on site, late, one enquiry at a time. Since 1 January 2025 the building owner must make sure the work has
been inspected, so documentation per penetration matters more than before.

## The idea
Use what the project already has: the IFC model (walls and decks with their fire rating, pipes with material and
size, insulation as coverings, systems, the architect's openings) and the manufacturer's ETA. Turn the ETA's Annex A
tables into records, find every penetration in the model, and compare one with the other, parameter by parameter,
keeping the page and row so a person can confirm every answer.

## What it does
1. **ETA to records.** 293 tested configurations from 38 tables of ETA-21/0110, with page, section and row rectangle.
   Merged cells are filled down; rows the PDF text layer garbles were typed from the page and marked.
2. **Find.** Every pipe, duct, cable and tray whose axis passes through a fire-rated wall or deck, with its opening,
   insulation and system type. A crossing of an unrated partition is ignored.
3. **Check.** 14 checks per tested row; the steel tables' intermediate-size graphs are interpolated; open vs closed
   systems set the pipe-end configuration that must be covered.
4. **Explain.** Tested rows that match, or the nearest row with the deviating parameter named, and a tested
   alternative where changing one parameter (usually the insulation) would make it compliant.
5. **Document.** Excel register, PDF register with QR labels, BCF issues, seal objects in the IFC, and brandteknisk
   vurdering drafts grouped by identical deviation.
6. **Ask.** A browser checker for phone enquiries and an MCP server for AI assistants, both on the same rules.

## What it found (demonstration block, 58 penetrations)
- 36 seals tested as built.
- 110x3.2 PVC drains in the hollow-core decks: nearest test is 110x3.4 (A.4.5, p. 52), wall thickness deviates.
- Copper water pipes insulated with Armaflex where the tested deck solution names Kaiflex ST (A.4.8, p. 56).
- Copper hot-water pipes with 30 mm stone wool through the decks: the stone-wool deck rows give E only or EI 45 (A.4.4,
  p. 48); the tested alternative is 9-13 mm elastomeric insulation with Multiwrap (A.4.8, EI 60).
- PP 50 branches through the 100 mm shaft walls: tested only up to Ø32 (A.1.4, p. 14).
- A tray and a cable bundle 120 mm apart: the ETA requires 200 mm between seals.
- PP 75 stacks in the decks: no tested PP configuration in floors in this ETA.
- A ventilation duct: fire damper or duct fire insulation instead.
- One pipe with no material in the model: returned as questions, not guessed.

## How we know it works
- A hand-written answer key for every planted case (status, deviating parameter, alternative): 59/59, no extra finds.
- 18 enquiries derived by hand from the ETA pages: all correct.
- The browser engine and the Python engine agree on 600 of 600 random enquiries.
- The MCP server passes an end-to-end test through the official client, and a live Claude session answered a phone
  enquiry correctly with section and page.

## What it is not
Not an approval and not a replacement for the certified fire consultant or the adviser's judgement. It is the
groundwork: the facts, the comparison and the documentation, so the adviser's time goes to the judgement.
