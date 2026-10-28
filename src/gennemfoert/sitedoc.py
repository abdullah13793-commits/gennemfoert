"""Site documentation and the building owner's handover package.

Each seal gets a checklist made from its own solution (the conditions of the cited ETA row), the installer signs it with
a photo, an inspector signs it off. The handover package is what the owner needs to show that the work was inspected:
one line per seal with the solution, the ETA reference, the checklist, signatures and photo, plus the issued
assessments. A CSV export carries the same rows to a documentation system.
"""
import csv
import datetime
import io
import json
import random
from pathlib import Path

from PIL import Image as PImage, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import text
from . import fonts

ROOT = Path(__file__).resolve().parents[2]


def checklist(p):
    v = p["verdict"]
    best = (v["matches"] or [None])[0]
    items = ["Hullet rengjort for støv, snavs og fedt", "Mærkat med ID og løsning opsat ved tætningen"]
    if best and best.get("system") == "Multicollar Slim":
        n = best.get("collars_per_face") or 1
        where = "på dækkets underside" if p["host"]["kind"] == "rigid_floor" else "pr. side af væggen"
        items += [f"Multicollar Slim: {n} {where}, lukket med Multiclips og skruer", "Ringspalte fuget (≤ 20 mm) eller udfyldt med Multimortar (dæk)"]
    if best and best.get("board"):
        items += [f"Multimastic {best['board']} skåret tæt om installationen", "Multimastic C coating og SP-fuge i kanten"]
    if best and best.get("wrap"):
        items += [f"Multiwrap: {best['wrap']}"]
    if best and best.get("insulation_length"):
        items += [f"Isolering min. {best['insulation_length']:g} mm på hver side"]
    items += ["Installationen understøttet som anført i løsningen"]
    return items


def illustration(pid, system, out):
    """A labelled schematic (not a photo) used in the demonstration where a site photo would be."""
    im = PImage.new("RGB", (480, 300), (238, 240, 243))
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(fonts.path(), 16)
    fb = ImageFont.truetype(fonts.path(True), 18)
    d.rectangle([60, 40, 420, 260], fill=(205, 208, 214))
    d.rectangle([60, 130, 420, 170], fill=(150, 156, 166))
    if system == "Multicollar Slim":
        for x in (160, 300):
            d.rectangle([x, 112, x + 18, 188], fill=(120, 124, 132), outline=(70, 70, 70))
    else:
        d.rectangle([200, 95, 280, 205], fill=(232, 220, 196), outline=(140, 120, 90))
    d.text((14, 10), f"{pid} · illustration, ikke foto", font=fb, fill=(30, 30, 30))
    d.text((14, 272), system or "", font=f, fill=(60, 60, 60))
    im.save(out)
    return out


def simulate_site(pens, rng=None, date0=datetime.date(2026, 10, 5)):
    rng = rng or random.Random(7)
    recs = {}
    for k, p in enumerate(pens):
        if p["verdict"]["status"] != "TESTET":
            continue
        if p["service"]["storey"] not in ("Kælder", "Stueetage"):
            continue
        d = date0 + datetime.timedelta(days=k % 9)
        ok = [True] * len(checklist(p))
        if k % 11 == 3:
            ok[1] = False                                   # label missing: caught at inspection
        recs[p["id"]] = {"installer": rng.choice(["Isolatør A", "Isolatør B"]), "installed": d.isoformat(), "checklist": ok,
                         "inspector": "Kontrollant (bygherre)" if all(ok) else None, "inspected": (d + datetime.timedelta(days=2)).isoformat() if all(ok) else None,
                         "remark": None if all(ok) else "Mærkat mangler, genbesøg"}
    return recs


