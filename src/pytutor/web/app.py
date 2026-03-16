from __future__ import annotations

import json
import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import Body, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..content import list_tracks, load_track
from ..engine import grade_submission
from ..progress import load_progress, mark_completed
from .. import ai

load_dotenv()

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    tracks = [load_track(t) for t in list_tracks()]
    progress = load_progress()
    return templates.TemplateResponse(
        "home.html",
        {"request": request, "tracks": tracks, "completed": progress.completed_exercises},
    )


@app.get("/track/{track_id}", response_class=HTMLResponse)
def view_track(track_id: str, request: Request):
    track = load_track(track_id)
    progress = load_progress()
    return templates.TemplateResponse(
        "track.html",
        {"request": request, "track": track, "completed": progress.completed_exercises},
    )


@app.get("/track/{track_id}/exercise/{exercise_id}", response_class=HTMLResponse)
def view_exercise(track_id: str, exercise_id: str, request: Request):
    track = load_track(track_id)
    progress = load_progress()

    exercise = None
    lesson_title = None
    for lesson in track.lessons:
        for ex in lesson.exercises:
            if ex.id == exercise_id:
                exercise = ex
                lesson_title = lesson.title
                break

    if exercise is None:
        return HTMLResponse("Not found", status_code=404)

    exercise_data_json = json.dumps(
        {
            "trackId": track.id,
            "exerciseId": exercise.id,
            "starterCode": exercise.starter_code,
            "solutionCode": exercise.solution_code or "",
        }
    )

    return templates.TemplateResponse(
        "exercise.html",
        {
            "request": request,
            "track": track,
            "lesson_title": lesson_title,
            "exercise": exercise,
            "completed": progress.completed_exercises,
            "result": None,
            "code": exercise.starter_code,
            "exercise_data_json": exercise_data_json,
        },
    )


@app.post("/track/{track_id}/exercise/{exercise_id}", response_class=HTMLResponse)
def submit_exercise(track_id: str, exercise_id: str, request: Request, code: str = Form(...)):
    track = load_track(track_id)

    exercise = None
    lesson_title = None
    for lesson in track.lessons:
        for ex in lesson.exercises:
            if ex.id == exercise_id:
                exercise = ex
                lesson_title = lesson.title
                break

    if exercise is None:
        return HTMLResponse("Not found", status_code=404)

    exercise_data_json = json.dumps(
        {
            "trackId": track.id,
            "exerciseId": exercise.id,
            "starterCode": exercise.starter_code,
            "solutionCode": exercise.solution_code or "",
        }
    )

    result = grade_submission(user_code=code, tests_code=exercise.tests_code)
    if result.passed:
        mark_completed(exercise.id)

    progress = load_progress()
    return templates.TemplateResponse(
        "exercise.html",
        {
            "request": request,
            "track": track,
            "lesson_title": lesson_title,
            "exercise": exercise,
            "completed": progress.completed_exercises,
            "result": result,
            "code": code,
            "exercise_data_json": exercise_data_json,
        },
    )


@app.post("/track/{track_id}/exercise/{exercise_id}/reset")
def reset_exercise(track_id: str, exercise_id: str):
    return RedirectResponse(url=f"/track/{track_id}/exercise/{exercise_id}", status_code=303)


@app.post("/api/ai/hint")
def api_ai_hint(payload: dict = Body(...)):
    if not ai.ai_enabled():
        raise HTTPException(status_code=400, detail="AI is not configured. Set PYTUTOR_OPENAI_API_KEY.")

    track_id = str(payload.get("track_id") or "")
    exercise_id = str(payload.get("exercise_id") or "")
    code = str(payload.get("code") or "")

    track = load_track(track_id)
    exercise = None
    for lesson in track.lessons:
        for ex in lesson.exercises:
            if ex.id == exercise_id:
                exercise = ex
                break
    if exercise is None:
        raise HTTPException(status_code=404, detail="Exercise not found")

    text = ai.chat(ai.make_hint_prompt(exercise_title=exercise.title, prompt_md=exercise.prompt_md, code=code))
    return {"text": text}


@app.post("/api/ai/explain")
def api_ai_explain(payload: dict = Body(...)):
    if not ai.ai_enabled():
        raise HTTPException(status_code=400, detail="AI is not configured. Set PYTUTOR_OPENAI_API_KEY.")

    track_id = str(payload.get("track_id") or "")
    exercise_id = str(payload.get("exercise_id") or "")
    code = str(payload.get("code") or "")

    track = load_track(track_id)
    exercise = None
    for lesson in track.lessons:
        for ex in lesson.exercises:
            if ex.id == exercise_id:
                exercise = ex
                break
    if exercise is None:
        raise HTTPException(status_code=404, detail="Exercise not found")

    text = ai.chat(ai.make_explain_prompt(exercise_title=exercise.title, prompt_md=exercise.prompt_md, code=code))
    return {"text": text}


@app.post("/api/ai/review")
def api_ai_review(payload: dict = Body(...)):
    if not ai.ai_enabled():
        raise HTTPException(status_code=400, detail="AI is not configured. Set PYTUTOR_OPENAI_API_KEY.")

    track_id = str(payload.get("track_id") or "")
    exercise_id = str(payload.get("exercise_id") or "")
    code = str(payload.get("code") or "")

    track = load_track(track_id)
    exercise = None
    for lesson in track.lessons:
        for ex in lesson.exercises:
            if ex.id == exercise_id:
                exercise = ex
                break
    if exercise is None:
        raise HTTPException(status_code=404, detail="Exercise not found")

    text = ai.chat(ai.make_review_prompt(exercise_title=exercise.title, code=code))
    return {"text": text}


def main() -> None:
    host = os.environ.get("PYTUTOR_HOST") or os.environ.get("HOST") or "127.0.0.1"
    port_raw = os.environ.get("PYTUTOR_PORT") or os.environ.get("PORT") or "8010"
    try:
        port = int(port_raw)
    except ValueError:
        port = 8010
    uvicorn.run(app, host=host, port=port)
