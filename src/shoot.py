"""Screenshots of the app (Edge headless, software WebGL). Needs: python -m http.server 8079 --directory web

python src/shoot.py check      -> scratch screenshots for review
python src/shoot.py gallery    -> publish/02_*.png ...
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = "http://localhost:8079/index.html"
ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]


def page(pw, w=1600, h=1000, theme="dark", mobile=False):
    b = pw.chromium.launch(channel="msedge", headless=True, args=ARGS)
    ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme=theme, device_scale_factor=1.5 if mobile else 1,
                        is_mobile=mobile, has_touch=mobile)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.goto(URL)
    pg.wait_for_function("window.G && window.G.ready", timeout=120000)
    pg.wait_for_timeout(600)
    return b, pg, errs


def shots(out, items, **kw):
    with sync_playwright() as pw:
        b, pg, errs = page(pw, **kw)
        for name, js, wait in items:
            if js:
                pg.evaluate(js)
            pg.wait_for_timeout(wait)
            pg.evaluate("G.frozen = true")
            pg.wait_for_timeout(200)
            pg.screenshot(path=str(out / f"{name}.png"), timeout=150000)
            pg.evaluate("G.frozen = false")
        b.close()
    print("ok", errs)


def gallery():
    out = ROOT / "publish"
    out.mkdir(exist_ok=True)
    shots(out, [("02_app_overview", "G.explode(true); G.camera([30,30,40],[18,4,-6]); G.filter('')", 2500),
                ("03_app_deviation", "G.explode(false); G.select('G-K-14')", 3000),
                ("04_app_alternative", "G.select('G-K-15')", 3000),
                ("05_app_checker", "G.tab('chk'); G.setForm({host_kind:'rigid_floor',thickness_mm:220,ei_required:'60',service_kind:'pipe',"
                                   "material:'copper',od_mm:28,wall_mm:1,open_system:'0',ins_type:'stone_wool',ins_t:30,ins_p:'Stenuld rørskål',aperture:'220x220'})", 2000)],
          w=1600, h=1000, theme="dark")
    shots(out, [("06_app_phone", "G.select('G-ST-02')", 3000)], w=390, h=844, theme="light", mobile=True)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "gallery":
        gallery()
    if mode == "phone":
        shots(ROOT / "publish", [("06_app_phone", "G.select('G-ST-02')", 3000)], w=390, h=844, theme="light", mobile=True)
    if mode == "check":
        out = Path(sys.argv[2])
        shots(out, [("app_overview", "G.camera([34,24,30],[18,0,-6])", 1500),
                    ("app_dev", "G.select('G-K-14')", 2500),
                    ("app_check", "G.tab('chk'); G.setForm({host_kind:'rigid_floor',thickness_mm:220,service_kind:'pipe',material:'pvc-u',od_mm:110,wall_mm:3.2,open_system:'1'})", 1500)])
