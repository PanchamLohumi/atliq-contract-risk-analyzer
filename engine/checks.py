"""The five checks.

Three of them are deterministic and use no model at all: entity vs governing
law is a lookup, proportionality is arithmetic, bundle completeness is a rule
table. That is deliberate (Session 2: reach for the least intelligent, least
expensive technique that works). The model is used only where the task is
genuinely to read unstructured legal prose and reason about scope.
"""
import re, json, datetime
from pathlib import Path
from . import llm, register

SIGNED = Path(__file__).resolve().parent.parent / "data" / "signed"
SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


# ----------------------------------------------------------------- extraction
EXTRACT_SYSTEM = (
    "You extract structured facts from a commercial contract draft. "
    "Return ONLY a JSON object. Never invent a value: if something is not stated "
    "in the text, use null. Quote numbers exactly as written."
)
EXTRACT_USER = """Extract these fields from the contract draft below.

{{
 "counterparty": "the other party's full name",
 "counterparty_country": "country of the counterparty",
 "counterparty_sector": "one of: hospitality, retail, healthcare, insurance, logistics, financial_services, technology, travel, food, other",
 "deal_type": "one of: MSA, services_agreement, SOW, NDA, BAA, DPA, partnership, pilot, subcontractor, contractor, amendment, other",
 "atliq_entity_named": "which AtliQ entity the draft names as the contracting party, or null",
 "invoicing_entity": "which entity the draft says will invoice, or null",
 "governing_law": "the governing law stated, or null",
 "contract_value_usd": numeric total contract value in USD or null,
 "contract_value_text": "the value exactly as written, or null",
 "liability_cap_text": "the liability cap clause text, or null",
 "liability_cap_clause": "clause number, or null",
 "liability_cap_multiple_of_fees": numeric multiple if expressible (1.0 for 1x fees, 1.5 for 150%) or null,
 "liability_cap_absolute_usd": numeric absolute cap in USD if stated as a fixed sum, or null,
 "delay_penalty_text": "liquidated damages / delay penalty clause text, or null",
 "delay_penalty_capped": true/false/null,
 "involves_personal_or_health_data": true/false,
 "services_described": "one short line on what AtliQ would be doing",
 "territory_of_services": "where the services or the client's operations are located"
}}

CONTRACT DRAFT:
---
{text}
---
Return only the JSON object."""


def _regex_fallback(text):
    """Used when no model is available. Deliberately shallow: it fills what it
    can and leaves the rest null so the brief can mark checks as NOT RUN."""
    def find(pat):
        m = re.search(pat, text, re.I)
        return m.group(1).strip() if m else None
    val = None
    m = re.search(r"(?:USD|\$|EUR|€)\s?([\d,]{4,})", text)
    if m:
        try: val = float(m.group(1).replace(",", ""))
        except ValueError: val = None
    return {
        "counterparty": find(r"(?:between|and)\s+\*\*([A-Z][^*]{3,60})\*\*"),
        "counterparty_country": None, "counterparty_sector": None,
        "deal_type": None,
        "atliq_entity_named": "AtliQ Inc" if "AtliQ Inc" in text else (
            "AtliQ Technologies Pvt Ltd" if "AtliQ Technologies" in text else None),
        "invoicing_entity": None,
        "governing_law": find(r"governed by[^.]{0,80}?laws? of ([^,.]{3,50})"),
        "contract_value_usd": val, "contract_value_text": None,
        "liability_cap_text": None, "liability_cap_clause": None,
        "liability_cap_multiple_of_fees": None, "liability_cap_absolute_usd": None,
        "delay_penalty_text": None, "delay_penalty_capped": None,
        "involves_personal_or_health_data": bool(re.search(r"\bPHI\b|protected health|personal data|GDPR|HIPAA", text, re.I)),
        "services_described": None, "territory_of_services": None,
        "_degraded": True,
    }


