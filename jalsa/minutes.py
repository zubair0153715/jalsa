"""Jalsa core: transcript normalization + rule-based minutes.

Everything here is extractive and verbatim — the rule-based engine NEVER
invents decisions, owners, or deadlines. Lines are classified by cue phrases;
output quotes the user's own transcript. Works fully offline with no API key.

Supported input:
  - Plain text lines
  - "Speaker Name: text" speaker labels
  - "[00:05] Speaker: text" or "00:05 Speaker: text" timestamps
  - "SPEAKER 1: text" diarization labels
  - WebVTT / SRT subtitle files (timestamps + cues)
  - English, Roman-Urdu, Urdu (proper script), and code-switched mixes
"""
import re

# Timestamps like [00:05], 00:05, [1:02:33], 1:02:33, 00:05.123
_TS = re.compile(r"\[?\b(\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?)\]?\s*")
# "Name: text" speaker label (Unicode-aware; names may be in Urdu script)
_LABEL = re.compile(r"^\s*([\w\u0600-\u06FF][\w\u0600-\u06FF .'-]{0,40}?)\s*:\s*(.+)$")
# "SPEAKER 1" / "SPEAKER_02" diarization labels
_DIAR = re.compile(r"(?i)^\s*speaker[\s_-]*(\d+)\s*:?\s*(.*)$")
# WebVTT cue header like "00:00:05.000 --> 00:00:10.000"
_VTT_CUE = re.compile(r"\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?\s*-->")


def _strip_ts(line):
    """Remove a leading timestamp from a line. Returns (ts_or_None, rest)."""
    m = _TS.match(line)
    if m:
        return m.group(1), line[m.end():].strip()
    return None, line.strip()


def parse_transcript(text):
    """Parse raw transcript text into a list of (speaker, text) turns.

    Returns (turns, warnings). Consecutive lines from the same speaker are
    merged into one turn. Lines without a label continue the current speaker;
    leading unlabeled lines are attributed to 'Narrator'.
    """
    warnings = []
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    # Drop WebVTT headers and NOTE blocks; SRT/VTT cue timings are filtered below.
    lines = []
    for raw in text.split("\n"):
        s = raw.strip()
        if not s:
            continue
        if s.upper() == "WEBVTT" or s.upper().startswith("NOTE"):
            continue
        if _VTT_CUE.search(s):
            continue
        if re.fullmatch(r"\d+", s):  # SRT sequence numbers
            continue
        if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?(?:[,.]\d+)?", s):  # bare timestamps
            continue
        lines.append(s)
    turns = []
    cur_speaker, cur_text = None, []
    speaker_seen = set()

    def flush():
        nonlocal cur_speaker, cur_text
        if cur_text:
            spk = cur_speaker or "Narrator"
            if turns and turns[-1][0] == spk:
                turns[-1] = (spk, turns[-1][1] + " " + " ".join(cur_text))
            else:
                turns.append((spk, " ".join(cur_text)))
        cur_text = []

    for line in lines:
        _ts, rest = _strip_ts(line)
        m_diar = _DIAR.match(rest)
        m_label = _LABEL.match(rest) if not m_diar else None
        if m_diar:
            flush()
            num = m_diar.group(1).lstrip("0") or "0"
            cur_speaker = f"Speaker {num}"
            speaker_seen.add(cur_speaker)
            body = m_diar.group(2).strip()
            if body:
                cur_text.append(body)
        elif m_label and len(m_label.group(1).split()) <= 4:
            flush()
            cur_speaker = m_label.group(1).strip()
            speaker_seen.add(cur_speaker)
            cur_text.append(m_label.group(2).strip())
        else:
            cur_text.append(rest)
    flush()
    if not turns:
        return [], ["Transcript khaali hai — text paste karo ya file upload karo."]
    if not speaker_seen:
        warnings.append("Koi speaker label nahi mila — sab kuch 'Narrator' ke naam.")
    return turns, warnings


# Cue phrases for classification (English + Roman-Urdu + Urdu). All matching is
# case-insensitive; matching a cue only *selects* the verbatim line.
_ACTION_CUES = (
    r"will\b|shall\b|should\b|need to\b|needs to\b|must\b|going to\b|plan to\b|"
    r"action\b|todo\b|to-do\b|follow[ -]?up\b|assign\b|deadline\b|by (monday|tuesday|"
    r"wednesday|thursday|friday|saturday|sunday|tomorrow|next week|eod|cob|\d)\b|"
    r"decided to\b|agreed to\b|take care of\b|handle\b|owner\b|responsible\b|"
    r"karna hai|karni hai|karega|karegi|karenge|hoga|hogi|honge|"
    r"کرنا ہے|کرنی ہے|کرے گا|کرے گی|کریں گے|ہوگا|ہوگی|ذمہ دار|"
    r"فیصلہ|طے پایا"
)
_DECISION_CUES = (
    r"we decided|decided to|we agreed|agreed (on|that)|final decision|"
    r"conclusion is|we('ll| will) go with|let's go with|approved|finalized|"
    r"فیصلہ (ہوا|کیا|کر لیا)|طے پایا|اتفاق (ہوا|رائے)|منظور"
)
_QUESTION_CUES = (
    r"\?\s*$|^(what|why|how|when|where|who|which|can|could|should|is|are|do|does|"
    r"will|kya|kab|kaise|kyun|kahan|kon)\b.*\?\s*$|"
    r"^(kya|kab|kaise|kyun|kahan|kon)\b.*؟\s*$|؟\s*$"
)

