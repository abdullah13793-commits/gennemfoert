"""Case workflow for brandtekniske vurderinger, with an audit trail that cannot be edited quietly.

States follow the published process (send enquiry, we review the material and ask if something is missing, we write the
assessment, you receive it) and add the steps a quality system expects: a second adviser checks every assessment before
it is issued (four eyes), and every event is chained by SHA-256 to the one before, so a changed or deleted entry is
detected. Each event records which knowledge-base version was used.
"""
import datetime
import hashlib
import json

STATES = ["MODTAGET", "MANGLER_INFO", "TIL_VURDERING", "UDKAST", "TIL_KONTROL", "UDSENDT", "BESVARET", "ARKIVERET", "AFVIST"]
TRANSITIONS = {
    "MODTAGET": {"MANGLER_INFO", "TIL_VURDERING", "BESVARET", "AFVIST"},
    "MANGLER_INFO": {"TIL_VURDERING", "AFVIST"},
    "TIL_VURDERING": {"UDKAST", "MANGLER_INFO", "AFVIST"},
    "UDKAST": {"TIL_KONTROL", "TIL_VURDERING"},
    "TIL_KONTROL": {"UDSENDT", "UDKAST"},
    "UDSENDT": {"ARKIVERET", "TIL_VURDERING"},
    "BESVARET": {"ARKIVERET", "TIL_VURDERING"},
    "AFVIST": {"ARKIVERET"},
    "ARKIVERET": set(),
}
LABEL = {"MODTAGET": "Modtaget", "MANGLER_INFO": "Mangler oplysninger", "TIL_VURDERING": "Til vurdering", "UDKAST": "Udkast",
         "TIL_KONTROL": "Til kontrol (4 øjne)", "UDSENDT": "Udsendt", "BESVARET": "Besvaret (testet løsning)", "ARKIVERET": "Arkiveret",
         "AFVIST": "Afvist (intet grundlag)"}


class WorkflowError(Exception):
    pass


def _hash(prev, event):
    body = json.dumps({k: v for k, v in event.items() if k != "hash"}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256((prev + body).encode("utf-8")).hexdigest()


def log(case, actor, action, detail=None, kb_version=None, at=None):
    prev = case["events"][-1]["hash"] if case["events"] else "0" * 64
    ev = {"at": (at or datetime.datetime.now().replace(microsecond=0)).isoformat(), "actor": actor, "action": action,
          "detail": detail or {}, "kb": kb_version, "state": case["status"]}
    ev["hash"] = _hash(prev, ev)
    case["events"].append(ev)
    return ev


def verify(case):
    """True if no event was changed, inserted or removed (except at the end)."""
    prev = "0" * 64
    for ev in case["events"]:
        if ev["hash"] != _hash(prev, ev):
            return False
        prev = ev["hash"]
    return True


def move(case, to, actor, detail=None, kb_version=None, at=None):
    frm = case["status"]
    if to not in TRANSITIONS.get(frm, set()):
        raise WorkflowError(f"{frm} -> {to} er ikke tilladt")
    if to == "UDSENDT":
        review = next((e for e in reversed(case["events"]) if e["action"] == "kontrol_godkendt"), None)
        author = next((e for e in reversed(case["events"]) if e["action"] == "udkast_gemt"), None)
        if not review or not author:
            raise WorkflowError("Kan ikke udsendes uden udkast og godkendt kontrol")
        if review["actor"] == author["actor"]:
            raise WorkflowError("Kontrollen skal udføres af en anden rådgiver end forfatteren (4-øjne-princip)")
    case["status"] = to
    log(case, actor, f"status:{frm}->{to}", detail, kb_version, at)
    return case


def decide(case, item_no, actor, decision, conditions, argument, kb_version=None, at=None):
    """Record the adviser's decision for one item: GODKENDT / BETINGET / AFVIST, with conditions and the argument."""
    if decision not in ("GODKENDT", "BETINGET", "AFVIST"):
        raise WorkflowError("ukendt beslutning")
    if decision == "BETINGET" and not conditions:
        raise WorkflowError("en betinget godkendelse kræver betingelser")
    if len((argument or "").strip()) < 40:
        raise WorkflowError("begrundelsen skal være skrevet af rådgiveren (min. 40 tegn)")
    it = next(i for i in case["items"] if i["no"] == item_no)
    it["decision"] = {"decision": decision, "conditions": conditions, "argument": argument, "author": actor,
                      "at": (at or datetime.datetime.now().replace(microsecond=0)).isoformat()}
    log(case, actor, "udkast_gemt", {"item": item_no, "decision": decision}, kb_version, at)
    return it


def review(case, actor, approve, comment, kb_version=None, at=None):
    author = next((e for e in reversed(case["events"]) if e["action"] == "udkast_gemt"), None)
    if author and author["actor"] == actor:
        raise WorkflowError("Forfatteren kan ikke kontrollere sit eget udkast (4-øjne-princip)")
    log(case, actor, "kontrol_godkendt" if approve else "kontrol_afvist", {"comment": comment}, kb_version, at)
    return case
