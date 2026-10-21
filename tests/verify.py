"""Jalsa verification: transcript parsing + rule-based minutes logic.

The rule-based engine is extractive — every test asserts it never invents
content (outputs must be verbatim substrings of the input) and that
classification hits the expected lines.

Run: ~/workspace/.venv-fc/bin/python tests/verify.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jalsa import minutes as m
from jalsa import gemini

PASS = []


def check(name, cond, detail=""):
    PASS.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name +
          (f" — {detail}" if detail and not cond else ""))


SAMPLE = """Ali: Assalam-o-Alaikum everyone, chalo aaj ka agenda shuru karte hain.
Sara: Design finalize ho gaya hai, lekin payment page par abhi testing baqi hai.
Ali: Testing kab tak complete hogi?
Sara: I will finish payment testing by Friday.
Zubair: We decided to launch on 15th March.
Ali: Budget approve ho gaya?
Zubair: Haan, budget approved hai.
Sara: Marketing ka plan ready hai, launch ke liye sab tayyar hai."""

# 1. speaker parsing
turns, w = m.parse_transcript("Ali: hello there")
check("label parse", turns == [("Ali", "hello there")], str(turns))
turns, w = m.parse_transcript("[00:05] Sara: hi there")
check("timestamp+label parse", turns == [("Sara", "hi there")], str(turns))
turns, w = m.parse_transcript("00:05 Sara: hi there")
check("bare timestamp parse", turns == [("Sara", "hi there")], str(turns))
turns, w = m.parse_transcript("SPEAKER 1: hello\nSPEAKER 1: again")
check("diarization merged", turns == [("Speaker 1", "hello again")], str(turns))
turns, w = m.parse_transcript("just some words\nmore words")
check("unlabeled -> Narrator", turns[0][0] == "Narrator", str(turns))
turns, w = m.parse_transcript("علی: ہم فیصلہ کرتے ہیں کہ launch hoga")
check("Urdu label parse", turns[0][0] == "علی", str(turns))
vtt = "WEBVTT\n\n00:00:05.000 --> 00:00:10.000\nAli: hello\n\n00:00:10.000 --> 00:00:12.000\nSara: hi"
turns, w = m.parse_transcript(vtt)
check("VTT cues filtered", turns == [("Ali", "hello"), ("Sara", "hi")], str(turns))
turns, w = m.parse_transcript("   \n  ")
check("empty -> warning", turns == [] and len(w) == 1, str(w))
turns, w = m.parse_transcript("Ali: one\nSara: two\nAli: three")
check("speaker switch keeps turns", len(turns) == 3, str(turns))

# 2. rule-based minutes: classification
mins, warns, err = m.rule_based_minutes(SAMPLE, "Test meeting")
check("minutes built", mins is not None and err is None, str(err))
check("action detected w/ owner",
      any(a["owner"] == "Sara" and "payment testing by Friday" in a["task"]
          for a in mins["actions"]),
      str(mins["actions"]))
check("decision detected",
      any("decided to launch on 15th March" in d["text"] for d in mins["decisions"]),
      str(mins["decisions"]))
check("question detected",
      any("Budget approve ho gaya" in q["text"] for q in mins["questions"]),
      str(mins["questions"]))
full = " ".join(t for _s, t in m.parse_transcript(SAMPLE)[0])
check("tldr verbatim (no invention)",
      all(s in full for s in mins["tldr"]) and len(mins["tldr"]) >= 1,
      str(mins["tldr"]))
check("quotes verbatim",
      all(q["text"] in full for q in mins["quotes"]), str(mins["quotes"]))
check("decisions/actions/questions verbatim",
      all(d["text"] in full for d in mins["decisions"]) and
      all(a["task"] in full for a in mins["actions"]) and
      all(q["text"] in full for q in mins["questions"]))
check("stats sane",
      mins["stats"]["speakers"] == ["Ali", "Sara", "Zubair"] and
      mins["stats"]["turns"] == 8 and mins["stats"]["words"] > 40,
      str(mins["stats"]))
check("ai flag false for rule-based", mins["ai"] is False)
mins2, _w2, err2 = m.rule_based_minutes("   ", "X")
check("empty transcript -> honest error", mins2 is None and err2, str(err2))
big = "Ali: " + "word " * 20000  # ~100k chars — no 30-minute-style cut-off
mins3, _w3, err3 = m.rule_based_minutes(big, "Long")
check("long transcript accepted (no cap)", mins3 is not None and err3 is None,
      str(err3))

# 3. markdown export
md = m.minutes_to_markdown(mins)
check("md has title", md.startswith("# Test meeting"))
check("md sections", all(s in md for s in
      ["## TL;DR", "## Decisions", "## Action items", "## Open questions",
       "## Key quotes"]))
check("md action checkboxes", "- [ ] **Sara** —" in md, md[:400])
check("md verbatim content", "decided to launch on 15th March" in md)
check("md no branding", "Otter" not in md and "Made with" not in md)
check("md speaker line", "Speakers: Ali, Sara, Zubair" in md)

# 4. gemini module: honest offline behavior on the VM (no key here)
check("key_available False on VM", gemini.key_available() is False)
_data, err = gemini._call("hello")
check("no-key call -> honest error",
      _data is None and "GEMINI_API_KEY" in (err or ""), str(err))
_m, _w, err = gemini.generate_minutes("", "T")
check("empty transcript rejected by AI path", err is not None)
_a, err = gemini.ask("", "kya hua?")
check("chat needs transcript", err is not None)
_a, err = gemini.ask("Ali: hello", "")
check("chat needs question", err is not None)
chunks = gemini._chunk("a\n" * 30000, limit=5000)
check("chunking splits long input", len(chunks) > 1, str(len(chunks)))
merged = gemini._merge_minutes([
    {"tldr": ["x"], "decisions": [], "actions": [], "questions": [], "quotes": []},
    {"tldr": ["x", "y"], "decisions": [], "actions": [], "questions": [], "quotes": []}])
check("merge dedupes", merged["tldr"] == ["x", "y"], str(merged["tldr"]))

# 5. routes import (needs fastapi — the deploy env)
try:
    from jalsa import routes  # noqa
    check("routes import", True)
    paths = sorted({r.path for r in routes.router.routes})
    check("routes registered",
          "/jalsa/api/minutes" in paths and "/jalsa/api/chat" in paths and
          "/jalsa/api/download-md" in paths and "/jalsa/api/ai-status" in paths,
          str(paths))
    check("MAX_INPUT no 30-min cut", routes.MAX_INPUT >= 100_000,
          str(routes.MAX_INPUT))
except Exception as e:
    check("routes import", False, repr(e)[:120])

failed = [n for n, ok, _d in PASS if not ok]
print(f"\n{len(PASS)-len(failed)}/{len(PASS)} checks passed")
sys.exit(1 if failed else 0)
