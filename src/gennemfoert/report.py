"""Issued brandteknisk vurdering (PDF), structured as the advisory service describes its own deliverable:

  1. Beskrivelse af den konkrete konstruktion og installation
  2. Gennemgang af afvigelsen fra eksisterende dokumentation (designed vs tested, with the ETA row)
  3. Faglig vurdering baseret på testdata, klassifikationsrapporter og dokumenterede løsninger (the adviser's argument)
  4. Anvisning af en mulig løsningsmodel
  5. Forudsætninger og begrænsninger
  6. Dokumentation: sources, knowledge-base version, audit trail, signatures, verification code + QR

The verification code is a hash of the case, the decision, the cited rows and the knowledge-base version; the QR opens
a page that says whether the assessment is genuine and still valid (not superseded by a later model revision).
"""
import hashlib
import io
import json
from pathlib import Path

import pymupdf
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import engine
from . import fonts

ROOT = Path(__file__).resolve().parents[2]
SRC = {"ETA-21/0110": ROOT / "data" / "eta" / "source" / "ETA-21-0110_Mulcol_Multimastic_C.pdf",
       "ETA-20/1322": ROOT / "data" / "eta" / "source" / "multicollar_eta.pdf"}
VERIFY_URL = "https://abdullah13793-commits.github.io/gennemfoert/v2/verify.html#"
INK, MUTED, ACC = colors.HexColor("#111827"), colors.HexColor("#6B7280"), colors.HexColor("#B7791F")


def kb_version():
    h = hashlib.sha256()
    for p in sorted(engine.KB_FILES.values()):
        if Path(p).exists():
            h.update(Path(p).read_bytes())
    return h.hexdigest()[:12]


def verification_code(case, item):
    body = {"case": case["id"], "item": item["no"], "decision": item.get("decision"), "kb": kb_version(),
            "rows": [m["id"] for m in (item["verdict"]["nearest"] or item["verdict"]["matches"])[:2]]}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16].upper()


def eta_crop(rec_brief, width_mm=170):
    """PNG of the cited ETA table area with the row highlighted."""
    pdf = SRC.get(rec_brief["eta"])
    if not pdf or not pdf.exists() or not rec_brief.get("row_bbox"):
        return None
    doc = pymupdf.open(pdf)
    page = doc[rec_brief["page"] - 1]
    rb = rec_brief["row_bbox"]
    clip = pymupdf.Rect(14, max(0, rb[1] - 110), page.rect.width - 14, min(page.rect.height, rb[3] + 50))
    hl = page.add_rect_annot(pymupdf.Rect(16, rb[1] - 1, page.rect.width - 16, rb[3] + 1))
    hl.set_colors(stroke=(0.94, 0.63, 0.13), fill=(1.0, 0.85, 0.4))
    hl.set_opacity(0.35)
    hl.update()
    pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=clip)
    buf = io.BytesIO(pix.tobytes("png"))
    w = width_mm * mm
    return Image(buf, width=w, height=w * pix.height / pix.width)


def _qr(text, size=26 * mm):
    w = QrCodeWidget(text)
    b = w.getBounds()
    d = Drawing(size, size, transform=[size / (b[2] - b[0]), 0, 0, size / (b[3] - b[1]), 0, 0])
    d.add(w)
    return d


