"""Gennemføringsregister: XLSX (register, material estimate, deviations) and PDF (register + QR site labels)."""
import json
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from . import text

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
SITE = "https://abdullah13793-commits.github.io/gennemfoert/app/#"
FILL = {"TESTET": "1F9D57", "AFVIGELSE": "E8A317", "IKKE_DAEKKET": "D63B3B", "ANDET_SYSTEM": "6B7BD6", "MANGLER_DATA": "8A8F98"}


def _board_layers(board):
    if not board:
        return 0
    return int(board.split(" ")[1].split("x")[0])


def materials(pens):
    """Indicative quantities for the TESTET seals (board area, perimeter sealant, wraps). Not a price basis."""
    board = defaultdict(float)
    sp_m, wraps, seals = 0.0, 0, 0
    for p in pens:
        v = p["verdict"]
        if v["status"] != "TESTET" or not p.get("aperture_mm"):
            continue
        m = v["matches"][0]
        if not m.get("board"):
            continue
        seals += 1
        w, h = p["aperture_mm"]
        typ = m["board"].split(" ")[0] + " " + m["board"].split(" ")[1].split("x")[1]
        board[f"Multimastic {typ}"] += _board_layers(m["board"]) * w * h / 1e6
        sp_m += 2 * 2 * (w + h) / 1000          # perimeter, both faces of the seal
        if m.get("wrap"):
            wraps += 2 if "each" in m["wrap"].lower() or "either side" in m["wrap"].lower() else 1
    return {"seals": seals, "board_m2": {k: round(v, 2) for k, v in board.items()}, "sealant_perimeter_m": round(sp_m, 1),
            "multiwrap_pcs": wraps}


def write_xlsx(pens, stats, out=None):
    out = out or OUT / "Gennemfoeringsregister.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Register"
    head = ["ID", "Etage", "Konstruktion", "Tykkelse (mm)", "Krav", "Gennemføring", "System", "Hul (mm)", "Status", "Løsning / nærmeste test",
            "Afviger på", "Handling", "Udført af", "Kontrolleret af", "Dato", "Foto"]
    ws.append(head)
    for p in pens:
        s, h, v = p["service"], p["host"], p["verdict"]
        best = (v["matches"] or v["nearest"] or [None])[0]
        ws.append([p["id"], s["storey"], h["name"], h["thickness_mm"], h["rating"], text.service_line(s), s.get("system") or "",
                   " x ".join(map(str, p["aperture_mm"])) if p.get("aperture_mm") else "", text.STATUS[v["status"]],
                   text.solution_line(v), ", ".join(best["deviates"]) if best and best.get("deviates") else "", text.ACTION[v["status"]],
                   "", "", "", ""])
        ws.cell(ws.max_row, 9).fill = PatternFill("solid", fgColor=FILL[v["status"]])
        ws.cell(ws.max_row, 9).font = Font(color="FFFFFF", bold=True)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F2937")
        c.alignment = Alignment(vertical="center", wrap_text=True)
    widths = [10, 11, 30, 9, 8, 38, 15, 10, 26, 52, 24, 44, 12, 14, 10, 10]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions
    m = materials(pens)
    ws2 = wb.create_sheet("Mængder (vejledende)")
    ws2.append(["Post", "Mængde", "Enhed", "Grundlag"])
    for k, a in m["board_m2"].items():
        ws2.append([k, a, "m²", "Hulareal x antal lag, kun testede tætninger"])
    ws2.append(["Multimastic SP (fuge i kant)", m["sealant_perimeter_m"], "m", "Hullets omkreds"])
    ws2.append(["Mulcol Multiwrap", m["multiwrap_pcs"], "stk", "Efter ETA-rækkens wrap-krav"])
    ws2.append([])
    ws2.append(["Vejledende mængder til tilbud og indkøb. Spild, tilskæring og produktvalg vurderes af rådgiver."])
    for c in ws2[1]:
        c.font = Font(bold=True)
    ws2.column_dimensions["A"].width, ws2.column_dimensions["D"].width = 34, 48
    ws3 = wb.create_sheet("Afvigelser")
    ws3.append(["ID", "Gennemføring", "Konstruktion", "Nærmeste test (ETA, afsnit, side)", "Parameter", "Projekteret", "Testet",
                "Testet alternativ"])
    for p in pens:
        v = p["verdict"]
        if v["status"] not in ("AFVIGELSE", "IKKE_DAEKKET") or not v["nearest"]:
            continue
        nb = v["nearest"][0]
        alt = v["alternatives"][0] if v["alternatives"] else None
        for c in nb["checks"]:
            if not c["ok"]:
                ws3.append([p["id"], text.service_line(p["service"]), p["host"]["name"], f"{nb['eta']} {nb['section']}, s. {nb['page']}",
                            c["check"], c["actual"], c["tested"],
                            f"{alt['section']} s. {alt['page']}: {alt['insulation']}" if alt else ""])
    for c in ws3[1]:
        c.font = Font(bold=True)
    for i, w in enumerate([10, 38, 30, 28, 22, 22, 30, 40], 1):
        ws3.column_dimensions[get_column_letter(i)].width = w
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out, m


