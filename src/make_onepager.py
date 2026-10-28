"""Two-page Danish leave-behind (A4): what Gennemført is, what it found, how it fits an adviser's day, a pilot.

python src/make_onepager.py [company]  ->  publish/Gennemfoert_<company>.pdf
"""
import json
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
COMPANY = sys.argv[1] if len(sys.argv) > 1 else None
pdfmetrics.registerFont(TTFont("Seg", r"C:\Windows\Fonts\segoeui.ttf"))
pdfmetrics.registerFont(TTFont("SegB", r"C:\Windows\Fonts\segoeuib.ttf"))
pdfmetrics.registerFont(TTFont("SegSB", r"C:\Windows\Fonts\seguisb.ttf"))
INK, INK2, MUTED = colors.HexColor("#111827"), colors.HexColor("#374151"), colors.HexColor("#6B7280")
ACC = colors.HexColor("#E8A317")
ST = {"TESTET": "#1F9D57", "AFVIGELSE": "#E8A317", "IKKE_DAEKKET": "#D63B3B", "ANDET_SYSTEM": "#6B7BD6", "MANGLER_DATA": "#8A8F98"}
W, H = A4
reg = json.loads((ROOT / "results" / "register.json").read_text(encoding="utf-8"))
ev = json.loads((ROOT / "results" / "evaluation.json").read_text(encoding="utf-8"))
par = json.loads((ROOT / "results" / "parity.json").read_text(encoding="utf-8"))
cnt = reg["stats"]["status"]
n = len(reg["penetrations"])


def para(c, x, y, text, width, font="Seg", size=9.5, lead=13.2, color=INK2):
    """Simple word-wrapped paragraph; returns the new y."""
    c.setFont(font, size)
    c.setFillColor(color)
    for raw in text.split("\n"):
        words, line = raw.split(" "), ""
        for w in words:
            t = (line + " " + w).strip()
            if pdfmetrics.stringWidth(t, font, size) > width:
                c.drawString(x, y, line)
                y -= lead
                line = w
            else:
                line = t
        c.drawString(x, y, line)
        y -= lead
    return y


def bullets(c, x, y, items, width, size=9.3, lead=12.8, gap=3.5):
    for b in items:
        c.setFillColor(ACC)
        c.circle(x + 1.6, y + 3.2, 1.5, stroke=0, fill=1)
        head, _, rest = b.partition(": ")
        if rest:
            c.setFont("SegB", size)
            c.setFillColor(INK)
            c.drawString(x + 7, y, head + ":")
            off = pdfmetrics.stringWidth(head + ": ", "SegB", size)
            words, line, first = rest.split(" "), "", True
            for w in words:
                t = (line + " " + w).strip()
                lim = width - 7 - (off if first else 0)
                if pdfmetrics.stringWidth(t, "Seg", size) > lim:
                    c.setFont("Seg", size)
                    c.setFillColor(INK2)
                    c.drawString(x + 7 + (off if first else 0), y, line)
                    y -= lead
                    line, first = w, False
                else:
                    line = t
            c.setFont("Seg", size)
            c.setFillColor(INK2)
            c.drawString(x + 7 + (off if first else 0), y, line)
        else:
            y = para(c, x + 7, y, b, width - 7, size=size, lead=lead) + lead
        y -= lead + gap
    return y


def img(c, path, x, y, w, h=None, radius=3 * mm):
    ir = ImageReader(str(path))
    iw, ih = ir.getSize()
    h = h or w * ih / iw
    c.saveState()
    p = c.beginPath()
    p.roundRect(x, y, w, h, radius)
    c.clipPath(p, stroke=0)
    c.drawImage(ir, x, y, w, h, preserveAspectRatio=False, mask="auto")
    c.restoreState()
    return h


out = ROOT / "publish" / (f"Gennemfoert_{COMPANY}.pdf" if COMPANY else "Gennemfoert_overblik.pdf")
c = canvas.Canvas(str(out), pagesize=A4)
c.setTitle("Gennemført: fra IFC-model til dokumenteret brandtætning")
c.setAuthor("")