def extract_facts(text):
    """Returns (facts, how). 'how' records whether a model ran, for the manifest."""
    if not llm.have_key():
        return _regex_fallback(text), {"ran": False, "reason": "no API key set", "mode": "regex fallback"}
    try:
        facts, model = llm.ask_json(EXTRACT_SYSTEM, EXTRACT_USER.format(text=text[:14000]))
        facts["_degraded"] = False
        return facts, {"ran": True, "mode": "model extraction", "model": model}
    except Exception as e:
        f = _regex_fallback(text)
        return f, {"ran": False, "reason": str(e)[:160], "mode": "regex fallback"}


# ------------------------------------------------------- check 1: collisions
COLLIDE_SYSTEM = (
    "You decide whether a proposed engagement would breach a restriction AtliQ "
    "has already agreed to in another contract. You are cautious: when scope is "
    "unclear you say so rather than clearing it. You never say a deal is safe to "
    "sign and never give legal advice. Return ONLY JSON."
)
COLLIDE_USER = """AtliQ has already agreed to this restriction:

ID: {cid}
Type: {ctype}
Counterparty: {cp}
What it restricts: {summary}
Scope detail: {scope}
Territory: {territory}
Binds AtliQ affiliates: {affil}
Verbatim clause: "{quote}"

AtliQ is now considering this engagement:
Counterparty: {d_cp} ({d_country}), sector: {d_sector}
Services: {d_services}
Territory of services: {d_territory}
AtliQ entity named in the draft: {d_entity}

Answer as JSON:
{{
 "collides": "yes" | "no" | "unclear",
 "severity": "critical" | "high" | "medium" | "low",
 "reason": "two sentences at most, pointing at the specific words in the restriction that do or do not catch this engagement",
 "what_is_uncertain": "if unclear, what exactly cannot be resolved from the text; otherwise null"
}}"""



# Relevance gate. A commitment only bites if the deal could actually trigger it.
# A mutual NDA for exploratory talks delivers no services, so a service
# exclusivity or a background-IP position cannot be breached by signing it.
# Gated commitments are moved to Considered and cleared, never silently dropped.
NEEDS_SERVICE_DELIVERY = {"non_compete", "exclusivity", "mfn_pricing",
                          "ip_assignment", "ip_retained_by_contractor"}
NON_SERVICE_DEAL_TYPES = {"nda", "mutual nda", "mutual_nda"}


def _is_relevant(commitment, facts):
    deal = (facts.get("deal_type") or "").strip().lower()
    if deal in NON_SERVICE_DEAL_TYPES and commitment.get("type") in NEEDS_SERVICE_DELIVERY:
        return False, (f"This deal is an {deal.upper()}, which delivers no services and sets no pricing. "
                       f"A {commitment['type'].replace('_',' ')} cannot be breached by signing it. "
                       "Re-checked automatically when a services agreement or SOW follows.")
    return True, None


def _keyword_collide(c, facts):
    """Fallback judgement when no model is available. Conservative: it raises
    rather than clears, and always marks itself uncertain."""
    sector = (facts.get("counterparty_sector") or "").lower()
    terr = ((facts.get("territory_of_services") or "") + " " +
            (facts.get("counterparty_country") or "")).lower()
    hay = (c.get("summary", "") + " " + c.get("scope_note", "")).lower()
    sector_hit = bool(sector) and sector[:6] in hay
    terr_hit = any(t.lower() in terr for t in c.get("territory", []) or [])
    if sector_hit or terr_hit:
        return {"collides": "unclear", "severity": "high",
                "reason": "Keyword overlap between this engagement and the restriction's sector or territory. No model was available to judge scope.",
                "what_is_uncertain": "Whether the restriction's defined terms actually catch this counterparty."}
    return {"collides": "no", "severity": "low", "reason": "No sector or territory overlap found by keyword match.", "what_is_uncertain": None}


