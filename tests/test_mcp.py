"""End-to-end MCP test: spawn the server over stdio with the official client and call every tool."""
import json
import sys
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
PIPE = {"construction": "rigid_floor", "thickness_mm": 200, "ei_required": 60, "service": "pipe", "material": "PVC-U", "system": "open"}


async def _calls():
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "src" / "mcp_server.py")])
    out = {}
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            out["server"] = init.server_info.name
            out["tools"] = sorted(t.name for t in (await s.list_tools()).tools)

            async def call(name, args=None):
                res = await s.call_tool(name, args or {})
                assert not res.is_error, (name, res)
                sc = res.structured_content
                if sc is not None:
                    return sc["result"] if set(sc) == {"result"} else sc
                return json.loads(res.content[0].text)
            out["overview"] = await call("project_overview")
            out["dev"] = await call("list_penetrations", {"status": "AFVIGELSE"})
            out["one"] = await call("get_penetration", {"penetration_id": out["dev"][0]["id"]})
            out["check_board"] = await call("check_penetration", {**PIPE, "outer_diameter_mm": 110, "wall_thickness_mm": 3.4})
            out["check_collar"] = await call("check_penetration", {**PIPE, "outer_diameter_mm": 110, "wall_thickness_mm": 3.2})
            out["check_dev"] = await call("check_penetration", {**PIPE, "material": "PP", "outer_diameter_mm": 75, "wall_thickness_mm": 2.6,
                                                               "thickness_mm": 150})
            out["prec"] = await call("find_precedents", {**PIPE, "construction": "flexible_wall", "thickness_mm": 100, "material": "PP",
                                                         "outer_diameter_mm": 50, "wall_thickness_mm": 1.2})
            out["intake"] = await call("precheck_enquiry", {"address": "Havnegade 2, 8000 Aarhus C", "timeline": "Snarest muligt", "items": [
                {"construction": {"kind": "rigid_floor", "thickness_mm": 200, "ei_required": 60},
                 "service": {"kind": "pipe", "material": "PVC-U", "od_mm": 110, "wall_mm": 3.2, "system": "open", "insulation": "none"},
                 "aperture_mm": [150, 150], "photos": {"hul": True, "installation": True, "konstruktion": True, "oversigt": True}},
                {"construction": {"kind": "rigid_wall"}, "service": {"kind": "pipe", "material": "Kobber"}}]})
            out["search"] = await call("search_eta", {"text_query": "elbow", "system": "Multicollar Slim"})
            out["kb"] = await call("knowledge_base")
            out["cases"] = await call("list_cases", {"status": "UDSENDT"})
            out["case"] = await call("get_case", {"case_id": out["cases"][0]["id"]})
            codes = json.loads((ROOT / "results" / "verify.json").read_text(encoding="utf-8"))
            out["verify_ok"] = await call("verify_assessment", {"code": next(iter(codes)).lower()})
            out["verify_bad"] = await call("verify_assessment", {"code": "0000000000000000"})
            out["quote"] = await call("quote_project")
            out["rev"] = await call("revision_impact")
            out["export"] = await call("export_documents")
    return out


def test_mcp_end_to_end():
    o = anyio.run(_calls)
    assert o["server"] == "gennemfoert"
    assert {"check_penetration", "find_precedents", "precheck_enquiry", "search_eta", "knowledge_base", "list_cases", "get_case",
            "verify_assessment", "quote_project", "revision_impact", "project_overview", "list_penetrations", "get_penetration",
            "export_documents"} <= set(o["tools"])
    assert o["overview"]["penetrations"] == 58 and o["overview"]["solution_systems"]["Multicollar Slim"] > 0
    assert o["one"]["status"] == "AFVIGELSE" and o["one"]["nearest_tested"][0]["page"] > 0
    assert o["check_board"]["status"] == "TESTET" and {m["system"] for m in o["check_board"]["tested_solutions"]} & {"Multimastic C", "Multicollar Slim"}
    assert o["check_collar"]["status"] == "TESTET" and o["check_collar"]["tested_solutions"][0]["system"] == "Multicollar Slim"
    assert o["check_dev"]["status"] == "AFVIGELSE" and o["check_dev"]["nearest_tested"][0]["deviates"] == ["godstykkelse"]
    assert o["prec"]["signature"] and o["prec"]["signature"][0]["param"] == "godstykkelse"
    assert o["intake"]["region"] == "VEST" and o["intake"]["items"][0]["triage"] == "BESVARET_TESTET" and o["intake"]["items"][1]["triage"] == "MANGLER_INFO"
    assert o["search"] and all(r["configuration"] == "elbow" for r in o["search"])
    assert {s["eta"] for s in o["kb"]["systems"]} == {"ETA-21/0110", "ETA-20/1322"}
    assert o["case"]["audit_chain_valid"] and o["case"]["four_eyes"]
    assert o["verify_ok"]["genuine"] and not o["verify_bad"]["genuine"]
    assert any(ln["no"] == "6476477918" for ln in o["quote"]["lines"])
    assert len(o["rev"]["changed"]) == 5
    assert o["export"]["bcf_topics"] >= 19
    (ROOT / "results" / "mcp_session.json").write_text(json.dumps(o, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