def package(pens, site, project, out_pdf, out_csv, img_dir):
    pdfmetrics.registerFont(TTFont("Seg", fonts.path()))
    pdfmetrics.registerFont(TTFont("SegB", fonts.path(True)))
    st = {k: ParagraphStyle(k, fontName=f, fontSize=s, leading=s * 1.35, textColor=colors.HexColor("#111827"), spaceAfter=a)
          for k, f, s, a in [("b", "Seg", 9, 3), ("h", "SegB", 13, 6), ("t", "SegB", 20, 4), ("c", "Seg", 8, 0), ("m", "Seg", 8, 2)]}
    P = lambda t, s="b": Paragraph(t, st[s])
    done = [p for p in pens if p["id"] in site]
    inspected = [p for p in done if site[p["id"]]["inspector"]]
    story = [P("Dokumentation af brandtætninger", "t"), P(f"{project} · overdragelse til bygherre · {datetime.date.today().isoformat()}", "m"), Spacer(1, 8)]
    kpi = [["Gennemføringer i registeret", str(len(pens))], ["Udført og dokumenteret", str(len(done))], ["Kontrolleret (bygherrens kontrol)", str(len(inspected))],
           ["Åbne bemærkninger", str(sum(1 for p in done if site[p["id"]]["remark"]))],
           ["Afvigelser med udstedt brandteknisk vurdering", "se registeret"]]
    t = Table([[P(a), P(f"<b>{b}</b>")] for a, b in kpi], colWidths=[110 * mm, 50 * mm])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB"))]))
    story += [t, Spacer(1, 8), P("Bygherren skal sikre, at arbejdet er kontrolleret (BR18, fra 1. januar 2025). Denne pakke samler, pr. tætning, "
                                 "den anvendte testede løsning med ETA-henvisning, udførelsens tjekliste, underskrifter og billede.", "b"), PageBreak()]
    img_dir.mkdir(parents=True, exist_ok=True)
    rows_csv = []
    for p in done:
        s = site[p["id"]]
        best = (p["verdict"]["matches"] or [{}])[0]
        img = illustration(p["id"], best.get("system"), img_dir / f"{p['id']}.png")
        cl = checklist(p)
        cl_rows = [[P(("OK " if ok else "<font color='#C2410C'><b>MANGLER</b></font> ") + c, "c")] for c, ok in zip(cl, s["checklist"])]
        info = [[P("<b>" + p["id"] + "</b> · " + text.service_line(p["service"]), "b")],
                [P(f"{p['host']['name']} ({p['host']['rating']}) · {p['service']['storey']}", "m")],
                [P(f"Løsning: {best.get('eta')} {best.get('section')} (s. {best.get('page')}), {best.get('system')}"
                   + (f", {best.get('board')}" if best.get("board") else ""), "c")]] + cl_rows + \
               [[P(f"Udført: {s['installer']} {s['installed']} · Kontrol: {s['inspector'] or '-'} {s['inspected'] or ''}"
                   + (f" · <font color='#C2410C'>{s['remark']}</font>" if s["remark"] else ""), "m")]]
        it = Table(info, colWidths=[110 * mm])
        block = Table([[it, Image(str(img), width=58 * mm, height=36 * mm)]], colWidths=[112 * mm, 60 * mm])
        block.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
                                   ("TOPPADDING", (0, 0), (-1, -1), 4)]))
        story += [block, Spacer(1, 6)]
        rows_csv.append({"id": p["id"], "etage": p["service"]["storey"], "konstruktion": p["host"]["name"], "krav": p["host"]["rating"],
                         "installation": text.service_line(p["service"]), "system": best.get("system"), "eta": best.get("eta"),
                         "afsnit": best.get("section"), "side": best.get("page"), "udfoert_af": s["installer"], "udfoert_dato": s["installed"],
                         "kontrol_af": s["inspector"] or "", "kontrol_dato": s["inspected"] or "", "bemaerkning": s["remark"] or ""})
    story += [Spacer(1, 6), P("Billeder i denne demonstration er skematiske illustrationer, ikke fotos. Projektet er fiktivt.", "m")]
    SimpleDocTemplate(str(out_pdf), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                      title="Dokumentation af brandtætninger", author="").build(story)
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_csv[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(rows_csv)
    return {"seals": len(pens), "documented": len(done), "inspected": len(inspected), "remarks": sum(1 for p in done if site[p['id']]["remark"])}


if __name__ == "__main__":
    reg = json.loads((ROOT / "results" / "register.json").read_text(encoding="utf-8"))
    site = simulate_site(reg["penetrations"])
    (ROOT / "results" / "site.json").write_text(json.dumps(site, indent=1, ensure_ascii=False), encoding="utf-8")
    r = package(reg["penetrations"], site, "Blok C, etageboliger (demonstration)", ROOT / "out" / "Dokumentationspakke_bygherre.pdf",
                ROOT / "out" / "Dokumentation_brandtaetninger.csv", ROOT / "out" / "site_img")
    print(r)
