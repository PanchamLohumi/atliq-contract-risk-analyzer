# AtliQ Contract Risk Analyzer

**Capstone 2 — Codebasics LIVE AI PM Cohort 2**
Pancham Lohumi · October 2026

Checks an incoming contract against everything AtliQ has already signed, and returns a
one-page triage brief. It is a review aid. It never signs, never approves, and never
says a contract is safe to sign.

---

## Submission index — all seven deliverables

| # | Deliverable | Where it is |
|---|---|---|
| 1 | Problem Discovery & User Research | [`deliverables/…_Problem_Discovery.xlsx`](deliverables/Capstone2_AI_PM_PanchamLohumi_CRA_Problem_Discovery.xlsx) |
| 2 | AI Opportunity Map | [Miro board](https://miro.com/app/board/uXjVEeHZ57w=/) — process map, dot vote, and the AI redesign of the voted step |
| 3 | AI PRD | [`deliverables/…_PRD.docx`](deliverables/Capstone2_AI_PM_PanchamLohumi_CRA_PRD.docx) |
| 4 | Cost Estimation | [`deliverables/…_Cost_Estimation.xlsx`](deliverables/Capstone2_AI_PM_PanchamLohumi_CRA_Cost_Estimation.xlsx) |
| 5 | Working prototype | This repository. Live app: **https://atliq-contract-risk-analyzer-panchamlohumi.streamlit.app/** · run locally with the steps below |
| 6 | Presentation | [`deliverables/…_Presentation.pdf`](deliverables/Capstone2_AI_PM_PanchamLohumi_CRA_Presentation.pdf) |
| 7 | Stakeholder demo video | **[VIDEO URL]** (~5 min) |

**Supporting material, not required but submitted:**

| | |
|---|---|
| Test strategy & coverage matrix | [`deliverables/…_Test_Strategy.docx`](deliverables/Capstone2_AI_PM_PanchamLohumi_CRA_Test_Strategy.docx) — all 15 contracts, expected behaviour, negative tests, disclosed limitations |
| Decision log | [`deliverables/…_Decision_Log.md`](deliverables/Capstone2_AI_PM_PanchamLohumi_CRA_Decision_Log.md) — every product decision, what evidence drove it, and the open questions |

---

## Run it locally

**1. Create a file called `.env`** in this folder with one line:

```
GROQ_API_KEY=your_key_here
```

Get a free key at console.groq.com. The key is never requested in the interface:
Karandeep is a CEO reviewing contracts, not a developer, so credentials are deployment
configuration, resolved from Streamlit secrets, the environment, or `.env`, in that order.

**2. Install and run:**

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

Opens at http://localhost:8501

**Without a key** the three rule-based checks still run, and the two model-based checks
report `NOT RUN` in the manifest. That is deliberate: a brief that silently skips a check
is more dangerous than one that admits it.

**3. Check it works** (optional):

```bash
python check_setup.py       # verifies Python, packages, data files, and the API key
python evals/run_evals.py   # 13 cases, 6 launch blockers. No API key needed.
```

## Deploy

Streamlit Community Cloud, free, straight from this repo. Set `GROQ_API_KEY` in the app's
**Secrets** panel — no code change needed, because `engine/config.py` reads Streamlit
secrets first. Vercel is not suitable here; it does not host long-running Python processes.

---

## What this does

AtliQ's CEO personally reviews and signs every client and partner contract. There is no
legal team. The thing he most needs to know when a contract arrives is whether it collides
with something AtliQ already promised somebody else — and no record of those promises has
ever existed.

The system builds that record, then checks each draft against it.

### Five checks, and only two use a model

| # | Check | How it runs |
|---|---|---|
| 1 | Collisions with past commitments, including whether a waiver actually covers this deal | Retrieval + model reasoning |
| 2 | Is that commitment still binding **today**? | Deterministic date logic |
| 3 | Risk terms against contract value | **Deterministic arithmetic** |
| 4 | Signing entity vs governing law vs invoicing | **Deterministic lookup** |
| 5 | Is the document bundle complete for this deal type? | **Deterministic rules** |

Three of the five use no model at all — a lookup and some arithmetic do not need one.
The other two are not rule-shaped: judging whether a clause written in one counterparty's
language restricts a deal described in another's means reading unstructured legal prose
and reasoning about defined terms, scope, territory and time.

---

## What I added to the dataset

The supplied dataset was used unchanged. Nothing was deleted or edited. Four files were
**added**, and they are the substance of the product:

| File | What it is | How it was built |
|---|---|---|
| `data/commitments_register.json` | **13 commitments** extracted from the 17 signed contracts: non-competes, exclusivity, most-favoured pricing, IP assigned away, data restrictions, and one waiver. Every entry carries the source file, the clause reference and a verbatim quote. | AI extraction, then verified clause by clause against the source text. The dataset's own README states that no such register exists at AtliQ and that "that absence is part of the problem". |
| `data/playbook.json` | AtliQ's **derived negotiating positions**, read from its own signed contracts. Liability is capped at 1× fees in 9 of 12; three contracts deviate. | Pattern extraction across the archive. Labelled **inferred, not policy** — the client confirmed "It is Karan's preference. There is no fixed rule." |
| `data/entities.json` | A structured form of `atliq_entities.md`, plus the companion-document rules by deal type (US healthcare → BAA; EU personal data → DPA). | Hand-written from the supplied fact sheet and the dataset README. |
| `evals/eval_set.json` | **13 evaluation cases**, 6 of them launch blockers, drawn from the dataset plus synthetic edge cases. | Written against the PRD's eval criteria. |

### Two things deliberately left out

- **The tracker's `restrictive_clauses` column.** It is blank for every contract that
  actually carries a restriction, including Al Noor, Crestline and CloudSpan. Feeding it
  in would teach the system that those contracts are unrestricted.
- **Outcome labels from past deals treated as approval.** Brightwater and Northwind were
  signed, but signed does not mean approved. Treating them as precedent would teach the
  system that uncapped penalties and IP giveaways are acceptable.

### Key dates

The register is computed against a current date you can change in the sidebar. The
dataset's "today" is 2026-09-28; the app defaults to the real current date.

---

## Guardrails that are implemented, not just promised

- **Cite or be cut.** Every finding's quote is matched word for word against the file it
  cites before the brief renders. A finding that fails is deleted and logged in the
  manifest. See `engine/checks.py: verify_citations`.
- **No write actions.** The system produces a document and nothing else. No e-signature
  integration in any version. Even a human reviewer cannot be delegated the signature —
  only Karandeep signs.
- **Nothing is suppressed.** Every finding appears, ordered by consequence. Ordering is
  the mitigation for alert fatigue, not filtering. The client asked to see all of them.
- **Lapsed restrictions are shown, not hidden**, under *Considered and cleared*, with the
  date they expired. The client asked for this: seeing what was ruled out builds trust.
- **Uncertainty is stated.** Anything the system cannot resolve is marked *needs human
  judgement* with a disclaimer, rather than asserted flatly or quietly dropped.
- **Attached companion documents are checked, not trusted.** The system verifies that an
  attached file really is that kind of document and that it has actually been signed. An
  unsigned Business Associate Agreement satisfies nothing under HIPAA.

---

## Layout

```
app.py                      Streamlit interface
check_setup.py              Pre-flight check: Python, packages, data, API key
engine/config.py            Resolves the API key from secrets / env / .env
engine/llm.py               Model access; discovers available models at runtime
engine/register.py          Loads the register; liveness on the OBLIGATION date
engine/checks.py            The five checks, citation verification, ordering
engine/papers.py            Companion paperwork: what a deal needs, and whether
                            what arrived is the right document and signed
engine/brief.py             Verdict header and brief assembly
data/signed/                The 17 signed contracts (supplied)
data/samples/               The 15 incoming drafts (supplied)
evals/run_evals.py          Scorecard runner
```

## Known limitations

- The paperwork scan reads only the document in front of it. The Kriti subcontract names
  Rheinwerk as end client but never says "personal data", so no flow-down requirement is
  raised even though AtliQ owes Rheinwerk GDPR obligations.
- Six counterparties appear in the tracker with no contract file, so any commitment inside
  them is invisible to the register.
- English only. Gulf Crown contains an Arabic-prevails clause.
- Client and partner contracts only. Employee and freelancer paperwork is HR's, and
  government contracts are out of scope.
- The model path has been exercised on a developer machine only. No load testing.

## Try it

| Contract | What you should see |
|---|---|
| `2026-09-27_loopmart_mutual_nda_draft.md` | The clean case. Three green lines. |
| `2026-09-18_gulf_crown_hotels_msa_draft.md` | A conflict with the Al Noor GCC non-compete, live until 14 Sep 2029 — eighteen months after that contract itself expires. A waiver exists and does **not** cover this deal. |
| `2026-09-10_harrington_health_msa_draft.md` | Paperwork banner. Attach the signed NDA (green) and the BAA draft (amber — found, but nobody signed it). |

Set the sidebar date to **2029-10-01**, re-run Gulf Crown, and watch the restriction move
to *Considered and cleared* as its tail runs out.