def _font():
    pdfmetrics.registerFont(TTFont("Seg", r"C:\Windows\Fonts\segoeui.ttf"))
    pdfmetrics.registerFont(TTFont("SegB", r"C:\Windows\Fonts\segoeuib.ttf"))


def write_pdf(pens, stats, project="Blok C, etageboliger (demonstration)", out=None):
    out = out or OUT / "Gennemfoeringsregister.pdf"
    _font()
    W, H = landscape(A4)
    c = canvas.Canvas(str(out), pagesize=(W, H))
    c.setTitle("Gennemføringsregister")
    c.setAuthor("")
    cnt = Counter(p["verdict"]["status"] for p in pens)
    # page 1: summary + table
    def header(title):
        c.setFillColor(colors.HexColor("#111827"))
        c.rect(0, H - 22 * mm, W, 22 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("SegB", 16)
        c.drawString(14 * mm, H - 13 * mm, title)
        c.setFont("Seg", 9)
        c.drawString(14 * mm, H - 18.5 * mm, f"{project} · {len(pens)} gennemføringer af brandadskillende bygningsdele · grundlag ETA-21/0110")
    header("Gennemføringsregister")
    x = 14 * mm
    for st in ["TESTET", "AFVIGELSE", "IKKE_DAEKKET", "ANDET_SYSTEM", "MANGLER_DATA"]:
        c.setFillColor(colors.HexColor("#" + FILL[st]))
        c.roundRect(x, H - 40 * mm, 50 * mm, 13 * mm, 2 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("SegB", 15)
        c.drawString(x + 4 * mm, H - 33.5 * mm, str(cnt.get(st, 0)))
        c.setFont("Seg", 8.5)
        c.drawString(x + 14 * mm, H - 33 * mm, text.SHORT[st])
        x += 53 * mm
    cols = [("ID", 15), ("Etage", 15), ("Konstruktion", 38), ("Krav", 13), ("Gennemføring", 66), ("Status", 52), ("Løsning / nærmeste test", 80)]
    y = H - 50 * mm

    def table_head(y):
        c.setFont("SegB", 7.5)
        c.setFillColor(colors.HexColor("#374151"))
        xx = 14 * mm
        for name, wmm in cols:
            c.drawString(xx, y, name)
            xx += wmm * mm
        return y - 5 * mm
    y = table_head(y)
    c.setFont("Seg", 7)
    for i, p in enumerate(pens):
        if y < 14 * mm:
            c.showPage()
            header("Gennemføringsregister (fortsat)")
            y = table_head(H - 30 * mm)
            c.setFont("Seg", 7)
        v = p["verdict"]
        if i % 2 == 0:
            c.setFillColor(colors.HexColor("#F3F4F6"))
            c.rect(13 * mm, y - 1.6 * mm, W - 26 * mm, 5 * mm, stroke=0, fill=1)
        vals = [p["id"], p["service"]["storey"], f"{text.HOST[p['host']['kind']]} {p['host']['thickness_mm']} mm", p["host"]["rating"],
                text.service_line(p["service"]), text.STATUS[v["status"]], text.solution_line(v)]
        xx = 14 * mm
        for (name, wmm), val in zip(cols, vals):
            if name == "Status":
                c.setFillColor(colors.HexColor("#" + FILL[v["status"]]))
                c.circle(xx + 1.2 * mm, y + 0.9 * mm, 1.2 * mm, stroke=0, fill=1)
                c.setFillColor(colors.HexColor("#111827"))
                c.drawString(xx + 3.5 * mm, y, str(val)[:36])
            else:
                c.setFillColor(colors.HexColor("#111827"))
                s = str(val)
                maxc = int(wmm * 0.62)
                c.drawString(xx, y, s if len(s) <= maxc else s[:maxc - 1] + "…")
            xx += wmm * mm
        y -= 5 * mm
    c.setFont("Seg", 6.5)
    c.setFillColor(colors.HexColor("#6B7280"))
    c.drawString(14 * mm, 8 * mm, text.DISCLAIMER)
    # labels: 3 x 7 per A4 portrait-like grid on landscape: 4 x 4
    c.showPage()
    lw, lh = (W - 20 * mm) / 4, (H - 20 * mm) / 4
    for i, p in enumerate(pens):
        k = i % 16
        if k == 0 and i:
            c.showPage()
        col, row = k % 4, k // 4
        x0, y0 = 10 * mm + col * lw, H - 10 * mm - (row + 1) * lh
        v = p["verdict"]
        c.setStrokeColor(colors.HexColor("#D1D5DB"))
        c.setDash(2, 2)
        c.rect(x0, y0, lw, lh, stroke=1, fill=0)
        c.setDash()
        c.setFillColor(colors.HexColor("#" + FILL[v["status"]]))
        c.rect(x0, y0 + lh - 7 * mm, lw, 7 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("SegB", 11)
        c.drawString(x0 + 3 * mm, y0 + lh - 5 * mm, f"BRANDTÆTNING {p['id']}")
        qr = QrCodeWidget(SITE + p["id"])
        b = qr.getBounds()
        size = 26 * mm
        d = Drawing(size, size, transform=[size / (b[2] - b[0]), 0, 0, size / (b[3] - b[1]), 0, 0])
        d.add(qr)
        renderPDF.draw(d, c, x0 + lw - size - 2 * mm, y0 + 3 * mm)
        c.setFillColor(colors.HexColor("#111827"))
        c.setFont("SegB", 8)
        best = (v["matches"] or v["nearest"] or [None])[0]
        lines = [(f"{p['host']['rating']} · {text.HOST[p['host']['kind']]} {p['host']['thickness_mm']} mm", "Seg"),
                 (text.service_line(p["service"])[:40], "Seg"),
                 (text.STATUS[v["status"]], "SegB"),
                 ((f"{best['eta']} {best['section']} s.{best['page']}" if best else "–"), "Seg"),
                 ((best.get("board") or "") if best and v["status"] == "TESTET" else "", "Seg"),
                 ("Udført: ________  Kontrol: ________", "Seg")]
        yy = y0 + lh - 12 * mm
        for s, fnt in lines:
            c.setFont(fnt, 7.2)
            c.drawString(x0 + 3 * mm, yy, s)
            yy -= 4.3 * mm
    c.save()
    return out


if __name__ == "__main__":
    reg = json.loads((ROOT / "results" / "register.json").read_text(encoding="utf-8"))
    x, m = write_xlsx(reg["penetrations"], reg["stats"])
    p = write_pdf(reg["penetrations"], reg["stats"])
    (ROOT / "results" / "materials.json").write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")
    print(x.name, p.name, m)