# ---------------- page 1
hero_h = W * 0.56
img(c, ROOT / "renders" / "hero.png", 0, H - hero_h, W, hero_h, radius=0)
c.setFillColor(colors.Color(0, 0, 0, alpha=0.55))
c.rect(0, H - hero_h, W, 30 * mm, stroke=0, fill=1)
c.setFillColor(colors.white)
c.setFont("SegB", 26)
c.drawString(16 * mm, H - hero_h + 16 * mm, "Gennemført")
c.setFont("Seg", 11.5)
c.drawString(16 * mm, H - hero_h + 8.5 * mm, "Fra IFC-model til dokumenteret brandtætning, kontrolleret mod den testede opbygning.")
c.setFont("Seg", 8)
c.setFillColor(colors.Color(1, 1, 1, alpha=0.8))
c.drawRightString(W - 12 * mm, H - 8 * mm, "Demonstrationsbygning (fiktiv) · grundlag ETA-21/0110")

y = H - hero_h - 13 * mm
x0, colw = 16 * mm, (W - 32 * mm - 8 * mm) / 2
c.setFont("SegB", 13)
c.setFillColor(INK)
c.drawString(x0, y, "Problemet")
yl = bullets(c, x0, y - 7 * mm, [
    "Kun gyldig som testet: små afvigelser (godstykkelse, isoleringsfabrikat, dimension, afstand mellem tætninger) "
    "opdages sent, på pladsen, én forespørgsel ad gangen.",
    "Ufuldstændige forespørgsler: rådgiveren bruger tid på at spørge efter konstruktion, EI, rør, isolering og fotos.",
    "Bygherrens ansvar: siden 1. januar 2025 skal bygherren sikre, at arbejdet er kontrolleret. "
    "Dokumentationen pr. gennemføring skal kunne holde."], colw)
x1 = x0 + colw + 8 * mm
c.setFont("SegB", 13)
c.setFillColor(INK)
c.drawString(x1, y, "Hvad Gennemført gør")
yr = bullets(c, x1, y - 7 * mm, [
    f"Finder: alle rør, kanaler og kabler gennem brandadskillende vægge og dæk i IFC-modellen ({n} på {reg['stats']['seconds']:g} s).",
    "Tjekker: hver gennemføring mod ETA'ens testede rækker, 14 parametre, med afsnit, side og den markerede række.",
    "Forklarer: navngiver afvigelsen og den nærmeste testede række, og foreslår et testet alternativ.",
    "Dokumenterer: register (Excel/PDF med QR-etiketter), BCF-sager, tætninger i IFC og udkast til brandteknisk vurdering.",
    "Svarer: 'Tjek en gennemføring' i browseren og en MCP-server, så en AI-assistent kan svare med kildehenvisning."], colw)
y = min(yl, yr) - 2 * mm
# status strip
c.setFont("SegB", 11)
c.setFillColor(INK)
c.drawString(x0, y, f"Resultat på demonstrationsbygningen: {n} gennemføringer")
y -= 13 * mm
bx = x0
labels = {"TESTET": "testet som bygget", "AFVIGELSE": "afvigelser, navngivet", "IKKE_DAEKKET": "ingen testet løsning",
          "ANDET_SYSTEM": "andet system (kanal)", "MANGLER_DATA": "mangler data"}
