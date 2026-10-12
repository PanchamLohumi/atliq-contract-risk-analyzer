"""Model access. The PRD names capabilities, not models: the model is an
engineering choice and is configurable here. Everything degrades gracefully if
no key is present, because a brief that silently drops a check is worse than one
that says the check did not run."""
import os, json, re

# Preference order by capability, not a hardcoded list. The actual model is
# discovered from the account at runtime, so the app does not break when a
# provider retires a name. The PRD names capabilities; this is the one place
# that resolves them to a model.
PREFERRED = ["llama-3.3-70b", "llama-3.1-70b", "gpt-oss-120b", "gpt-oss-20b",
             "qwen", "llama-3.1-8b", "llama3-70b", "mixtral"]
_resolved = None


class LLMUnavailable(Exception):
    pass


def have_key() -> bool:
    return bool(os.getenv("GROQ_API_KEY", "").strip())


def _client():
    if not have_key():
        raise LLMUnavailable("No GROQ_API_KEY set")
    try:
        from groq import Groq
    except ImportError as e:
        raise LLMUnavailable("groq package not installed") from e
    return Groq(api_key=os.getenv("GROQ_API_KEY").strip())


def _extract_json(text: str):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i != -1], default=-1)
    if start == -1:
        raise ValueError("no JSON found in model output")
    depth, instr, esc, opener = 0, False, False, text[start]
    closer = "}" if opener == "{" else "]"
    for i in range(start, len(text)):
        ch = text[i]
        if esc:
            esc = False; continue
        if ch == "\\":
            esc = True; continue
        if ch == '"':
            instr = not instr; continue
        if instr:
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("unterminated JSON in model output")


def available_models():
    """Ask the account what it can actually use."""
    try:
        return sorted(m.id for m in _client().models.list().data)
    except Exception:
        return []


def resolve_models():
    """Return an ordered shortlist of real model ids for this account."""
    global _resolved
    if _resolved is not None:
        return _resolved
    forced = os.getenv("GROQ_MODEL", "").strip()
    if forced:
        _resolved = [forced]
        return _resolved
    avail = available_models()
    if not avail:
        _resolved = ["llama-3.3-70b-versatile"]  # last resort if listing fails
        return _resolved
    ordered, seen = [], set()
    for pref in PREFERRED:
        for m in avail:
            if pref in m.lower() and m not in seen and "whisper" not in m.lower() \
               and "tts" not in m.lower() and "guard" not in m.lower():
                ordered.append(m); seen.add(m)
    for m in avail:  # anything else, as a backstop
        if m not in seen and all(k not in m.lower() for k in ("whisper", "tts", "guard")):
            ordered.append(m)
    _resolved = ordered[:4]
    return _resolved


def ask_json(system: str, user: str, max_tokens: int = 1600):
    """Return parsed JSON from the model. Raises LLMUnavailable if it cannot run."""
    client = _client()
    last_err = None
    for model in resolve_models():
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                temperature=0,
                max_tokens=max_tokens,
            )
            return _extract_json(resp.choices[0].message.content), model
        except Exception as e:  # model missing, rate limited, bad JSON
            last_err = e
            continue
    raise LLMUnavailable(f"All candidate models failed. Last error: {last_err}")