def build(case, item_no, out):
    pdfmetrics.registerFont(TTFont("Seg", fonts.path()))
    pdfmetrics.registerFont(TTFont("SegB", fonts.path(True)))
    it = next(i for i in case["items"] if i["no"] == item_no)
    dec = it.get("decision") or {}
    v = it["verdict"]
    ref = (v["nearest"] or v["matches"])[0] if (v["nearest"] or v["matches"]) else None
    code = verification_code(case, it)
    st = {k: ParagraphStyle(k, fontName=f, fontSize=s, leading=s * 1.38, textColor=c, spaceAfter=a)
          for k, f, s, c, a in [("b", "Seg", 9.6, INK, 4), ("h", "SegB", 12, INK, 6), ("t", "SegB", 18, INK, 2), ("m", "Seg", 8.6, MUTED, 2),
                                ("cell", "Seg", 8.6, INK, 0)]}
    P = lambda t, s="b": Paragraph(t, st[s])
    c, s = it["construction"], it["service"]
    story = [P("Brandteknisk vurdering", "t"), P(f"Sag {case['id']}, punkt {it['no']} · {case['project']['address']} · udstedt "
                                                 f"{(dec.get('at') or case['created'])[:10]}", "m"), Spacer(1, 6)]
    head = Table([[P("<b>Afgørelse</b>", "cell"), P({"GODKENDT": "Godkendt", "BETINGET": "Godkendt på betingelser", "AFVIST": "Ikke godkendt"}
                                                    .get(dec.get("decision"), "-"), "cell"),
                   P("<b>Verifikationskode</b>", "cell"), P(code, "cell")]], colWidths=[28 * mm, 52 * mm, 34 * mm, 56 * mm])
    head.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF7E6")), ("BOX", (0, 0), (-1, -1), 0.6, ACC),
                              ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [head, Spacer(1, 10)]
    story += [P("1. Konstruktion og installation", "h"),
              P(f"Konstruktion: {c.get('label') or c.get('kind')}, {c.get('thickness_mm')} mm, krav EI {c.get('ei_required')}"
                + (" (huldæk)" if c.get("hollow_core") else "") + "."),
              P(f"Installation: {s.get('label') or s.get('kind')}" + (f", Ø{s.get('od_mm'):g} x {s.get('wall_mm'):g} mm" if s.get('od_mm') and s.get('wall_mm') else "")
                + (f", isolering {s['insulation'].get('product')} {s['insulation'].get('thickness_mm')} mm" if isinstance(s.get("insulation"), dict) else ", uisoleret")
                + (f", {'åbent' if s.get('system') == 'open' else 'lukket'} system" if s.get("system") else "")
                + (f", hul {it['aperture_mm'][0]} x {it['aperture_mm'][1]} mm" if it.get("aperture_mm") else "") + ".")]
    story += [P("2. Afvigelse fra den testede opbygning", "h")]
    if ref:
        story += [P(f"Nærmeste testede opbygning: <b>{ref['eta']} {ref['section']}</b>, side {ref['page']} ({ref.get('system')}): "
                    f"{ref['service']}, {ref['classification']}" + (f", {ref['insulation']}" if ref.get("insulation") else "") + ".")]
        rows = [[P("<b>Parameter</b>", "cell"), P("<b>Projekteret</b>", "cell"), P("<b>Testet</b>", "cell"), P("<b></b>", "cell")]]
        for ch in ref["checks"]:
            rows.append([P(ch["check"], "cell"), P(str(ch["actual"]), "cell"), P(str(ch["tested"]) + (f" ({ch['note']})" if ch.get("note") else ""), "cell"),
                         P("OK" if ch["ok"] else "<font color='#C2410C'><b>afviger</b></font>", "cell")])
        tb = Table(rows, colWidths=[38 * mm, 42 * mm, 72 * mm, 18 * mm], repeatRows=1)
        tb.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                                ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story += [tb, Spacer(1, 6)]
        img = eta_crop(ref)
        if img:
            story += [KeepTogether([P(f"Uddrag af {ref['eta']}, side {ref['page']} (den citerede række markeret):", "m"), img])]
    story += [P("3. Faglig vurdering", "h"), P(dec.get("argument", "-").replace("\n", "<br/>"))]
    if dec.get("precedents"):
        story += [P("Sammenlignelige tidligere afgørelser: " + ", ".join(dec["precedents"]), "m")]
    story += [P("4. Løsningsmodel", "h")]
    sol = []
    if v.get("alternatives"):
        a = v["alternatives"][0]
        sol.append(f"Testet alternativ: {a['eta']} {a['section']} (side {a['page']}), kræver ændring af: {', '.join(a['deviates'])}.")
    sol += dec.get("conditions") or []
    story += [P("• " + x) for x in sol] or [P("-")]
    story += [P("5. Forudsætninger og begrænsninger", "h")]
    for x in (v.get("conditions") or []) + [
            "Vurderingen er projektspecifik og bygger på de oplysninger og det materiale, der er fremsendt.",
            "Vurderingen gælder alene for den beskrevne løsning og under de anførte forudsætninger.",
            "Ændringer i konstruktion, installation, materialer, produkter eller udførelse kan medføre, at vurderingen ikke længere er gældende "
            "og skal revurderes."]:
        story += [P("• " + x)]
    story += [P("6. Dokumentation og sporbarhed", "h")]
    ev = case.get("events", [])
    author = dec.get("author", "-")
    reviewer = next((e["actor"] for e in reversed(ev) if e["action"] == "kontrol_godkendt"), "-")
    doc_rows = [["Kilder", ", ".join(sorted({m['eta'] for m in (v['nearest'] + v['matches'] + v['alternatives'])})) + " (ETA-Danmark); EN 1366-3; EN 13501-2; BR18"],
                ["Vidensbase-version", kb_version()], ["Hændelseslog", f"{len(ev)} hændelser, kæde-hash {ev[-1]['hash'][:12] if ev else '-'}"],
                ["Udarbejdet af", author], ["Kontrolleret af (4 øjne)", reviewer]]
    dt = Table([[P(f"<b>{a}</b>", "cell"), P(b, "cell")] for a, b in doc_rows], colWidths=[42 * mm, 100 * mm])
    dt.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    qr = _qr(VERIFY_URL + code)
    story += [Table([[dt, [qr, P(f"Scan for at kontrollere, at vurderingen er ægte og gældende · {code}", "m")]]],
                    colWidths=[145 * mm, 30 * mm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")])]
    story += [Spacer(1, 8), P("Demonstration: sag, projekt og afgørelse er fiktive eksempler. Beslutningsstøtte; vurderingen udarbejdes og underskrives af en person.", "m")]

    def deco(cv, d):
        cv.saveState()
        cv.setFillColor(ACC)
        cv.rect(0, A4[1] - 6 * mm, A4[0], 6 * mm, stroke=0, fill=1)
        cv.setFont("Seg", 7.5)
        cv.setFillColor(MUTED)
        cv.drawString(18 * mm, 10 * mm, f"Brandteknisk vurdering · {case['id']}-{it['no']} · verifikationskode {code}")
        cv.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Side {d.page}")
        cv.restoreState()
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
                            title=f"Brandteknisk vurdering {case['id']}-{it['no']}", author="")
    doc.build(story, onFirstPage=deco, onLaterPages=deco)
    return code
