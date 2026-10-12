"""Assembles the triage brief.

Shape is fixed by the PRD: a three-line verdict header where the first words
carry the answer, then every finding ordered by consequence and never filtered,
then what was checked and cleared, then the manifest of which checks ran.

Deliberately no severity jargon in the header. "Worst is medium" is a developer
word. Karandeep is a CEO reading this at 11pm; each line says what it means for
the decision in front of him.
"""
import datetime
from . import checks, register

# Per-line vocabulary. Each check answers its own question, so each line gets
# verdicts specific to that question rather than one generic severity ladder.
LINES = [
    {"label": "Past promises", "question": "Does this collide with something we already signed?",
     "checks": ["Past promises"],
     "clear": ("NOTHING FOUND", "No live commitment we have made reaches this deal."),
     "blocked": ("CONFLICT", "This appears to breach a commitment AtliQ has already made."),
     "judgement": ("YOUR CALL", "A commitment may reach this deal. The scope is not clear-cut."),
     "minor": ("WORTH A LOOK", "A commitment touches this deal, but not severely."),
     "unknown": ("COULDN'T CHECK", "")},
    {"label": "Our own paper", "question": "Is this in line with how AtliQ normally contracts?",
     "checks": ["Proportionality"],
     "clear": ("IN LINE", "Risk terms sit within the pattern across AtliQ's signed contracts."),
     "blocked": ("OUT OF PATTERN", "Risk is disproportionate to what this deal is worth."),
     "judgement": ("OUT OF PATTERN", "Terms depart from AtliQ's usual position."),
     "minor": ("SLIGHTLY OFF", "A term sits a little outside AtliQ's usual position."),
     "unknown": ("COULDN'T CHECK", "")},
    {"label": "Deal completeness", "question": "Is the paperwork right and complete?",
     "checks": ["Entity and governing law", "Bundle completeness"],
     "clear": ("COMPLETE", "Correct signing entity, and no companion documents missing."),
     "blocked": ("SOMETHING'S MISSING", "The paperwork is not right yet."),
     "judgement": ("SOMETHING'S MISSING", "The paperwork needs attention."),
     "minor": ("MINOR GAP", "A small paperwork issue worth correcting."),
     "unknown": ("COULDN'T CHECK", "")},
]


def _state(manifest, names):
    """ran / not_applicable / could_not_run, collapsed across a line's checks."""
    sts = [manifest.get(n, {}).get("status", "could_not_run") for n in names if n in manifest]
    if not sts:
        return "could_not_run", None
    if "ran" in sts:
        return "ran", None
    if all(s == "not_applicable" for s in sts):
        why = next((manifest[n].get("detail") for n in names
                    if manifest.get(n, {}).get("status") == "not_applicable"), None)
        return "not_applicable", why
    why = next((manifest[n].get("remedy") for n in names
                if manifest.get(n, {}).get("remedy")), None)
    return "could_not_run", why


def _verdict_line(cfg, group, manifest):
    state, why = _state(manifest, cfg["checks"])
    if state == "not_applicable":
        return cfg["label"], "NOT APPLICABLE", why or "This check does not apply to this type of deal.", "clear"
    if state == "could_not_run":
        return cfg["label"], cfg["unknown"][0], why or "A required input was not present in the draft.", "unknown"
    if not group:
        w, t = cfg["clear"]
        return cfg["label"], w, t, "clear"

    worst = min(group, key=lambda f: checks.SEV_ORDER.get(f.get("severity", "low"), 5))
    sev = worst.get("severity", "low")
    if worst.get("uncertain"):
        w, base = cfg["judgement"]
    elif sev in ("critical", "high"):
        w, base = cfg["blocked"]
    else:
        w, base = cfg["minor"]

    n = len(group)
    more = f" Plus {n - 1} other point{'s' if n > 2 else ''} below." if n > 1 else ""
    return cfg["label"], w, f"{base} {worst.get('title', '')}.{more}", sev


def analyse(facts, reg, playbook, entities, today=None):
    """The expensive half: everything that needs the register or a model.

    Run once per draft. Its result is cached so the reviewer can answer the
    paperwork question afterwards without paying for the analysis again.
    """
    today = today or datetime.date.today()
    manifest = {}
    coll, cleared, m1 = checks.check_collisions(facts, reg, today); manifest["Past promises"] = m1
    prop, m2 = checks.check_proportionality(facts, playbook); manifest["Proportionality"] = m2
    ent, m3 = checks.check_entity(facts, entities); manifest["Entity and governing law"] = m3
    needed, why, rule = checks.required_bundle(facts, entities)
    return {"today": today, "findings": coll + prop + ent, "cleared": cleared,
            "manifest": manifest, "bundle_required": needed,
            "bundle_why": why, "bundle_rule": rule}


def assemble(core, facts, entities, companion_docs=None):
    """The cheap half: the paperwork check, citation verification, ordering.

    Recomputed on every render, so ticking a document updates the brief
    immediately with no model call.
    """
    manifest = dict(core["manifest"])
    bun, m4 = checks.check_bundle(facts, entities, companion_docs)
    manifest["Bundle completeness"] = m4

    kept, dropped = checks.verify_citations(list(core["findings"]) + bun)
    ordered = checks.order_findings(kept)

    header = [_verdict_line(cfg, [f for f in ordered if f["check"] in cfg["checks"]], manifest)
              for cfg in LINES]

    gaps = [{"check": name, "missing": m.get("missing"), "remedy": m.get("remedy")}
            for name, m in manifest.items() if m.get("status") == "could_not_run"]

    return {
        "generated": core["today"].isoformat(),
        "facts": facts, "header": header, "findings": ordered, "cleared": core["cleared"],
        "manifest": manifest, "dropped": dropped, "gaps": gaps,
        "bundle_required": core["bundle_required"],
        "bundle_why": core["bundle_why"], "bundle_rule": core["bundle_rule"],
        "disclaimer": ("This is a review aid, not legal advice. It does not say whether a contract is "
                       "safe to sign. A human with signing authority decides, and only Karandeep signs."),
    }


def build(facts, reg, playbook, entities, companion_docs=None, today=None):
    """One-shot path, used by the evaluation harness."""
    core = analyse(facts, reg, playbook, entities, today)
    return assemble(core, facts, entities, companion_docs)
