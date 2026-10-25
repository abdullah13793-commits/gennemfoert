"""Danish labels shared by the register, the BCF issues, the web app and the MCP server."""
STATUS = {
    "TESTET": "Testet løsning",
    "AFVIGELSE": "Afvigelse: brandteknisk vurdering",
    "IKKE_DAEKKET": "Ingen testet løsning i ETA'en",
    "ANDET_SYSTEM": "Andet system (spjæld / kanalisolering)",
    "MANGLER_DATA": "Mangler data",
}
SHORT = {"TESTET": "Testet", "AFVIGELSE": "Afvigelse", "IKKE_DAEKKET": "Ikke dækket", "ANDET_SYSTEM": "Andet system",
         "MANGLER_DATA": "Mangler data"}
ACTION = {
    "TESTET": "Udfør som testet. Følg betingelserne og dokumentér med foto.",
    "AFVIGELSE": "Brandteknisk vurdering af afvigelsen, eller ændr til den testede/alternative løsning.",
    "IKKE_DAEKKET": "Vælg et andet testet system (fx brandmanchet) eller få en brandteknisk vurdering.",
    "ANDET_SYSTEM": "Brandspjæld eller brandisolering af kanalen efter producentens dokumentation.",
    "MANGLER_DATA": "Indhent de manglende oplysninger hos projekterende/installatør.",
}
PRIORITY = {"TESTET": "Minor", "AFVIGELSE": "Major", "IKKE_DAEKKET": "Critical", "ANDET_SYSTEM": "Normal", "MANGLER_DATA": "Major"}
HOST = {"rigid_wall": "Massiv væg", "flexible_wall": "Let væg", "rigid_floor": "Massivt dæk"}
SERVICE = {"pipe": "Rør", "duct": "Ventilationskanal", "cable": "Kabel", "cable_bundle": "Kabelbundt", "cable_tray": "Kabelbakke"}
DISCLAIMER = ("Beslutningsstøtte, ikke godkendelse. Hver løsning kontrolleres mod kildedokumentet (ETA-21/0110) og "
              "producentens monteringsvejledning. En brandteknisk vurdering udarbejdes og underskrives af en person.")


def service_line(s):
    if s["kind"] == "cable_tray":
        return f"{SERVICE['cable_tray']} {s.get('width_mm')}x{s.get('height_mm')} mm"
    ins = s.get("insulation")
    od = s.get("od_mm")
    txt = f"{s.get('material') or '?'} Ø{od:g}".replace(".", ",") if od else f"{s.get('material') or '?'} Ø?"
    if s.get("wall_mm"):
        txt += f"x{s['wall_mm']:g}".replace(".", ",")
    if s["kind"] == "cable_bundle":
        txt = f"Kabelbundt Ø{s.get('bundle_mm')} (kabler ≤ {s.get('od_mm')} mm)"
    elif s["kind"] == "cable":
        txt = f"Kabel Ø{s.get('od_mm')}"
    elif s["kind"] == "duct":
        txt = f"Ventilationskanal Ø{s.get('od_mm')}"
    if ins:
        txt += f", {ins['product']} {ins['thickness_mm']:g} mm"
    return txt


def solution_line(v):
    if v["matches"]:
        m = v["matches"][0]
        return f"{m['eta']} {m['section']} (s. {m['page']}): {m['board']}, {m['classification']}"
    if v["nearest"]:
        n = v["nearest"][0]
        return f"Nærmeste testede: {n['eta']} {n['section']} (s. {n['page']}), afviger på: {', '.join(n['deviates'])}"
    return ""
