"""Jalsa — free AI meeting notes: transcript in, minutes out.

Original clean-room build. Not affiliated with Otter.ai or any other
meeting-notes tool. Transcripts stay in the user's browser unless AI is used;
the server stores nothing and trains on nothing.
"""
import logging
import re

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel

from . import gemini
from . import minutes as minutesmod
from .pages import JALSA_HTML

log = logging.getLogger("jalsa.routes")
router = APIRouter(prefix="/jalsa")

MAX_INPUT = 500_000  # ~a full day of meetings; never a 30-minute cut-off


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def page():
    return HTMLResponse(JALSA_HTML)


@router.get("/api/ai-status")
def api_ai_status():
    return JSONResponse({"ai_available": gemini.key_available()})


class MinutesIn(BaseModel):
    title: str = ""
    transcript: str = ""
    lang: str = "en"
    use_ai: bool = True


@router.post("/api/minutes")
def api_minutes(body: MinutesIn):
    transcript = (body.transcript or "").strip()
    if not transcript:
        return JSONResponse(
            {"error": "Transcript khaali hai — text paste karo ya file upload karo."},
            status_code=400)
    if len(transcript) > MAX_INPUT:
        return JSONResponse(
            {"error": f"Transcript bohat lamba hai ({len(transcript)} chars, "
                      f"limit {MAX_INPUT}). Chhota karke dobara try karo."},
            status_code=400)
    lang = body.lang if body.lang in ("en", "ur") else "en"
    if body.use_ai and gemini.key_available():
        m, warnings, err = gemini.generate_minutes(transcript, body.title, lang)
        if err:
            # Honest fallback: rule-based minutes still delivered.
            rb, w2, _e2 = minutesmod.rule_based_minutes(transcript, body.title, lang)
            if rb is None:
                return JSONResponse({"error": err}, status_code=200)
            w2.append(f"AI unavailable ({err})")
            return JSONResponse({"minutes": rb, "warnings": w2, "ai": False})
        return JSONResponse({"minutes": m, "warnings": warnings, "ai": True})
    m, warnings, err = minutesmod.rule_based_minutes(transcript, body.title, lang)
    if err:
        return JSONResponse({"error": err}, status_code=400)
    return JSONResponse({"minutes": m, "warnings": warnings, "ai": False})


class ChatIn(BaseModel):
    transcript: str = ""
    question: str = ""
    lang: str = "en"


@router.post("/api/chat")
def api_chat(body: ChatIn):
    lang = body.lang if body.lang in ("en", "ur") else "en"
    if not gemini.key_available():
        return JSONResponse(
            {"error": "AI chat ke liye GEMINI_API_KEY set nahi hai."},
            status_code=200)
    answer, err = gemini.ask(body.transcript, body.question, lang)
    if err:
        return JSONResponse({"error": err}, status_code=200)
    return JSONResponse({"answer": answer})


class MdIn(BaseModel):
    minutes: dict = {}


@router.post("/api/download-md")
def api_download_md(body: MdIn):
    m = body.minutes or {}
    required = ("title", "tldr", "decisions", "actions", "questions",
                "quotes", "stats")
    if not all(k in m for k in required):
        return JSONResponse({"error": "Minutes data incomplete hai."},
                            status_code=400)
    try:
        text = minutesmod.minutes_to_markdown(m)
    except Exception:
        log.exception("markdown build failed")
        return JSONResponse({"error": "Markdown banane mein masla."},
                            status_code=500)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", m["title"]).strip("-")[:60] or "jalsa-minutes"
    return Response(
        content=text.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe}.md"'},
    )
