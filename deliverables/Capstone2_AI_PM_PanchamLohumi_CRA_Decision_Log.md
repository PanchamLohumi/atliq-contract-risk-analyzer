# Capstone 2 — AtliQ Contract Risk Analyzer
## Decision Log & Traceability
**Pancham Lohumi · AI PM Cohort 2 (Codebasics) · Submission 12 Oct 2026 · Demo 17–18 Oct 2026**

This log exists so that in the viva I can answer three questions about any part of the
submission: *what did you decide, what else could you have done, and which cohort
concept led you there.*

Dataset "today" = **28 September 2026**. Client/owner of this track: **Aakash**.

---

## 1. Decision Log

| # | Decision | Alternatives considered | Why this one | Cohort concept | Decided by | Date |
|---|---|---|---|---|---|---|
| D-01 | Take Capstone 2 (Contract Risk Analyzer) rather than Capstone 1 (Sales & CRM Assistant) | Capstone 1; Bring Your Own Product | Contract review is a judgement-heavy, high-consequence process, so guardrails and evals carry real weight. My QA Lead background (test design, severity, false positives vs misses) transfers directly. Rarer choice, so the submission stands out. | S14 track choice; S8 evals as the core AI PM skill | Me | 1 Oct |
| D-02 | Primary persona = **Karandeep (CEO, sole signatory)**. Sellers (Bhavin, Dhaval, Jay), Pranav and outside counsel are secondary stakeholders. | Centre on the sellers waiting in the queue | Karandeep is the only person who reviews and signs. The queue is a symptom of his bottleneck, not the root cause. Fixing his review fixes their wait. | S4 persona (one primary persona, hypothesis not survey) | Me | 1 Oct |
| D-03 | Scope the solution to **3 core checks** rather than attacking every problem in the dataset | Build 6+ checks; build one check very deeply | ~8 hours of build time. A narrow tool with strong evals beats a broad one that half-works. *Status: provisional — to be re-validated against the Opportunity Map dot vote (D-08).* | S14 Feasibility Impact Analysis (don't pick low-feasibility work); S12 MVP boundary | AI proposed, I confirmed | 1 Oct |
| D-04 | Opportunity Map process boundary: **Input = contract received → Output = signed or rejected** | Narrow (inbox → review brief ready); wide (deal agreed → signed → obligations registered) | The capstone brief says to keep the lifecycle simple and spend the effort on the review. ~8 steps, with the review itself broken into finer steps. | S11 — every Opportunity Map starts by fixing Input and Output | Me | 4 Oct |
| D-05 | Prototype: **Streamlit / FastAPI deployed on Render or Railway** | Streamlit Community Cloud; Next.js on Vercel | Approved in S14. Gives more control than Community Cloud. **Known risk:** free-tier services spin down when idle, so a cold start could cost ~a minute of the 5-minute demo video. Mitigation: warm the app before recording; Streamlit Community Cloud held as fallback. | S6 vibe-coding stack; S14 recommended stack | Me (challenged once by AI, held) | 4 Oct |
| D-06 | Model API: **Groq free tier** | Google Gemini free tier (larger context); Claude API (paid) | What the cohort used in S6, free with no card, and mentors can help debug it. Contracts in the dataset are 5–23 KB, so context size is not a blocker. | S6 Groq setup; S9 model choice is the PM's biggest cost lever | Me | 4 Oct |
| D-07 | Close the research gap by running a **Mom's Test conversation with Aakash** at client office hours (confirmed 7 Oct, 8pm) | Document the gap in the assumptions log and move on | S12 is explicit: do not write the current state from your own head. All research so far is secondary (documents only). One real conversation upgrades the whole submission. | S4 Mom's Test; S12 "if you have not had that conversation, do not write it" | Me | 4 Oct |
| D-08 | Build the Miro board by **pasting the drafted blocks by hand**, not by generating it through the Miro REST API | Script the board via the API from my laptop (token + connected folder); hybrid start-manual-then-switch | Zero setup, and handling the canvas myself means I can actually navigate and defend the board in the viva rather than presenting something generated for me. | S11 — the canvas is a thinking tool, and the PM leads the room | Me | 6 Oct |
| D-10 | **Dot vote: Step 5** (cross-check against what AtliQ already signed), with an explicit note that fixing step 5 also removes most of step 3's pain | Step 4 (where the hours go); Step 3 (assemble context); merging steps 3 and 5 into one | Step 5 is the only column whose tools row is empty. An empty tools row means nobody has managed to build a tool for it, which signals unmet need, not unimportance. Step 4 is the obvious AI fit but, by my own reasoning, a clause summariser is blind to history and would not have prevented Brightwater, which failed from not reading at all rather than reading slowly. I first wanted to merge 3 and 5; held the method instead and kept them separate, because the mentors enforced staying in lane and merging would have grown v1 scope. | S11 dot vote (most cumbersome step, not best AI fit); S2 least intelligent technique; S8 failure-mode reasoning | Me (AI challenged the merge, I took the refinement) | 7 Oct |
| D-11 | The product's core artifact is a **commitments register**, not a search tool | A search-and-compare tool over the existing contracts | Repeatedly proposed "a search register" and "a tool for search and compare" before realising the missing thing is the data, not the tool. You cannot search what was never written down. Counsel could not advise without it, Jay asked for it and got silence, and step 8 never creates it, so step 3 restarts from zero every time. | S4 root cause, not symptom; S15 data readiness | Me (corrected during the canvas walkthrough) | 7 Oct |
| D-12 | **Do not trust the tracker's `restrictive_clauses` column** as a source | Use it as a cross-check or seed | The column is blank even for contracts that do carry restrictions (Al Noor, Crestline, CloudSpan). It is blank because filling it honestly requires legal analysis, not because of poor discipline. Feeding it to the system would teach it that those contracts are unrestricted. | S15 data readiness; S8 groundedness | Me | 7 Oct |
| D-13 | **Severity is ranked by consequence, not by model confidence** | Rank by confidence score | A low-confidence flag on uncapped liability matters more than a high-confidence flag on payment terms. Pairs with the precision/recall trade-off that must be stated in the PRD. | S8 precision vs recall; S12 eval criteria | Me | 7 Oct |
| D-09 | Triage header = **three fixed categories** (past promises / red-line deviations / bundle completeness), each line leading with its verdict | Verdict → biggest reason → next action; or a hybrid verdict banner above the three categories | A fixed structure means Karandeep always knows where to look, and the three lines map cleanly to the three checks, which keeps one coherent story across all seven deliverables. Refinement adopted: each line opens with a verdict word, not a category label, so the answer arrives before the explanation. | S12 behaviour and output specification; S13 AI UX | Me (challenged once, held, refined) | 6 Oct |

---

## 1b. Client Validation — Office Hours with Aakash Pardeshi, 7 Oct 2026

Closes open item O-01. All research before this date was secondary (documents only).

### Baselines, in the client's words

| Measure | Value | Quote |
|---|---|---|
| Review time today | ~3 hours per contract | "let's consider Karan takes around 3 hours to properly review the entire contract" |
| Target | under 5 minutes end to end | "if I can get the result, overall result in less than five minutes, then it would be helpful for us to move fast" |
| Queue time | ~1 week | "a particular contract will stay in Karan's state for at least a week by the time he gets to that" |
| Volume | ~20 contracts/month (client estimate, hedged) | "25 would be a bit too much. Let's say 20." Dataset says ~9. Discrepancy carried openly. |
| Counsel spend | Pending; to be posted on Discord | Two categories named: litigation, and complex-contract review |
| Language | English only for MVP | "for sake of this MVP, let's keep it to English" |
| Cost ceiling | None stated | "we don't have any preference or any cost as such in mind" |

### What the client is most worried about — validates D-10

> "The most worrying part is, you know, NDA or maybe conflict of interest. If I'm working with a healthcare client from US and there is a certain period, say for example for 2 years, I cannot take a project from a competitor. But what if the project ends, and there is a hot lead from the competitor for the same work? ... What if Karan is too busy to keep that in mind, that this project happened 2 years back ... if it is uncovered, then it will be a huge fine for us."

He raised the **expiry** question unprompted, which is exactly the Orbit control case. Asked separately what takes *longest*, he answered reading every clause, because no universal template exists. **Longest and most-worrying are different things, and the dot was placed on the worry.**

### How they find past commitments today — the current state, in his words

> "We talk to the project leads, we talk to the project managers of different projects ... There is no way that we have this documented as it's a small company. There is no way there is a single universal place where all the project data or project knowledge is kept. So whenever we are going through the new project, we have to manually go and reconcile, and we need to talk to people and adhere to their best judgment."

On checking whether an old restriction is still live: "It's a manual review of the older contracts ... we need to go and check and rely on best judgment and Karan's memory."

### Definition of "safe to sign" — the product's acceptance criteria

1. "Absolute clarity on the clauses which are mentioned"
2. "It is benchmarked, or it is verified by our policies which we have"
3. "No clause as such which will impact our brand reputation"
4. "There is no conflict of interest based on the history of the clients which we have served in past"

### What the system must never do

> "Sign the contract, give approval, or maybe do anything. My first intention is to just review it and give it to Karan just to analyse. And make his life better and easy. And be accurate."

### Three contradictions between stated preference and evidence

| # | Client says | Evidence shows | How this is handled |
|---|---|---|---|
| T-1 | "We will be diligently going through the entire list of alerts ... it won't happen that we start ignoring P3, P4." | Brightwater was signed from an airport gate with "Looks standard, signing now." | Never suppress a flag — recall is the launch gate — but order strictly by consequence so the 11pm reader meets the ruinous ones first. Fatigue is solved by ordering, not filtering. |
| T-2 | ~20 contracts a month | Dataset records ~9 a month, up from ~5 | Use 20 for cost estimation (conservative, and it is the client's number). Note the discrepancy rather than hide it. |
| T-3 | "There is no fixed policy as such ... it requires majorly a human judgment to crack it." | negotiation_notes.md shows consistently applied positions: LD 0.5%/week of milestone capped at 5%, liability 1x fees, mutual indemnity, payment 30 to 45 days, mutual NDAs only, and a 120k euro deal refused over unlimited liability. | The policy exists in behaviour but was never written down. The product derives the playbook from past negotiations rather than asking anyone to author one. Scoped to **legal positions only** — the client is right that commercial rates flex with cash position, repeat business and brand value. |

**The insight T-3 produces:** AtliQ has two undocumented memories — *what we promised* (the commitments register) and *how we negotiate* (the playbook). Both live in one person's head. The product writes down both by reading what AtliQ actually did. That is also why a bought tool does not solve this: a third-party CLM has no memory of AtliQ's own history.

### Scope expansions raised and declined

| Raised | Decision | Reason |
|---|---|---|
| Track promises made over phone and WhatsApp ("yes, it is important to track them") | Out of v1, named as v2 | A capture problem, not a review problem. No such data exists in the dataset. |
| Sync the mailbox for centralised intake | Out of v1 | Client said "we can definitely think about that", not that it is required. |
| Counterparty legitimacy and payment-default history | Out | No data for it anywhere in the dataset. |

### Changes forced by the session

- **Persona widens.** Not Karandeep alone: a management team with assignable primary and secondary reviewers. "Someone can be a primary reviewer, someone can be a secondary reviewer, just to ensure that there is nothing missed." Karandeep is the authority, delegable to Bhavin, Dhaval or Jay when busy.
- **Guardrail wording** becomes "a human with signing authority decides", not "Karandeep decides".
- **RBAC confirmed:** CEO super-admin, sellers restricted and unable to see other clients' contracts, no client-facing users.
- **Synthetic test contracts are explicitly permitted** for edge cases and evals: "feel free to add it ... there's no restriction as such."
- **Scope confirmed verbatim:** "the phases that we need to consider as part of our capstone is received, reviewed, negotiated, signed or rejected. And we need to spend our major time in the review phase."

---

## 2. Open Items & Known Weaknesses

Carrying these openly is itself a PM move (S12 open questions and assumptions log).

| # | Item | Why it matters | Status |
|---|---|---|---|
| O-01 | **All research to date is secondary.** Persona, empathy map and 5 Whys were built from documents, never from a user conversation. | S4 and S12 both require a real conversation behind the current state. A judge will ask "how do you know?" | **CLOSED 7 Oct** at client office hours. See section 1b. Baselines, the "safe to sign" definition and the never-do list are now in the client's own words. |
| O-07 | **Counsel spend per year is unknown.** Aakash is posting it to the Discord capstone channel. | Feeds the cost-benefit case in the cost estimation sheet. | Open. Check Discord; use the ₹1.2 lakh per engagement figure from the dataset as an interim. |
| O-08 | **The playbook must be derived, not authored.** The client states no fixed policy exists; the dataset shows one applied consistently. | If the derivation is wrong, every playbook-deviation flag is wrong. | Open. Derive from negotiation_notes.md plus the signed contracts, show the derivation, and label it as inferred rather than stated. |
| O-02 | **Our guardrail design says Karandeep reviews every flag.** | S11's most-repeated correction: "a guardrail that says a human reviews everything is not a guardrail, it is a refusal to automate." Needs sampling + triage: full review on critical flags, spot-check on the quiet ones. | To fix in D1 revision and carry into the PRD. |
| O-03 | **JTBD statement missing from Step 1.** | S4's framework is five steps (Mom's Test → JTBD → Persona → Empathy Map → 5 Whys). We did three. | To add after the Aakash conversation. |
| O-04 | Targets in the Step 1 draft (e.g. "review down to 45 minutes") are **my assumptions, not data**. | S12: assumptions are fine, but say so plainly — "do not ask why it is 85 and not 90". | Label as assumptions; validate what I can with Aakash. |
| O-05 | **TravelHub vs the Al Noor non-compete is a judgement call**, not a confirmed collision. Depends on whether a travel app counts as a "Hospitality Business". | Overstating it would be exactly the false-alarm behaviour the product is meant to avoid. | Keep flagged as *probable, needs counsel*. |
| O-06 | The Harrington PHI situation is **potential unauthorised exposure, unconfirmed** — the legal characterisation is for counsel. | Our own tool must hedge the same way. Modelling that discipline in the submission is the point. | Wording locked; do not escalate. |

---

## 3. Traceability Thread

One coherent story is what the rubric rewards (S14: "as one coherent story"). Each row
must survive end to end — pain point → opportunity → requirement → eval → demo moment.

| Pain point (D1) | Opportunity (D2) | PRD requirement (D3) | Eval test (D3/D5) | Demo moment (D6/D7) |
|---|---|---|---|---|
| *To be filled after the Opportunity Map dot vote* | | | | |

---

## 4. AI Fit — Why AI, and Where Deliberately Not

Assessment explicitly weighs "AI fit (why AI is the right tool here)" (S14).
S2's rule: *reach for the least intelligent, least expensive technique that solves the problem.*
S8: if ~70% of checks can be handled by rules, use rules there and reserve the model for the harder 30%.

| Check | Technique | Why |
|---|---|---|
| Entity vs governing-law mismatch | **Rule-based** | Deterministic lookup against `atliq_entities.md`. Using an LLM here would add cost, latency and hallucination risk for zero gain. |
| Missing document in a deal bundle | **Rule-based** | A checklist keyed on deal type (US healthcare → NDA + BAA + MSA; EU personal data → DPA). Deterministic. |
| Collision with past commitments | **Retrieval + generation** | Requires reading unstructured signed contracts, understanding clause meaning, and reasoning about scope (Affiliates, territory, waivers, expiry). No rule can do this. |
| Risky-clause detection against the playbook | **Generation with citation** | Same clause is expressed a hundred different ways across counterparties' paper. Pattern matching misses it. |

**The line I will defend in the viva:** AI is used only where the task needs language
understanding and judgement. Two of the checks are deliberately *not* AI, and saying so
is part of the answer.

---

## 5. Guardrails — Running List

To be completed from the Opportunity Map guardrail cards (S11) and the PRD failure-mode
table (S12). Recorded here so each one has a written commitment, not just a card name —
"a card without a written commitment is decoration" (S11).

| Guardrail | Written commitment | Source |
|---|---|---|
| Human augmentation / human control | A human decides and signs. The system never auto-approves, rejects or signs. Overrides are logged. | S11 |
| Accountability | Named human ownership expressed as a concrete SLA, not "the AI is accountable". | S11 (mentor correction to Team D) |
| Partial human in the loop | Critical flags reviewed in full; quiet flags spot-checked on a sample. Not "review everything". | S11 (the session's most-repeated correction) |
| Groundedness | No flag without a verbatim quote, file name and clause reference. | S8 groundedness; S12 eval criteria |
| No legal advice | The system never says "safe to sign". It reports "no deviations or active conflicts found". | Dataset constraint + S13 responsible AI |
| Past deals are evidence, not policy | Signed contracts must not become precedent (Brightwater's uncapped LDs, the PipeKit IP giveaway). | My own addition, adopted from a second-opinion review |
| Data residency / confidentiality | Confidential contracts and any PHI never go to a model-training API. | S15 data residency |

---

## 6. Behaviour States vs Guardrails

Noted because I asked this question in Session 12 and it is a likely viva question.

- A **behaviour state** tells the AI what to do when it is uncertain (state management).
- A **guardrail** names a way the AI can fail and the control that prevents it.

They live in different PRD sections for that reason.

---

*Log started 4 Oct 2026. Updated as each decision is made.*
