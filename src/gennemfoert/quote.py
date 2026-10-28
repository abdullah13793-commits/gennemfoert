"""From tested solutions to a material list with the wholesaler's item numbers (indicative quantities).

Quantities are geometric and transparent: board area from the opening and the number of layers, edge sealant from the
joint length, collar segments from the circumference (one roll = 174 segments over 2610 mm, i.e. 15 mm per segment),
Multiclips from ETA-20/1322 section 1 item 5. Conversion factors are editable. Mulcol does not publish consumption tables
("contact your Mulcol contact for the consumption overview"), so every line says how it was computed. Prices come from
the customer agreement and are not part of this file.
"""
import math

ITEMS = {  # public item numbers from the wholesaler's web shop (product pages, 2026)
    "FB1": {"no": "6476478013", "name": "Mulcol Multimastic FB1 50 mm, 1-sidet brandplade", "unit": "stk", "size_m2": 0.625},
    "FB2": {"no": "6476478014", "name": "Mulcol Multimastic FB2 60 mm, 2-sidet brandplade", "unit": "stk", "size_m2": 0.625},
    "SP": {"no": "6476478010", "name": "Mulcol Multimastic SP akryl 310 ml brandfuge", "unit": "stk", "ml": 310},
    "C6": {"no": "6476477922", "name": "Mulcol Multimastic C coating 6 kg brandmaling", "unit": "stk"},
    "COLLAR": {"no": "6476477918", "name": "Mulcol Multicollar Slim 2600x30 mm brandmanchet (174 segmenter)", "unit": "rl", "segments": 174},
    "DISC": {"no": "6476477924", "name": "Mulcol Multidisc brand-kabeldisk Ø65", "unit": "stk"},
    "FOAM": {"no": "6476477929", "name": "Mulcol Multifoam 2K 380 ml brandskum", "unit": "stk"},
}
FACTORS = {"board_waste": 1.15, "joint_mm2": 100.0, "segment_mm": 2610 / 174, "inlay_mm": 12.0, "coat_kg_m2": 1.5}


def segments_for(outer_d_mm, f=FACTORS):
    return math.ceil(math.pi * (outer_d_mm + 2 * f["inlay_mm"]) / f["segment_mm"])


def lines_for(item, best, faces, f=FACTORS):
    """Quantities for one penetration solved by `best` (an engine brief). Returns raw quantities (not yet rounded to packs)."""
    q = {}
    ap = item.get("aperture_mm") or [200, 200]
    if best.get("board"):
        typ = best["board"].split(" ")[0]
        layers = int(best["board"].split(" ")[1].split("x")[0])
        area = ap[0] * ap[1] / 1e6 * layers
        q[typ] = q.get(typ, 0) + area * f["board_waste"]
        joint_m = 2 * (ap[0] + ap[1]) / 1000 * 2                    # perimeter, both faces
        q["SP_ml"] = q.get("SP_ml", 0) + joint_m * f["joint_mm2"]        # m x mm² = ml
        q["C_m2"] = q.get("C_m2", 0) + ap[0] * ap[1] / 1e6 * (2 if typ == "FB2" or layers > 1 else 1)
    if best.get("system") == "Multicollar Slim":
        n = (best.get("collars_per_face") or 1) * faces
        q["COLLAR_seg"] = q.get("COLLAR_seg", 0) + n * segments_for(item["outer_d"], f)
        q["clips"] = q.get("clips", 0) + n * item.get("clips", 2)
        gap = (min(ap) - item["outer_d"]) / 2
        if gap <= 20:
            q["SP_ml"] = q.get("SP_ml", 0) + math.pi * (item["outer_d"] + gap) * gap * 10 / 1000 * faces   # depth 10 mm
        else:
            q["mortar_l"] = q.get("mortar_l", 0) + (ap[0] * ap[1] - math.pi * item["outer_d"] ** 2 / 4) * item["thickness_mm"] / 1e6
    return q


def material_list(solved, f=FACTORS):
    """solved: [{'outer_d', 'thickness_mm', 'aperture_mm', 'faces', 'clips', 'best'}] -> list of quote lines."""
    tot = {}
    for it in solved:
        for k, v in lines_for(it, it["best"], it["faces"], f).items():
            tot[k] = tot.get(k, 0) + v
    out = []
    for typ in ("FB1", "FB2"):
        if tot.get(typ):
            n = math.ceil(tot[typ] / ITEMS[typ]["size_m2"])
            out.append({**ITEMS[typ], "qty": n, "basis": f"{tot[typ]:.2f} m² plade inkl. {round((f['board_waste'] - 1) * 100)} % spild, plader á {ITEMS[typ]['size_m2']} m²"})
    if tot.get("COLLAR_seg"):
        rolls = math.ceil(tot["COLLAR_seg"] / ITEMS["COLLAR"]["segments"])
        out.append({**ITEMS["COLLAR"], "qty": rolls, "basis": f"{tot['COLLAR_seg']:.0f} segmenter á {f['segment_mm']:.1f} mm "
                    f"(omkreds af rør inkl. isolering + 2x{f['inlay_mm']:.0f} mm indlæg), {tot['clips']:.0f} Multiclips (følger med)"})
    if tot.get("SP_ml"):
        n = math.ceil(tot["SP_ml"] / ITEMS["SP"]["ml"])
        out.append({**ITEMS["SP"], "qty": n, "basis": f"{tot['SP_ml']:.0f} ml fuge (kant/ringspalte, {f['joint_mm2']:.0f} mm² tværsnit)"})
    if tot.get("C_m2"):
        out.append({**ITEMS["C6"], "qty": max(1, math.ceil(tot["C_m2"] * f["coat_kg_m2"] / 6)), "basis": f"{tot['C_m2']:.2f} m² pladeflade med ≤ 1 mm coating "
                    f"(mængde efter producentens anvisning; overslag {f['coat_kg_m2']:g} kg/m²)"})
    if tot.get("mortar_l"):
        out.append({"no": "-", "name": "Mulcol Multimortar (brandmørtel)", "unit": "l", "qty": round(tot["mortar_l"], 1),
                    "basis": "ringspalte i dæk udfyldes helt (ETA-20/1322 afsnit 1, pkt. 4); mængden følger modellens hul, et kernebor tæt på manchetten sparer mørtel; varenummer efter sortiment"})
    return out


def project_quote(pens, f=FACTORS):
    """Material list for every penetration of a register that has a tested solution (the first, cheapest match)."""
    from . import engine
    solved = []
    for p in pens:
        v = p["verdict"]
        if v["status"] != "TESTET":
            continue
        best = v["matches"][0]
        q = engine.query_from_penetration(p)
        od = engine.outer_diameter(q)
        solved.append({"id": p["id"], "outer_d": od, "thickness_mm": p["host"]["thickness_mm"], "aperture_mm": p.get("aperture_mm") or [200, 200],
                       "faces": 1 if p["host"]["kind"] == "rigid_floor" else 2, "clips": engine.collar_clips(od), "best": best})
    per = {}
    for s in solved:
        per[s["best"]["system"]] = per.get(s["best"]["system"], 0) + 1
    return {"lines": material_list(solved, f), "seals": len(solved), "per_system": per, "factors": f,
            "not_quoted": [p["id"] for p in pens if p["verdict"]["status"] != "TESTET"]}