_ACTION_RE = re.compile(_ACTION_CUES, re.IGNORECASE)
_DECISION_RE = re.compile(_DECISION_CUES, re.IGNORECASE)
_QUESTION_RE = re.compile(_QUESTION_CUES, re.IGNORECASE)


def _split_sentences(text):
    parts = re.split(r"(?<=[.!?؟])\s+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) >= 12]


def rule_based_minutes(transcript, title="", lang="en"):
    """Build structured minutes from a transcript — extractive only.

    Returns (minutes_dict, warnings, error). Every quoted string is verbatim
    from the input; nothing is invented.
    """
    title = (title or "").strip()[:200] or "Untitled meeting"
    turns, warnings = parse_transcript(transcript)
    if not turns:
        return None, warnings, warnings[0]

    full_text = " ".join(t for _s, t in turns)
    sentences = _split_sentences(full_text)
    words = len(full_text.split())
    speakers = []
    for s, _t in turns:
        if s not in speakers:
            speakers.append(s)

    # TL;DR: the longest sentences, in original order (extractive, verbatim)
    ranked = sorted(sentences, key=len, reverse=True)[:5]
    tldr = sorted(ranked, key=sentences.index)[:3]

    decisions, actions, questions, quotes = [], [], [], []
    seen = set()
    for speaker, text in turns:
        for sent in _split_sentences(text):
            key = sent.lower()
            if key in seen:
                continue
            seen.add(key)
            entry = {"speaker": speaker, "text": sent}
            if _QUESTION_RE.search(sent):
                questions.append(entry)
            elif _DECISION_RE.search(sent):
                decisions.append(entry)
            elif _ACTION_RE.search(sent):
                owner = speaker if speaker != "Narrator" else ""
                actions.append({"owner": owner, "task": sent, "deadline": ""})

    # Key quotes: longest non-question, non-action sentences, verbatim
    quote_pool = [s for s in sentences
                  if not _QUESTION_RE.search(s) and not _ACTION_RE.search(s)]
    quotes = [{"speaker": "", "text": s}
              for s in sorted(quote_pool, key=len, reverse=True)[:3]]

    minutes = {
        "title": title,
        "lang": lang if lang in ("en", "ur") else "en",
        "tldr": tldr,
        "decisions": decisions[:20],
        "actions": actions[:30],
        "questions": questions[:20],
        "quotes": quotes,
        "stats": {
            "turns": len(turns),
            "words": words,
            "speakers": speakers,
            "sentences": len(sentences),
        },
        "ai": False,
    }
    return minutes, warnings, None


def minutes_to_markdown(m):
    """Render a minutes dict as clean Markdown. Returns (filename-safe, text)."""
    L = []
    L.append(f"# {m['title']}")
    L.append("")
    st = m["stats"]
    L.append(f"*Speakers: {', '.join(st['speakers'])} · "
             f"{st['turns']} turns · {st['words']} words*")
    L.append("")
    L.append("## TL;DR")
    for s in m["tldr"]:
        L.append(f"- {s}")
    L.append("")
    L.append("## Decisions")
    if m["decisions"]:
        for d in m["decisions"]:
            L.append(f"- **{d['speaker']}:** {d['text']}")
    else:
        L.append("- _(none detected)_")
    L.append("")
    L.append("## Action items")
    if m["actions"]:
        for a in m["actions"]:
            owner = f"**{a['owner']}** — " if a["owner"] else ""
            dl = f" _(by {a['deadline']})_" if a["deadline"] else ""
            L.append(f"- [ ] {owner}{a['task']}{dl}")
    else:
        L.append("- _(none detected)_")
    L.append("")
    L.append("## Open questions")
    if m["questions"]:
        for q in m["questions"]:
            L.append(f"- **{q['speaker']}:** {q['text']}")
    else:
        L.append("- _(none detected)_")
    L.append("")
    L.append("## Key quotes")
    for q in m["quotes"]:
        L.append(f"> {q['text']}")
    L.append("")
    L.append("---")
    L.append("*Minutes generated by Jalsa (rule-based, extractive). "
             "AI draft ho to facts verify kar lena.*")
    return "\n".join(L)
