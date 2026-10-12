"""Loads the three records the product depends on and computes liveness.

The central rule, and the one that took a correction to get right: a contract
ending is NOT the same event as its obligations ending. Al Noor's agreement
expires 14 Mar 2028 but its Restricted Period runs to 14 Sep 2029. Liveness is
always measured against the obligation end date.
"""
import json, datetime
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def _load(name):
    with open(DATA / name, encoding="utf-8") as f:
        return json.load(f)


def load_all():
    reg = _load("commitments_register.json")
    return reg, _load("playbook.json"), _load("entities.json")


def parse_date(s):
    if not s:
        return None
    try:
        return datetime.date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def liveness(commitment, today=None):
    """Return (is_live, label, detail). Never guesses: an absent obligation end
    date is reported as indefinite rather than assumed expired."""
    today = today or datetime.date.today()
    end = parse_date(commitment.get("expires"))
    basis = commitment.get("expiry_basis")
    if end is None:
        return True, "no end date recorded", (
            "No obligation end date is recorded for this commitment, so it is treated as live. "
            "Survival clauses in AtliQ's contracts run from three years to indefinite.")
    if end < today:
        d = (today - end).days
        return False, f"lapsed {end.isoformat()}", (
            (basis + " ") if basis else "") + f"The obligation ended {d} days ago."
    d = (end - today).days
    return True, f"live until {end.isoformat()}", (
        (basis + " ") if basis else "") + f"Still binding for another {d} days."


def waivers_for(reg, commitment_id):
    out = []
    for c in reg["commitments"]:
        if c.get("type") != "waiver":
            continue
        if c.get("waiver_of") == commitment_id or (
            commitment_id == "CM-001" and c.get("id") == "CM-002"
        ):
            out.append(c)
    return out


def active_commitments(reg, today=None):
    live, lapsed = [], []
    for c in reg["commitments"]:
        if c.get("type") == "waiver":
            continue
        ok, label, detail = liveness(c, today)
        (live if ok else lapsed).append((c, label, detail))
    return live, lapsed
