"""Companion paperwork: what a deal needs, and whether what arrived is any good.

Two jobs:

1. A fast scan of the draft the moment it is selected, so the reviewer is warned
   that extra paperwork will be needed BEFORE waiting on an analysis. This is
   deliberately a cheap regex pass, not a model call.
2. Judging an attached companion document: is it the right kind of document,
   and has it actually been signed? A Business Associate Agreement sitting
   unsigned in an inbox satisfies nothing. HIPAA requires an executed one.
"""
import re

DOC_PATTERNS = {
    "BAA": (r"business associate agreement|\bBAA\b", "Business Associate Agreement"),
    "DPA": (r"data processing agreement|processing of personal data|art(?:icle)?\.?\s*28", "Data Processing Agreement"),
    "NDA": (r"nondisclosure agreement|non-disclosure agreement|\bNDA\b", "Nondisclosure Agreement"),
    "MSA": (r"master (?:professional )?services agreement|\bMSA\b", "Master Services Agreement"),
    "SOW": (r"statement of work|\bSOW\b", "Statement of Work"),
}


def quick_signals(text):
    """Guess, from the raw text, which companion documents this deal will need.

    Returns (label, documents, reason) or (None, [], None). Intentionally
    conservative: it warns, it does not conclude. The authoritative answer comes
    from required_bundle() once the facts have been extracted.
    """
    t = text[:40000]
    low = t.lower()
    us = bool(re.search(r"\bunited states\b|\bdelaware\b|\btexas\b|\bnew jersey\b|\bU\.S\.", t))
    healthcare = bool(re.search(r"\bhipaa\b|protected health information|\bPHI\b|covered entity|hospital|clinic|patient", low))
    eu = bool(re.search(r"\bgdpr\b|\bgmbh\b|germany|münchen|munich|european union|regulation \(eu\)", low))
    personal = bool(re.search(r"personal data|data subject|controller|processor", low))
    subcontract = bool(re.search(
        r"^#\s*(?:independent\s+)?(?:sub)?contractor[\w\s]*agreement|subcontractor services agreement",
        low, re.M))

    if subcontract and (healthcare or personal):
        return ("a subcontractor or freelancer touching regulated data",
                ["Signed BAA or DPA flow-down with this contractor"],
                "The client's rule: \"If there's a healthcare project, I would want to sign BAA "
                "for my freelancers as well.\" Obligations AtliQ owes its client must flow down "
                "to anyone AtliQ hands the data to.")
    if healthcare and us:
        return ("a US healthcare engagement",
                ["Mutual NDA", "Business Associate Agreement (BAA)", "Master Services Agreement or Services Agreement"],
                "HIPAA requires a signed Business Associate Agreement before a vendor touches "
                "patient data. A services agreement on its own is not enough.")
    if eu and personal:
        return ("an EU engagement involving personal data",
                ["Data Processing Agreement (DPA) or Annex", "Services Agreement"],
                "GDPR Article 28 requires a written Data Processing Agreement between the client "
                "as controller and AtliQ as processor.")
    return (None, [], None)


def _identity(text):
    """The part of a document that says what it IS, not what it mentions.

    A nondisclosure agreement can refer to a BAA in passing; that does not make
    it one. So classification reads the title and the opening "this X is
    entered into" sentence, and nothing else.
    """
    bits = []
    for line in text.split("\n")[:60]:
        line = line.strip()
        if line.startswith("#"):
            bits.append(line.lstrip("# ").strip())
        if re.match(r"\*?\*?this\b", line, re.I) and "entered into" in line.lower():
            bits.append(line[:400])
    return " \n ".join(bits) or text[:500]


def classify(text):
    """Which kind of document does this file look like? Returns a set of codes."""
    ident = _identity(text).lower()
    found = set()
    for code, (pat, _) in DOC_PATTERNS.items():
        if re.search(pat, ident, re.I):
            found.add(code)
    return found


def expected_code(label):
    """Map a required-document label onto the code classify() returns."""
    l = label.lower()
    if "business associate" in l or "baa" in l:
        return "BAA"
    if "data processing" in l or "dpa" in l:
        return "DPA"
    if "nondisclosure" in l or "nda" in l:
        return "NDA"
    if "statement of work" in l or "sow" in l:
        return "SOW"
    if "master services" in l or "services agreement" in l or "msa" in l:
        return "MSA"
    if "flow-down" in l or "subcontractor" in l:
        return "BAA"
    return None


BLANK_SIG = re.compile(r"(?:by|name|title|date)\s*:\s*_{4,}", re.I)
EXECUTED_HINT = re.compile(r"executed pdf|\[signed\]|duly executed|signed by|acknowledged and agreed", re.I)


def is_executed(text):
    """Has this document actually been signed?

    A draft with an empty signature block is not an agreement. This is the
    difference between 'we have a BAA' and 'we have a BAA nobody signed', and
    for HIPAA only the second sentence matters.
    """
    blanks = len(BLANK_SIG.findall(text))
    if EXECUTED_HINT.search(text) and blanks == 0:
        return True, "signed"
    if blanks >= 2:
        return False, f"signature block is empty ({blanks} unfilled fields)"
    if EXECUTED_HINT.search(text):
        return True, "signed"
    if re.search(r"\bdraft\b", text[:600], re.I):
        return False, "the document says it is a draft"
    return False, "no signature could be found"


def assess(label, file_name, file_text):
    """Judge one attached companion document against what was required."""
    want = expected_code(label)
    got = classify(file_text)
    signed, why = is_executed(file_text)

    if want and want not in got:
        return {"ok": False, "level": "wrong", "file": file_name,
                "message": f"This file does not look like a {label}. "
                           f"It reads as: {', '.join(sorted(got)) or 'an unrecognised document type'}."}
    if not signed:
        return {"ok": False, "level": "unsigned", "file": file_name,
                "message": f"Found, but not signed — {why}. An unsigned agreement does not satisfy "
                           f"the requirement, and starting work on it carries the same exposure as "
                           f"having nothing at all."}
    return {"ok": True, "level": "ok", "file": file_name,
            "message": f"Found and signed."}