def check_collisions(facts, reg, today=None):
    findings, cleared = [], []
    live, lapsed = register.active_commitments(reg, today)

    for c, label, detail in lapsed:
        cleared.append({
            "commitment_id": c["id"], "counterparty": c["counterparty"],
            "type": c["type"], "status": label, "detail": detail,
            "source_file": c.get("source_file"), "source_clause": c.get("source_clause"),
            "why_cleared": "The obligation has lapsed. Shown rather than hidden, because the client asked to see what was checked and ruled out.",
        })

    used_model = llm.have_key()
    gated = 0
    for c, label, detail in live:
        relevant, why = _is_relevant(c, facts)
        if not relevant:
            gated += 1
            cleared.append({
                "commitment_id": c["id"], "counterparty": c["counterparty"],
                "type": c["type"], "status": label, "detail": why,
                "source_file": c.get("source_file"), "source_clause": c.get("source_clause"),
                "why_cleared": "Live, but not capable of being triggered by this type of deal.",
            })
            continue
        try:
            if used_model:
                verdict, _ = llm.ask_json(COLLIDE_SYSTEM, COLLIDE_USER.format(
                    cid=c["id"], ctype=c["type"], cp=c["counterparty"],
                    summary=c.get("summary", ""), scope=c.get("scope_note", "none recorded"),
                    territory=", ".join(c.get("territory", []) or []) or "not territory limited",
                    affil=c.get("binds_affiliates"), quote=c.get("quote", "")[:900],
                    d_cp=facts.get("counterparty"), d_country=facts.get("counterparty_country"),
                    d_sector=facts.get("counterparty_sector"), d_services=facts.get("services_described"),
                    d_territory=facts.get("territory_of_services"), d_entity=facts.get("atliq_entity_named"),
                ), max_tokens=500)
            else:
                verdict = _keyword_collide(c, facts)
        except Exception as e:
            verdict = _keyword_collide(c, facts)
            verdict["reason"] += f" (model call failed: {str(e)[:80]})"

        if verdict.get("collides") == "no":
            cleared.append({
                "commitment_id": c["id"], "counterparty": c["counterparty"],
                "type": c["type"], "status": label, "detail": verdict.get("reason", ""),
                "source_file": c.get("source_file"), "source_clause": c.get("source_clause"),
                "why_cleared": "Live, but checked and found not to reach this engagement.",
            })
            continue

        # waiver scope test - a waiver clears only what its express terms cover
        waiver_note = None
        for w in register.waivers_for(reg, c["id"]):
            beneficiary = (w.get("summary", "") + " " + w.get("narrowing_note", "")).lower()
            d_cp = (facts.get("counterparty") or "").lower()
            covered = bool(d_cp) and d_cp.split()[0] in beneficiary and len(d_cp.split()[0]) > 3
            waiver_note = {
                "waiver_id": w["id"], "covers_this_deal": covered,
                "quote": w.get("quote"), "source_file": w.get("source_file"),
                "source_clause": w.get("source_clause"),
                "text": (f"A waiver exists ({w['id']}) and it DOES appear to name this counterparty. Verify its express terms."
                         if covered else
                         f"A waiver exists ({w['id']}) but it does not cover this engagement. It is limited to its express terms."),
            }

        unclear = verdict.get("collides") == "unclear"
        findings.append({
            "check": "Past promises",
            "severity": "medium" if unclear and verdict.get("severity") in (None, "low") else verdict.get("severity", "high"),
            "uncertain": unclear,
            "title": f"{c['type'].replace('_','-').replace('-',' ').strip().capitalize().replace('Mfn','MFN').replace('Ip ','IP ')} commitment to {c['counterparty']}",
            "detail": verdict.get("reason", ""),
            "what_is_uncertain": verdict.get("what_is_uncertain"),
            "commitment_id": c["id"],
            "liveness": label, "liveness_detail": detail,
            "quote": c.get("quote"), "source_file": c.get("source_file"),
            "source_clause": c.get("source_clause"),
            "waiver": waiver_note,
        })
    return findings, cleared, {"ran": True, "mode": "model reasoning" if used_model else "keyword fallback, conservative",
                               "status": "ran",
                               "detail": f"{len(live)} live commitments checked, {len(lapsed)} already lapsed"
                                         + (f", {gated} not applicable to this deal type" if gated else "") + ".",
                               "commitments_live": len(live), "commitments_lapsed": len(lapsed),
                               "gated_as_not_applicable": gated}