bw = (W - 32 * mm - 4 * 4 * mm) / 5
for k in ["TESTET", "AFVIGELSE", "IKKE_DAEKKET", "ANDET_SYSTEM", "MANGLER_DATA"]:
    c.setFillColor(colors.HexColor(ST[k]))
    c.roundRect(bx, y - 4 * mm, bw, 13 * mm, 2 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("SegB", 17)
    c.drawString(bx + 3 * mm, y + 2.5 * mm, str(cnt.get(k, 0)))
    c.setFont("Seg", 7.4)
    c.drawString(bx + 3 * mm, y - 1.6 * mm, labels[k])
    bx += bw + 4 * mm
y -= 13 * mm
y = para(c, x0, y, f"Kontrolleret mod en håndskrevet facitliste: {ev['correct']}/{ev['planted']} rigtige (status, afvigende parameter, alternativ), "
         f"ingen ekstra fund. 18 forespørgsler afledt i hånden fra ETA'ens sider: alle rigtige. Browser og server giver samme svar i "
         f"{par['identical']}/{par['queries']} tilfældige forespørgsler.", W - 32 * mm, size=9, lead=12.6, color=MUTED)
c.setFont("Seg", 7.5)
c.setFillColor(MUTED)
c.drawString(x0, 10 * mm, "Beslutningsstøtte, ikke godkendelse: rådgiveren bekræfter mod kildedokumentet, og en person underskriver hver brandteknisk vurdering.")
c.showPage()

# ---------------- page 2
y = H - 16 * mm
c.setFont("SegB", 14)
c.setFillColor(INK)
c.drawString(x0, y, "Svaret med beviset ved siden af")
from PIL import Image as _I
crop = ROOT / "publish" / "_card_crop.png"
_I.open(ROOT / "publish" / "03_app_deviation.png").crop((934, 188, 1588, 1000)).save(crop)
cw = 92 * mm
ch = img(c, crop, W - 16 * mm - cw, y - 6 * mm - cw * 812 / 654, cw)
crop.unlink()
tw = W - 32 * mm - cw - 7 * mm
yy = para(c, x0, y - 10 * mm, "Eksempel fra registeret: kobberrør Ø22 med Armaflex AF 13 mm gennem et 220 mm huldæk, krav REI 60.",
          tw, font="SegB", size=9.6, lead=13.2, color=INK)
yy = para(c, x0, yy - 2 * mm, "Den nærmeste testede opbygning er ETA-21/0110 A.4.8, side 56: samme rør, samme dimension, samme "
          "isoleringstykkelse, men testet med Kaiflex ST. Afvigelsen er isoleringsfabrikatet, og det står i én linje, med den markerede "
          "række fra ETA'en ved siden af.", tw, size=9.2, lead=12.8)
yy = para(c, x0, yy - 2 * mm, "Alle 14 parametre vises som projekteret mod testet: konstruktion, tykkelse, materiale, diameter, "
          "godstykkelse, isolering (type, tykkelse, fabrikat), klassifikation, rørende, hulstørrelse, kantafstand, afstand mellem "
          "tætninger og fyldningsgrad.", tw, size=9.2, lead=12.8)
yy = para(c, x0, yy - 2 * mm, "Hvor en ændring af én parameter giver en testet løsning, foreslås den: fx kobber med 30 mm stenuld i "
          "dæk (kun E-klassificeret) mod 9-13 mm elastomer med Multiwrap (A.4.8, EI 60).", tw, size=9.2, lead=12.8)
y = min(yy, y - 6 * mm - ch) - 6 * mm
c.setFont("SegB", 12.5)
c.setFillColor(INK)
c.drawString(x0, y, "Sådan passer det ind" + (f" hos {COMPANY}" if COMPANY else ""))
y = bullets(c, x0, y - 6.5 * mm, [
    "Før projektet: mængder og produktliste tidligt fra konsulentens IFC-model, til tilbud og salg.",
    "Ved forespørgslen: samme regler som en struktureret formular, så forespørgslen er komplet første gang.",
    "I vurderingen: fakta, sammenligning og citater er udfyldt, så rådgiverens tid går til selve vurderingen.",
    "Ved aflevering: register med ID'er, QR-etiketter og bevis pr. tætning, som bygherren kan bruge.",
    "Supplerer producenternes selectors (fx Multiselector) og dokumentationsværktøjer (fx Datamanager): "
    "det dækker tværs af de mærker, der sælges, og arbejder i åbne formater (IFC, BCF, Excel)."], W - 32 * mm, size=9.1, lead=12.4, gap=2)
y -= 1 * mm
c.setFont("SegB", 12.5)
c.setFillColor(INK)
c.drawString(x0, y, "Forslag til pilot")
y = bullets(c, x0, y - 6.5 * mm, [
    "Uge 1-2: de 5-10 mest solgte ETA'er ind i databasen (fx manchetter, Multimastic, Conlit), hver række kontrolleret.",
    "Uge 3-4: kør på ét rigtigt projekt fra en rådgiverkunde og sammenlign med den manuelle gennemgang.",
    "Uge 5-6: 'Tjek en gennemføring' som forespørgselsformular, og måling af hvor mange mails om manglende oplysninger der spares."],
    W - 32 * mm, size=9.1, lead=12.4, gap=2)
c.setFont("Seg", 7.5)
c.setFillColor(MUTED)
c.drawString(x0, 10 * mm, "Demonstrationsbygningen og dens installationer er fiktive. ETA-data fra det offentligt tilgængelige ETA-21/0110 (ETA-Danmark, 2021).")
c.save()
print(out)
