"""End-to-end MCP test: spawn the server over stdio with the official client and call every tool."""
import json
import sys
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


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
            out["check_ok"] = await call("check_penetration", {"construction": "rigid_floor", "thickness_mm": 200, "ei_required": 60,
                                                              "service": "pipe", "material": "PVC-U", "outer_diameter_mm": 110,
                                                              "wall_thickness_mm": 3.4, "system": "open"})
            out["check_dev"] = await call("check_penetration", {"construction": "rigid_floor", "thickness_mm": 200, "ei_required": 60,
                                                               "service": "pipe", "material": "PVC-U", "outer_diameter_mm": 125,
                                                               "wall_thickness_mm": 3.9, "system": "open"})
            out["search"] = await call("search_eta", {"text_query": "copper kaiflex", "construction": "rigid_floor"})
            out["export"] = await call("export_documents")
    return out


def test_mcp_end_to_end():
    o = anyio.run(_calls)
    assert o["server"] == "gennemfoert"
    assert {"check_penetration", "search_eta", "project_overview", "list_penetrations", "get_penetration", "export_documents"} <= set(o["tools"])
    assert o["overview"]["penetrations"] == 58
    assert o["one"]["status"] == "AFVIGELSE" and o["one"]["nearest_tested"][0]["page"] > 0
    assert o["check_ok"]["status"] == "TESTET" and o["check_ok"]["tested_solutions"][0]["section"] == "A.4.5"
    assert o["check_dev"]["status"] == "AFVIGELSE" and "diameter" in o["check_dev"]["nearest_tested"][0]["deviates"]
    assert o["search"] and all(r["section"].startswith("A.4") for r in o["search"])
    assert o["export"]["bcf_topics"] == 22
    (ROOT / "results" / "mcp_session.json").write_text(json.dumps(o, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