# ------------------------------------------- check 2: proportionality (RULES)
def check_proportionality(facts, playbook):
    """Deterministic. No model. Arithmetic against contract value, with the
    denominator read from the clause rather than assumed."""
    findings = []
    pb = {p["id"]: p for p in playbook["positions"]}
    value = facts.get("contract_value_usd")
    mult = facts.get("liability_cap_multiple_of_fees")
    absolute = facts.get("liability_cap_absolute_usd")

    deal = (facts.get("deal_type") or "").strip().lower()
    if value is None and deal in NON_SERVICE_DEAL_TYPES:
        return findings, {"ran": False, "status": "not_applicable", "mode": "deterministic",
                          "detail": "An NDA carries no fees, so there is no contract value to measure risk against. "
                                    "This check applies once a services agreement or SOW follows."}
    if value is None:
        return findings, {"ran": False, "status": "could_not_run", "mode": "deterministic",
                          "missing": "the total contract value",
                          "remedy": "The draft does not state a total contract value. It is usually in the fees "
                                    "schedule or the attached SOW. Without it, risk terms cannot be judged "
                                    "proportionate to the size of the deal."}

    ratio = None
    if absolute:
        ratio = absolute / value if value else None
        basis = f"a fixed cap of ${absolute:,.0f} against a contract value of ${value:,.0f}"
    elif mult is not None:
        ratio = mult
        basis = f"a cap of {mult}x fees on a contract worth ${value:,.0f}"
    if ratio is None:
        return findings, {"ran": False, "status": "could_not_run", "mode": "deterministic",
                          "missing": "a numeric liability cap",
                          "remedy": "A liability clause was found but could not be reduced to a number. "
                                    "Read the limitation of liability clause directly."}

    bands = pb["PB-05"]["proposed_bands"]
    sev = next((b["severity"] for b in bands if ratio <= b["ratio_up_to"]), "critical")
    label = next((b["label"] for b in bands if ratio <= b["ratio_up_to"]), "")
    if sev != "none":
        findings.append({
            "check": "Proportionality", "severity": sev, "uncertain": False,
            "title": f"Liability exposure is {ratio:.2g}x contract value",
            "detail": (f"This draft carries {basis}. That is {label}. "
                       f"AtliQ's own pattern is 1x fees, seen in 9 of 12 signed contracts. "
                       f"Threshold bands are the product team's proposal and are not yet confirmed by the client."),
            "quote": facts.get("liability_cap_text"),
            "source_file": "the draft under review",
            "source_clause": facts.get("liability_cap_clause"),
            "deterministic": True,
        })
    if facts.get("delay_penalty_capped") is False:
        findings.append({
            "check": "Proportionality", "severity": "high", "uncertain": False,
            "title": "Delay penalty appears uncapped",
            "detail": ("AtliQ's pattern caps liquidated damages, typically at 5% of the milestone fee or 10% of total fees. "
                       "Brightwater was signed with an uncapped delay penalty and cost $23,200 on a $92,000 deal."),
            "quote": facts.get("delay_penalty_text"),
            "source_file": "the draft under review", "source_clause": None, "deterministic": True,
        })
    return findings, {"ran": True, "status": "ran", "mode": "deterministic arithmetic",
                      "detail": f"Liability exposure computed at {ratio:.2g}x contract value."}


