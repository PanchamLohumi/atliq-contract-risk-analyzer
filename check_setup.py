"""Run this first: python check_setup.py
Confirms Python, packages, data files and the Groq key before you touch the app."""
import sys, os
ok = True
print(f"Python {sys.version.split()[0]}")
if sys.version_info >= (3, 13):
    print("  ! Python 3.13+ is very new. If pip install failed, use Python 3.11 or 3.12.")
for mod in ("streamlit", "groq", "pypdf", "docx"):
    try:
        __import__(mod); print(f"  ok   {mod}")
    except ImportError:
        print(f"  MISSING  {mod}  -> pip install -r requirements.txt"); ok = False
from pathlib import Path
for f in ("app.py", "data/commitments_register.json", "data/playbook.json",
          "data/entities.json", "data/signed", "data/samples", "evals/eval_set.json"):
    p = Path(f)
    print(("  ok   " if p.exists() else "  MISSING  ") + f)
    ok &= p.exists()
key = os.getenv("GROQ_API_KEY", "").strip()
if not key:
    key = input("\nPaste your Groq API key to test it (or press Enter to skip): ").strip()
if key:
    os.environ["GROQ_API_KEY"] = key
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from engine import llm
    models = llm.available_models()
    if not models:
        print("\n  COULD NOT REACH GROQ. Check the key and your network.")
        ok = False
    else:
        print(f"\n  Key works. {len(models)} models available.")
        print("  Will use, in order:", ", ".join(llm.resolve_models()))
        try:
            out, used = llm.ask_json("Return only JSON.", 'Return {"status":"ok"}', 60)
            print(f"  Live call succeeded on {used}: {out}")
        except Exception as e:
            print(f"  Live call FAILED: {str(e)[:200]}"); ok = False
print("\n" + ("ALL GOOD - run: streamlit run app.py" if ok else "FIX THE ITEMS ABOVE FIRST"))
