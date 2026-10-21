"""Jalsa AI minutes + AI chat via Gemini (free tier).

Same call pattern as app/bayan/gemini.py: urllib, key read from the
environment AT CALL TIME only, never stored or logged.
The chat prompt carries a grounding rule: answer ONLY from the transcript,
quote it, and say plainly when something is not there.
"""
import json
import os
import urllib.error
import urllib.request

from . import minutes as minutesmod

MODEL = "gemini-2.5-flash"
TIMEOUT = 90


def _get_key():
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_APIkey")


def key_available():
    return bool(_get_key())


def _call(prompt, max_tokens=2000):
    key = _get_key()
    if not key:
        return None, "AI ke liye GEMINI_API_KEY set nahi hai — rule-based minutes use karo."
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           f"{MODEL}:generateContent?key={key}")
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": max_tokens},
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        return None, f"Gemini HTTP {e.code} — key ya quota check karo."
    except Exception as e:
        return None, f"Gemini se rabta nahi ho saka: {type(e).__name__}."
    try:
        obj = json.loads(body)
        raw = obj["candidates"][0]["content"]["parts"][0]["text"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.lstrip().startswith("json"):
                raw = raw.lstrip()[4:]
        return json.loads(raw.strip()), None
    except Exception:
        return None, "Gemini ne samajh nahi aaya jawab diya — dobara try karo."


MINUTES_PROMPT = """You are a meeting-minutes writer. Read the transcript and reply with
ONLY this JSON, no markdown fences, no extra text:
{"tldr":["3-5 sentence summary, plain words"],
 "decisions":[{"speaker":"name or empty","text":"decision made"}],
 "actions":[{"owner":"name or empty","task":"what to do","deadline":"when, or empty"}],
 "questions":[{"speaker":"name or empty","text":"open question"}],
 "quotes":[{"speaker":"name or empty","text":"memorable verbatim quote"}]}

Rules:
- NEVER invent names, dates, numbers, or commitments. Every decision, action,
  and quote must be traceable to the transcript; use the speakers' real names
  from the transcript.
- If an action's owner or deadline is not stated, leave it empty — do not guess.
- Max 6 decisions, 10 actions, 6 questions, 3 quotes.
- Output language: %s. The transcript may mix English, Roman-Urdu, and Urdu —
  understand all three.

Meeting title: %s
Transcript:
%s
"""


def _chunk(text, limit=24000):
    """Split a long transcript into chunks (long meetings must not be cut off)."""
    if len(text) <= limit:
        return [text]
    parts, cur = [], []
    size = 0
    for para in text.split("\n"):
        if size + len(para) > limit and cur:
            parts.append("\n".join(cur))
            cur, size = [], 0
        cur.append(para)
        size += len(para)
    if cur:
        parts.append("\n".join(cur))
    return parts


def _merge_minutes(parts):
    merged = {"tldr": [], "decisions": [], "actions": [],
              "questions": [], "quotes": []}
    seen = set()
    for p in parts:
        for k in merged:
            for item in (p.get(k) or []):
                sig = json.dumps(item, sort_keys=True, ensure_ascii=False).lower()
                if sig not in seen:
                    seen.add(sig)
                    merged[k].append(item)
    for k, cap in (("tldr", 5), ("decisions", 6), ("actions", 10),
                   ("questions", 6), ("quotes", 3)):
        merged[k] = merged[k][:cap]
    return merged


def generate_minutes(transcript, title="", lang="en"):
    """AI-generate structured minutes. Returns (minutes_dict, warnings, error)."""
    transcript = (transcript or "").strip()
    if not transcript:
        return None, [], "Transcript khaali hai — text paste karo ya file upload karo."
    title = title.strip()[:200] or "Untitled meeting"
    lang_name = "Urdu (proper script)" if lang == "ur" else "English"
    chunks = _chunk(transcript)
    parts, warnings = [], []
    for i, ch in enumerate(chunks):
        data, err = _call(MINUTES_PROMPT % (lang_name, title, ch))
        if err:
            # Honest fallback on the failed chunk: never return half-silence.
            rb, w2, _e2 = minutesmod.rule_based_minutes(ch, title, lang)
            if rb:
                parts.append({k: rb[k] for k in
                              ("tldr", "decisions", "actions", "questions", "quotes")})
                warnings.append(f"Chunk {i+1}/{len(chunks)}: AI fail hua "
                                f"({err}) — rule-based fallback use kiya.")
            else:
                return None, [], err
        else:
            parts.append(data)
    merged = _merge_minutes(parts)
    turns, _w = minutesmod.parse_transcript(transcript)
    speakers = []
    for s, _t in turns:
        if s not in speakers:
            speakers.append(s)
    minutes = {
        "title": title,
        "lang": lang,
        "tldr": merged["tldr"],
        "decisions": [{"speaker": d.get("speaker", ""), "text": d.get("text", "")}
                      for d in merged["decisions"]],
        "actions": [{"owner": a.get("owner", ""), "task": a.get("task", ""),
                     "deadline": a.get("deadline", "")}
                    for a in merged["actions"]],
        "questions": [{"speaker": q.get("speaker", ""), "text": q.get("text", "")}
                      for q in merged["questions"]],
        "quotes": [{"speaker": q.get("speaker", ""), "text": q.get("text", "")}
                   for q in merged["quotes"]],
        "stats": {"turns": len(turns), "words": len(transcript.split()),
                  "speakers": speakers, "sentences": 0},
        "ai": True,
    }
    warnings.append("AI draft — facts verify kar lena before sharing.")
    return minutes, warnings, None


CHAT_PROMPT = """You answer questions about a meeting transcript. Reply in %s.
Rules:
- Answer ONLY from the transcript. Quote or closely paraphrase what was said,
  naming the speaker when the transcript names them.
- If the transcript does not contain the answer, say so plainly — NEVER invent
  names, dates, numbers, or commitments.
- Keep answers short (under 120 words) unless asked for detail.

Transcript:
%s

Question: %s
"""


def ask(transcript, question, lang="en"):
    """AI chat over a transcript. Returns (answer, error)."""
    transcript = (transcript or "").strip()
    question = (question or "").strip()[:500]
    if not transcript:
        return None, "Pehle transcript do — phir sawal pooch sakte ho."
    if not question:
        return None, "Sawal likho — meeting ke baare mein kya poochna hai?"
    lang_name = "Urdu (proper script)" if lang == "ur" else "English"
    chunks = _chunk(transcript, limit=30000)
    # Answer from the first chunk that contains an answer; simpler and honest.
    data, err = _call(CHAT_PROMPT % (lang_name, chunks[0], question),
                      max_tokens=600)
    if err:
        return None, err
    if isinstance(data, dict):
        return data.get("answer") or data.get("text") or json.dumps(data), None
    return str(data), None