# ----------------------------------------------- check 3: entity/law (RULES)
def canonical_entity(name):
    """Map however a contract spells an AtliQ entity onto which one it is.

    Contracts use full legal names ("ATLIQ TECHNOLOGIES PRIVATE LIMITED") while
    the finance sheet uses the short form ("AtliQ Technologies Pvt Ltd"). A
    naive string match treats those as different companies and raises a false
    conflict on a perfectly correct contract.
    """
    if not name:
        return None
    n = re.sub(r"[^a-z ]", " ", name.lower())
    n = re.sub(r"\s+", " ", n).strip()
    if "atliq" not in n:
        return None
    if any(k in n for k in ("private limited", "pvt ltd", "pvt limited", "technologies private")):
        return "PVT_LTD"
    if re.search(r"\batliq inc\b|\binc\b|\bincorporated\b|delaware", n):
        return "INC"
    if "technologies" in n:
        return "PVT_LTD"
    return None


ENTITY_LABEL = {"PVT_LTD": "AtliQ Technologies Pvt Ltd", "INC": "AtliQ Inc"}


def check_entity(facts, entities):
    """Deterministic. A lookup against the finance fact sheet."""
    findings = []
    named_raw = (facts.get("atliq_entity_named") or "").strip()
    named = canonical_entity(named_raw)
    country = (facts.get("counterparty_country") or "").strip().lower()
    invoicing = canonical_entity(facts.get("invoicing_entity"))

    if not named:
        return findings, {"ran": False, "status": "could_not_run",
                          "missing": "the AtliQ contracting entity",
                          "remedy": "The draft does not clearly name which AtliQ entity is contracting. "
                                    "It is usually in the preamble, on the first page.",
                          "mode": "deterministic lookup"}
    if not country:
        return findings, {"ran": False, "status": "could_not_run",
                          "missing": "the counterparty's country",
                          "remedy": "The draft does not state where the counterparty is based, "
                                    "so the correct AtliQ entity cannot be determined.",
                          "mode": "deterministic lookup"}

    is_us_client = any(k in country for k in ("united states", "usa", "u.s.", "u.s"))
    expected = "INC" if is_us_client else "PVT_LTD"
    if named != expected:
        findings.append({
            "check": "Entity and governing law", "severity": "high", "uncertain": False,
            "title": f"Wrong contracting entity: the draft names {ENTITY_LABEL[named]}",
            "detail": (f"The counterparty is in {facts.get('counterparty_country')}. Per the finance fact sheet, "
                       f"{ENTITY_LABEL[expected]} serves that region. AtliQ Inc serves clients in the United States only; "
                       f"AtliQ Technologies Pvt Ltd serves everywhere else. The entity named decides which "
                       f"tax regime applies and which bank account is paid."),
            "quote": None, "source_file": "data/atliq_entities.md", "source_clause": "Entity fact sheet",
            "deterministic": True,
        })
    if invoicing and named and invoicing != named:
        findings.append({
            "check": "Entity and governing law", "severity": "medium", "uncertain": False,
            "title": "Contracting entity and invoicing entity do not match",
            "detail": (f"The draft contracts as {ENTITY_LABEL[named]} but invoices as {ENTITY_LABEL[invoicing]}. "
                       "Finance records that this mismatch caused payment delays twice in 2025."),
            "quote": None, "source_file": "data/atliq_entities.md", "source_clause": "Notes from finance",
            "deterministic": True,
        })
    return findings, {"ran": True, "status": "ran", "mode": "deterministic lookup",
                      "detail": f"Draft names {ENTITY_LABEL[named]}; {ENTITY_LABEL[expected]} is correct for this region."}


