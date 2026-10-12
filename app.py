import os, io, time, datetime
from pathlib import Path
import streamlit as st

from engine import register, checks, brief, llm, config, papers

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / "data" / "samples"
KEY_FOUND, KEY_SOURCE = config.load_key()

st.set_page_config(page_title="AtliQ Contract Risk Analyzer", page_icon="::", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 2.2rem; max-width: 1180px;}
.verdict {border-radius:10px; padding:14px 18px; margin-bottom:10px; border:1px solid #e7e7e7;}
.verdict .word {font-weight:700; font-size:1.05rem; letter-spacing:.02em;}
.verdict .lbl {font-size:.78rem; text-transform:uppercase; letter-spacing:.08em; color:#595959;}
.verdict .q {font-size:.8rem; color:#8a8a8a; font-style:italic;}
.verdict .tail {font-size:.92rem; color:#313131; margin-top:2px;}
.v-critical{background:#fff0f0;border-color:#ffc6c6;} .v-critical .word{color:#bd0a0a;}
.v-high{background:#fff5ed;border-color:#f8d3af;} .v-high .word{color:#9b4a08;}
.v-medium{background:#fffbed;border-color:#fff6b6;} .v-medium .word{color:#af7e04;}
.v-low{background:#f7f7f7;} .v-low .word{color:#595959;}
.v-clear{background:#eaf9ef;border-color:#adf0c7;} .v-clear .word{color:#067429;}
.v-unknown{background:#f4f2fd;border-color:#dedaff;} .v-unknown .word{color:#6631d7;}
blockquote {border-left:3px solid #b0b0b0; margin:6px 0; padding:2px 0 2px 12px; color:#444; font-size:.9rem;}
.small {font-size:.82rem; color:#595959;}
.step {font-size:.9rem; color:#595959; padding:2px 0;}
</style>
""", unsafe_allow_html=True)

# Plain words first; the technical severity stays available but secondary.
SEV_PLAIN = {"critical": "Blocks signing", "high": "Needs attention",
             "medium": "Worth a look", "low": "Minor", "info": "For information"}

st.title("AtliQ Contract Risk Analyzer")
st.caption("Checks an incoming draft against everything AtliQ has already signed. "
           "A review aid, not legal advice. It never says safe to sign.")

# ----------------------------------------------------------------- sidebar
with st.sidebar:
    st.subheader("Contract to review")
    names = sorted(p.name for p in SAMPLES.glob("*.md"))
    pick = st.selectbox("Pick one from the queue", ["-- upload instead --"] + names,
                        index=1 if names else 0)
    up = st.file_uploader("or upload a contract", type=["pdf", "docx", "md", "txt"])

    st.divider()
    today = st.date_input(
        "Treat today's date as", value=datetime.date.today(),
        help="Whether a past promise still binds AtliQ is worked out against this date. "
             "Move it forward to watch a restriction expire.")

    st.divider()
    if KEY_FOUND:
        st.caption(f"All five checks available. Credentials loaded from {KEY_SOURCE}.")
    else:
        st.caption("Running the rule-based checks only. The two checks that need a model "
                   "will report as NOT RUN rather than quietly passing.")
        with st.expander("Developer setup"):
            st.markdown("No API key is configured. Set one of:\n\n"
                        "- a `.env` file in this folder with `GROQ_API_KEY=...`\n"
                        "- `.streamlit/secrets.toml` with `GROQ_API_KEY = \"...\"`\n"
                        "- an app secret, if deployed on Streamlit Community Cloud\n\n"
                        "Then restart. This panel is for whoever deploys the tool, "
                        "not the reviewer using it.")
            tmp = st.text_input("Or paste a key for this session only", type="password")
            if tmp:
                os.environ["GROQ_API_KEY"] = tmp.strip()
                st.rerun()


SIGNED = ROOT / "data" / "signed"


def doc_library():
    """Everything already in AtliQ's folders that could be a companion document."""
    out = {}
    for p in sorted(SIGNED.glob("*.md")):
        out[f"signed/ {p.name}"] = p
    for p in sorted(SAMPLES.glob("*.md")):
        out[f"incoming/ {p.name}"] = p
    return out


def read_upload(f):
    data = f.read()
    if f.name.lower().endswith(".pdf"):
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
    if f.name.lower().endswith(".docx"):
        import docx
        return "\n".join(p.text for p in docx.Document(io.BytesIO(data)).paragraphs)
    return data.decode("utf-8", errors="replace")


text, source_name = None, None
if up is not None:
    text, source_name = read_upload(up), up.name
elif pick and pick != "-- upload instead --":
    text, source_name = (SAMPLES / pick).read_text(encoding="utf-8"), pick

# Changing the contract or the date invalidates the brief on screen. Showing a
# stale result beside a newly chosen draft is how the wrong thing gets signed.
signature = (source_name, str(today))
if st.session_state.get("signature") != signature:
    for k in ("core", "facts", "elapsed", "papers"):
        st.session_state.pop(k, None)
    st.session_state["signature"] = signature

# ----------------------------------------------------- what this thing does
if "core" not in st.session_state:
    st.markdown("#### What this does")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**1. Looks up what we already promised**\n\nAtliQ has signed 17 contracts. "
                    "Some contain promises not to work with certain clients, not to undercut a "
                    "price, or to hand over ownership of something. Nobody has a list of them. "
                    "This tool built one, and checks the new contract against it.")
    with c2:
        st.markdown("**2. Compares it to how we normally contract**\n\nAtliQ has no written policy, "
                    "but its past contracts show a consistent pattern. The tool reads that pattern "
                    "and flags terms that sit outside it — especially where the risk is large "
                    "compared to what the deal is worth.")
    with c3:
        st.markdown("**3. Checks the paperwork is complete**\n\nSome deals are not legal with one "
                    "document alone. A US healthcare contract needs a BAA; an EU one needs a DPA. "
                    "The tool works out what this particular deal needs and tells you what is missing.")
    st.info("It produces a one-page brief for a human to read. It never signs, never approves, "
            "and never tells you a contract is safe to sign.", icon=":material/info:")
    st.divider()

if not text:
    st.info("Pick a contract from the queue in the sidebar, or upload a PDF or Word file.")
    st.stop()

st.markdown(f"**{source_name}**  ·  {len(text.split()):,} words")
with st.expander("Read the contract"):
    st.text(text[:20000])

# ------------------------------------------------- companion paperwork, early
# The moment a contract is chosen, a cheap scan says whether this KIND of deal
# needs extra paperwork. The reviewer is told before waiting on an analysis,
# and can attach what they have first.
need_label, need_docs, need_rule = papers.quick_signals(text)
satisfied, attach_notes = [], []

if need_docs:
    st.error(f"**Extra paperwork required — this is {need_label}.**\n\n{need_rule}", icon=":material/gavel:")
    st.markdown("##### Which of these do you have?")
    st.caption("Attach each one from AtliQ's folders, or upload it. The tool checks that the file "
               "really is that kind of document and that it has actually been signed.")

    lib = doc_library()
    own_codes = papers.classify(text)
    for i, doc in enumerate(need_docs):
        want = papers.expected_code(doc)
        c1, c2 = st.columns([1.05, 1.35])
        with c1:
            st.markdown(f"**{doc}**")
        # The contract under review satisfies its own line in the bundle.
        if want and want in own_codes and want in ("MSA", "SOW"):
            with c2:
                st.success("This is the contract you are reviewing.", icon=":material/task_alt:")
            satisfied.append(doc)
            continue
        with c2:
            choice = st.selectbox("Attach", ["— not supplied —", "Upload a file…"] + list(lib),
                                  key=f"att_{i}", label_visibility="collapsed")
        blob = None
        if choice == "Upload a file…":
            with c2:
                upf = st.file_uploader(f"Upload {doc}", type=["pdf", "docx", "md", "txt"],
                                       key=f"up_{i}", label_visibility="collapsed")
            if upf:
                blob, bname = read_upload(upf), upf.name
        elif choice != "— not supplied —":
            blob, bname = lib[choice].read_text(encoding="utf-8"), choice
        if blob:
            r = papers.assess(doc, bname, blob)
            attach_notes.append((doc, r))
            with c2:
                if r["level"] == "ok":
                    st.success(r["message"], icon=":material/task_alt:")
                    satisfied.append(doc)
                elif r["level"] == "unsigned":
                    st.warning(r["message"], icon=":material/draft:")
                else:
                    st.error(r["message"], icon=":material/report:")
        else:
            with c2:
                st.caption("Nothing attached yet.")
    st.divider()

bcol, _ = st.columns([1, 2.2])
with bcol:
    run = st.button("Analyse this contract", type="primary")

# ------------------------------------------------------------- run the work
if run:
    reg, playbook, entities = register.load_all()
    t0 = time.time()
    box = st.status("Working through the contract...", expanded=True)
    with box:
        st.write("Reading the contract and pulling out the facts: who it is with, where "
                 "they are, what it is worth, what it commits AtliQ to.")
        facts, how = checks.extract_facts(text)
        st.write(f"Checking it against {len(reg['commitments'])} promises AtliQ has already "
                 "made, and working out which of those are still binding today.")
        st.write("Comparing the risk terms to the size of the deal, and the signing entity "
                 "to the governing law.")
        core = brief.analyse(facts, reg, playbook, entities, today)
        core["manifest"]["Draft extraction"] = how
        st.write("Checking every quote word for word against the contract it came from.")
    box.update(label="Done.", state="complete", expanded=False)
    st.session_state.update(core=core, facts=facts, elapsed=time.time() - t0)

core = st.session_state.get("core")
if not core:
    st.stop()

facts = st.session_state["facts"]
_, _, entities = register.load_all()

# The paperwork panel above already collected this, before the analysis ran.
out = brief.assemble(core, facts, entities, satisfied)
elapsed = st.session_state.get("elapsed", 0)

# ------------------------------------------------------------ verdict header
st.markdown("### The brief")
st.caption(f"Produced in {elapsed:.1f} seconds. A human review of this contract takes about "
           f"two hours, or six to eight for a complex one.")

cls_map = {"critical": "v-critical", "high": "v-high", "medium": "v-medium",
           "low": "v-low", "clear": "v-clear", "unknown": "v-unknown"}
questions = {"Past promises": "Does this clash with something we already signed?",
             "Our own paper": "Is this in line with how we normally contract?",
             "Deal completeness": "Is the paperwork right and complete?"}
for label, word, tail, sev in out["header"]:
    st.markdown(
        f'<div class="verdict {cls_map.get(sev, "v-low")}"><div class="lbl">{label}</div>'
        f'<div class="q">{questions.get(label, "")}</div>'
        f'<span class="word">{word}</span><div class="tail">{tail}</div></div>',
        unsafe_allow_html=True)

with st.expander("How to read this"):
    st.markdown(
        "- **The three lines above** answer the three questions a reviewer has to settle before "
        "signing. Read them first; they are written so the verdict is the first thing you see.\n"
        "- **Findings** are listed worst-first. Nothing is hidden or filtered — the ordering is "
        "what saves you time, not leaving things out.\n"
        "- **Every finding quotes the clause it came from** and names the file. If a quote could "
        "not be matched word for word against its source, the finding is deleted before you see it.\n"
        "- **Considered and cleared** shows what the tool checked and ruled out, including "
        "promises that have expired. Seeing what was ruled out is how you know it looked.\n"
        "- **Needs human judgement** means the tool could not settle the question. That is not a "
        "pass. It is a request for you to read the clause yourself.")

# ------------------------------------------------- what could not be checked
if out.get("gaps"):
    st.markdown("#### What could not be checked")
    st.caption("Not problems with the contract. These are things the draft did not contain, "
               "so the check could not run. Never treated as a pass.")
    for g in out["gaps"]:
        st.warning(f"**{g['check']}** — missing: {g['missing']}\n\n{g['remedy']}")

# ----------------------------------------------------------------- findings
st.markdown("#### Findings")
st.caption("Everything the tool found, worst first. Nothing is filtered out.")

if not out["findings"]:
    st.success("Nothing found. See what was checked and ruled out below.")
for i, f in enumerate(out["findings"], 1):
    sev = f.get("severity", "low")
    plain = SEV_PLAIN.get(sev, "Noted")
    flag = "  ·  NEEDS HUMAN JUDGEMENT" if f.get("uncertain") else ""
    with st.expander(f"{i}.  {plain}  —  {f['title']}{flag}", expanded=(i <= 2)):
        det = "  ·  worked out by rule, no model involved" if f.get("deterministic") else ""
        st.markdown(f"<span class='small'>{f['check']}  ·  severity {sev}{det}</span>",
                    unsafe_allow_html=True)
        st.write(f.get("detail", ""))
        if f.get("uncertain") and f.get("what_is_uncertain"):
            st.warning(f"The tool is not confident here, please check it yourself: "
                       f"{f['what_is_uncertain']}")
        if f.get("liveness"):
            st.markdown(f"<span class='small'><b>Still binding?</b> {f['liveness']} — "
                        f"{f.get('liveness_detail','')}</span>", unsafe_allow_html=True)
        if f.get("quote"):
            st.markdown(f"> {f['quote']}")
        if f.get("source_file"):
            st.markdown(f"<span class='small'><b>Taken from:</b> {f['source_file']}"
                        + (f" · clause {f['source_clause']}" if f.get("source_clause") else "")
                        + (f" · {f.get('citation')}" if f.get("citation") else "") + "</span>",
                        unsafe_allow_html=True)
        if f.get("waiver"):
            w = f["waiver"]
            (st.info if w["covers_this_deal"] else st.error)(w["text"])
            if w.get("quote"):
                st.markdown(f"> {w['quote']}")

# ------------------------------------------------------- considered & cleared
st.markdown("#### Considered and cleared")
st.caption("What the tool checked and ruled out, including promises that have already expired. "
           "Shown rather than hidden, because seeing what was ruled out is how you know it looked.")
for c in out["cleared"]:
    st.markdown(f"- **{c['commitment_id']} · {c['counterparty']}** "
                f"({c['type'].replace('_',' ')}) — *{c['status']}*. {c['detail']}")

# -------------------------------------------------------------- the manifest
with st.expander("Which checks ran"):
    labels = {"ran": "RAN", "not_applicable": "NOT APPLICABLE", "could_not_run": "COULD NOT RUN"}
    for name, m in out["manifest"].items():
        state = labels.get(m.get("status", "could_not_run"), "COULD NOT RUN")
        extra = m.get("detail") or m.get("remedy") or m.get("reason") or m.get("mode") or ""
        st.markdown(f"- **{name}** — {state}. {extra}")
    if out["dropped"]:
        st.markdown("**Findings deleted because their quote could not be verified:**")
        for d in out["dropped"]:
            st.markdown(f"- {d.get('title')} — {d.get('drop_reason')}")
    else:
        st.markdown("_Nothing was deleted: every quote was matched word for word against its "
                    "source file._")

st.divider()
st.caption(out["disclaimer"])
