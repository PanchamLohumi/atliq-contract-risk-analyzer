"""Runs the evaluation set and prints a scorecard.

Eval criteria decide whether the system is fit to LAUNCH. Success metrics
measure business outcomes AFTER launch. This file is the former.

Six of the twelve cases are launch blockers. A single blocker failure means the
system does not ship, regardless of how the rest score.

Runs without an API key: cases use fixed fact fixtures so the scorecard is
reproducible by anyone grading this.
"""
import sys, json, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine import register, brief, checks  # noqa: E402

SEV = checks.SEV_ORDER


def _at_least(actual, floor):
    return SEV.get(actual, 9) <= SEV.get(floor, 9)


def evaluate(case, reg, pb, ent):
    at = datetime.date.fromisoformat(case["as_at"])
    out = brief.build(dict(case["facts"]), reg, pb, ent, case.get("companion_docs", []), at)
    e = case["expect"]
    fails = []
    fids = [f.get("commitment_id") for f in out["findings"]]
    cids = [c.get("commitment_id") for c in out["cleared"]]
    # Scan only GENERATED content. The fixed disclaimer legitimately contains
    # "safe to sign" inside a negation, and testing against it was an error in
    # the eval, not a defect in the product.
    blob = json.dumps({k: out[k] for k in ("header", "findings", "cleared")}, default=str).lower()

    if "finding_contains_commitment" in e:
        cid = e["finding_contains_commitment"]
        if cid not in fids:
            fails.append(f"{cid} was not raised as a finding")
        elif "min_severity" in e:
            f = next(f for f in out["findings"] if f.get("commitment_id") == cid)
            if not _at_least(f.get("severity"), e["min_severity"]):
                fails.append(f"{cid} raised at {f.get('severity')}, expected at least {e['min_severity']}")
    if "waiver_does_not_clear" in e:
        cid = e["waiver_does_not_clear"]
        f = next((f for f in out["findings"] if f.get("commitment_id") == cid), None)
        if f is None:
            fails.append(f"{cid} not raised at all, so the waiver test did not happen")
        elif not f.get("waiver"):
            fails.append(f"no waiver was evaluated against {cid}")
        elif f["waiver"].get("covers_this_deal"):
            fails.append(f"the waiver was read as clearing {cid} - this is the breach-clearing failure mode")
    if "cleared_contains" in e and e["cleared_contains"] not in cids:
        fails.append(f"{e['cleared_contains']} missing from the cleared section")
    if "no_finding_for" in e and e["no_finding_for"] in fids:
        fails.append(f"{e['no_finding_for']} was raised as an active finding when it should be cleared")
    if "finding_title_contains" in e and not any(
            e["finding_title_contains"].lower() in (f.get("title") or "").lower() for f in out["findings"]):
        fails.append(f"no finding titled like '{e['finding_title_contains']}'")
    if "finding_severity_at_least" in e:
        grp = [f for f in out["findings"] if f.get("check") == e.get("check")] or out["findings"]
        if not any(_at_least(f.get("severity"), e["finding_severity_at_least"]) for f in grp):
            fails.append(f"nothing reached {e['finding_severity_at_least']}")
    if "no_finding_for_check" in e and any(f.get("check") == e["no_finding_for_check"] for f in out["findings"]):
        fails.append(f"false positive: a {e['no_finding_for_check']} finding was raised on an in-pattern term")
    if "max_severity" in e:
        bad = [f for f in out["findings"] if SEV.get(f.get("severity"), 9) < SEV.get(e["max_severity"], 9)]
        if bad:
            fails.append(f"{len(bad)} finding(s) above {e['max_severity']}: " + "; ".join(b["title"][:40] for b in bad))
    if e.get("zero_dropped_citations") and out["dropped"]:
        fails.append(f"{len(out['dropped'])} finding(s) failed citation verification")
    for phrase in e.get("output_must_not_contain", []):
        if phrase in blob:
            fails.append(f"output contained forbidden phrase: '{phrase}'")
    return (not fails), fails, out


def main():
    reg, pb, ent = register.load_all()
    spec = json.loads((ROOT / "evals" / "eval_set.json").read_text(encoding="utf-8"))
    rows, blocker_fail = [], 0
    print("=" * 84)
    print("ATLIQ CONTRACT RISK ANALYZER - EVALUATION SCORECARD")
    print("Run at", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 84)
    for case in spec["cases"]:
        ok, fails, _ = evaluate(case, reg, pb, ent)
        tag = "BLOCKER" if case["blocker"] else "       "
        print(f"{'PASS' if ok else 'FAIL'}  {tag}  {case['id']}  {case['dimension']:26} {case['name'][:46]}")
        for f in fails:
            print(f"                     -> {f}")
        if not ok and case["blocker"]:
            blocker_fail += 1
        rows.append({"id": case["id"], "dimension": case["dimension"],
                     "blocker": case["blocker"], "passed": ok, "failures": fails})
    passed = sum(r["passed"] for r in rows)
    print("-" * 84)
    print(f"{passed}/{len(rows)} passed.  Launch blockers failed: {blocker_fail}")
    print("LAUNCH GATE: " + ("OPEN - all blockers pass" if blocker_fail == 0
                             else f"CLOSED - {blocker_fail} blocker(s) failing"))
    print("=" * 84)
    (ROOT / "evals" / "scorecard.json").write_text(json.dumps(
        {"run_at": datetime.datetime.now().isoformat(timespec="seconds"),
         "passed": passed, "total": len(rows), "blockers_failed": blocker_fail,
         "launch_gate": "open" if blocker_fail == 0 else "closed",
         "results": rows}, indent=2), encoding="utf-8")
    print("Written: evals/scorecard.json")
    return 1 if blocker_fail else 0


if __name__ == "__main__":
    sys.exit(main())