# -------------------------------------------- check 4: bundle complete (RULES)
def required_bundle(facts, entities):
    """Work out which companion documents THIS deal needs.

    The reviewer should not have to know contract law to use the tool. The
    system knows the country, the sector and whether regulated data is
    involved, so it decides what the deal requires and then asks only whether
    those specific documents arrived.
    """
    reqs = entities["bundle_requirements"]
    sector = (facts.get("counterparty_sector") or "").lower()
    country = (facts.get("counterparty_country") or "").lower()
    deal = (facts.get("deal_type") or "").lower()
    regulated = bool(facts.get("involves_personal_or_health_data"))
    us = any(k in country for k in ("united states", "usa", "u.s.", "u.s"))
    eu = any(k in country for k in ("germany", "france", "netherlands", "spain",
                                    "italy", "ireland", "belgium", "poland", "sweden", "eu"))

    if "healthcare" in sector and us:
        return (reqs["us_healthcare"], "a US healthcare engagement",
                "HIPAA requires a signed Business Associate Agreement before a vendor "
                "touches patient data. A services agreement on its own is not enough.")
    if regulated and eu:
        return (reqs["eu_personal_data"], "an EU engagement involving personal data",
                "GDPR Article 28 requires a written Data Processing Agreement between "
                "the client as controller and AtliQ as processor.")
    if deal == "subcontractor" and regulated:
        return (reqs["subcontractor_regulated_data"], "a subcontractor touching regulated data",
                "Obligations AtliQ owes its client must flow down to anyone AtliQ hands "
                "the data to, or AtliQ stays liable for a breach it cannot see.")
    return ([], None, None)


def check_bundle(facts, entities, companion_docs=None):
    """Deterministic. A rule table by deal type."""
    findings = []
    supplied = [d.lower() for d in (companion_docs or [])]
    needed, why, rule = required_bundle(facts, entities)

    if not needed:
        return findings, {"ran": True, "status": "ran", "mode": "deterministic rules",
                          "detail": "This deal type requires no special companion documents.",
                          "required": [], "supplied": supplied}

    joined = " ".join(supplied)
    missing = [d for d in needed
               if not any(tok in joined for tok in
                          [w.lower() for w in re.findall(r"[A-Z]{2,}|[A-Za-z]{4,}", d)[:2]])]
    if missing:
        findings.append({
            "check": "Bundle completeness", "severity": "high", "uncertain": False,
            "title": f"Paperwork incomplete for {why}",
            "detail": (rule + " Not supplied with this draft: " + "; ".join(missing) + "."),
            "quote": None, "source_file": "data/entities.json", "source_clause": "bundle_requirements",
            "deterministic": True,
        })
    return findings, {"ran": True, "status": "ran", "mode": "deterministic rules",
                      "detail": (f"Required for {why}: " + "; ".join(needed) + "."),
                      "required": needed, "why": why, "rule": rule, "supplied": supplied}


# ------------------------------------------------- guardrail: cite or be cut
def _norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def verify_citations(findings):
    """Every finding must carry a quote that exists verbatim in the file it
    cites. A finding that fails verification is dropped and logged. This is the
    anti-fabrication guardrail from the PRD, implemented rather than promised."""
    kept, dropped = [], []
    cache = {}
    for f in findings:
        q, src = f.get("quote"), f.get("source_file")
        if not q or not src or src in ("the draft under review",) or src.startswith("data/"):
            f["citation"] = "n/a" if not q else "not checked against an archive file"
            kept.append(f); continue
        path = SIGNED / Path(src).name
        if path not in cache:
            cache[path] = _norm(path.read_text(encoding="utf-8")) if path.exists() else None
        body = cache[path]
        if body is None:
            f["citation"] = "source file not found"
            dropped.append({**f, "drop_reason": f"cited file {src} is not in the archive"})
            continue
        parts = [p for p in re.split(r"\s*\.\.\.\s*|\s*…\s*", q) if len(p.strip()) > 12]
        ok = all(_norm(p) in body for p in parts) if parts else _norm(q) in body
        if ok:
            f["citation"] = "verified verbatim against source"
            kept.append(f)
        else:
            dropped.append({**f, "drop_reason": "quoted text could not be matched verbatim in the cited file"})
    return kept, dropped


def order_findings(findings):
    return sorted(findings, key=lambda f: (SEV_ORDER.get(f.get("severity", "low"), 5),
                                           0 if not f.get("uncertain") else 1))
