# Jalsa (جلسہ) — free AI meeting notes

**Transcript in → meeting minutes out.** Free, unlimited, no per-meeting cut-off.

An original clean-room build. Not affiliated with Otter.ai or any other
meeting-notes product. Built as one of the daily gap-builds:
[gap report](../market-gaps/daily/2026-10-21-jalsa.md) (Otter.ai's public gaps).

## Why it exists (the gaps it fills)

Otter.ai's free plan (public pricing, Oct 2026): 300 min/month, a **30-minute
per-conversation cap** (an hour-long meeting is cut off mid-sentence), **3 file
imports lifetime**, and history auto-deleted beyond 25 transcripts. Accuracy
drops on non-native accents and code-switching (G2 reviews, 2026); it covers
~6 languages and **no Urdu**. The notes it generates need heavy post-editing,
and you "can't copy directly from the transcript" (G2).

Jalsa answers all three:
1. **Free, unlimited** — any transcript length, any number of meetings. No minute
   quota, no per-meeting cut-off. (Honest caveat: AI features run on the
   owner's free Gemini quota; the rule-based engine is always unlimited.)
2. **Urdu-first** — proper Urdu + Roman-Urdu + English + code-switching input;
   minutes in English or Urdu.
3. **Minutes you can ship** — TL;DR, decisions, action items (owner + deadline),
   open questions, key quotes — one-click copy per section, Markdown download,
   print. Plus AI chat over the transcript with a grounding rule: it quotes the
   transcript and says plainly when something isn't there.

## Privacy

Transcripts stay in your browser unless AI is used. The server stores nothing
and trains on nothing.

## Layout

- `jalsa/minutes.py` — transcript normalization, speaker parsing, extractive
  rule-based minutes (never invents content), Markdown export
- `jalsa/gemini.py` — AI minutes + AI chat (Gemini, key read at call time only)
- `jalsa/routes.py` — FastAPI router (`/jalsa`, `/api/minutes`, `/api/chat`,
  `/api/download-md`, `/api/ai-status`)
- `jalsa/pages.py` — single-page UI
- `tests/verify.py` — verification suite (run with the project's Python env)

## Run the checks

```bash
python tests/verify.py
```

## Deploy

This module ships as a route inside the host FastAPI app:

```python
from app.jalsa.routes import router as jalsa_router
app.include_router(jalsa_router)
```

## License

MIT — original code, no third-party assets.
