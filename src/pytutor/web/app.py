from __future__ import annotations

import json
import os
import time
from base64 import b64decode
from pathlib import Path
from typing import Any

import uvicorn
from dotenv import load_dotenv
from fastapi import Body, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from ..content import list_tracks, load_track
from ..engine import grade_submission
from .. import ai
from .. import auth
from .. import db

load_dotenv()


class _BasicAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI):
        super().__init__(app)
        self._user = os.environ.get("PYTUTOR_BASIC_AUTH_USER") or ""
        self._pass = os.environ.get("PYTUTOR_BASIC_AUTH_PASS") or ""

    def _enabled(self) -> bool:
        return bool(self._user and self._pass)

    def _authorized(self, request: Request) -> bool:
        auth = request.headers.get("authorization") or ""
        if not auth.lower().startswith("basic "):
            return False
        try:
            raw = b64decode(auth.split(" ", 1)[1]).decode("utf-8")
            user, pw = raw.split(":", 1)
        except Exception:
            return False
        return user == self._user and pw == self._pass

    async def dispatch(self, request: Request, call_next):
        if not self._enabled():
            return await call_next(request)

        # Allow health checks if you ever add them.
        if self._authorized(request):
            return await call_next(request)

        return Response(
            status_code=401,
            headers={"WWW-Authenticate": "Basic realm=\"Python Tutor\""},
            content="Authentication required",
        )


class _RateLimiter:
    def __init__(self):
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = time.time()
        window_start = now - window_seconds
        bucket = self._hits.get(key, [])
        bucket = [t for t in bucket if t >= window_start]
        if len(bucket) >= limit:
            self._hits[key] = bucket
            return False
        bucket.append(now)
        self._hits[key] = bucket
        return True


_rate_limiter = _RateLimiter()

_conn = db.connect()
db.init_db(_conn)


def _current_user(request: Request) -> auth.User | None:
    token = request.cookies.get(auth.session_cookie_name())
    if not token:
        return None
    return auth.get_user_by_session(_conn, token=token)


def _require_user(request: Request) -> auth.User:
    user = _current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def _redirect_to_login(request: Request) -> RedirectResponse:
    return RedirectResponse(url="/auth/login", status_code=303)


app = FastAPI()
app.add_middleware(_BasicAuthMiddleware)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    user = _current_user(request)
    if user is None:
        return _redirect_to_login(request)
    tracks = [load_track(t) for t in list_tracks()]
    completed = auth.get_completed(_conn, user_id=user.id)
    return templates.TemplateResponse(
        "home.html",
        {"request": request, "tracks": tracks, "completed": completed, "user": user},
    )


@app.get("/track/{track_id}", response_class=HTMLResponse)
def view_track(track_id: str, request: Request):
    user = _current_user(request)
    if user is None:
        return _redirect_to_login(request)
    track = load_track(track_id)
    completed = auth.get_completed(_conn, user_id=user.id)
    return templates.TemplateResponse(
        "track.html",
        {"request": request, "track": track, "completed": completed, "user": user},
    )


@app.get("/track/{track_id}/exercise/{exercise_id}", response_class=HTMLResponse)
def view_exercise(track_id: str, exercise_id: str, request: Request):
    user = _current_user(request)
    if user is None:
        return _redirect_to_login(request)
    track = load_track(track_id)
    completed = auth.get_completed(_conn, user_id=user.id)

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
            "completed": completed,
            "result": None,
            "code": exercise.starter_code,
            "exercise_data_json": exercise_data_json,
            "user": user,
        },
    )


@app.post("/track/{track_id}/exercise/{exercise_id}", response_class=HTMLResponse)
def submit_exercise(track_id: str, exercise_id: str, request: Request, code: str = Form(...)):
    user = _current_user(request)
    if user is None:
        return _redirect_to_login(request)
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
        auth.mark_completed(_conn, user_id=user.id, exercise_id=exercise.id)

    completed = auth.get_completed(_conn, user_id=user.id)
    return templates.TemplateResponse(
        "exercise.html",
        {
            "request": request,
            "track": track,
            "lesson_title": lesson_title,
            "exercise": exercise,
            "completed": completed,
            "result": result,
            "code": code,
            "exercise_data_json": exercise_data_json,
            "user": user,
        },
    )


@app.post("/track/{track_id}/exercise/{exercise_id}/reset")
def reset_exercise(track_id: str, exercise_id: str):
    return RedirectResponse(url=f"/track/{track_id}/exercise/{exercise_id}", status_code=303)


@app.get("/auth/login", response_class=HTMLResponse)
def auth_login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/auth/login", response_class=HTMLResponse)
def auth_login_post(request: Request, email: str = Form(...), password: str = Form(...)):
    user = auth.authenticate(_conn, email=email, password=password)
    if user is None:
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Invalid email or password"}
        )

    token = auth.create_session(_conn, user_id=user.id)
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(
        auth.session_cookie_name(),
        token,
        httponly=True,
        samesite="lax",
        secure=bool(os.environ.get("PYTUTOR_COOKIE_SECURE") or ""),
    )
    return resp


@app.get("/auth/register", response_class=HTMLResponse)
def auth_register_get(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "error": None})


@app.post("/auth/register", response_class=HTMLResponse)
def auth_register_post(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        user = auth.create_user(_conn, email=email, password=password)
    except Exception:
        return templates.TemplateResponse(
            "register.html", {"request": request, "error": "Account already exists"}
        )

    token = auth.create_session(_conn, user_id=user.id)
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(
        auth.session_cookie_name(),
        token,
        httponly=True,
        samesite="lax",
        secure=bool(os.environ.get("PYTUTOR_COOKIE_SECURE") or ""),
    )
    return resp


@app.post("/auth/logout")
def auth_logout(request: Request):
    token = request.cookies.get(auth.session_cookie_name())
    if token:
        auth.delete_session(_conn, token=token)
    resp = RedirectResponse(url="/auth/login", status_code=303)
    resp.delete_cookie(auth.session_cookie_name())
    return resp


@app.post("/api/ai/hint")
def api_ai_hint(request: Request, payload: dict = Body(...)):
    user = _require_user(request)
    if not _rate_limiter.allow(f"ai:user:{user.id}", limit=30, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many AI requests. Try again in a minute.")

    api_key = request.headers.get("x-pytutor-openai-key")
    if not (api_key and api_key.strip()):
        raise HTTPException(status_code=400, detail="AI key missing. Add your OpenAI key in Settings.")

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

    text = ai.chat(
        ai.make_hint_prompt(exercise_title=exercise.title, prompt_md=exercise.prompt_md, code=code),
        api_key=api_key,
    )
    return {"text": text}


@app.post("/api/ai/explain")
def api_ai_explain(request: Request, payload: dict = Body(...)):
    user = _require_user(request)
    if not _rate_limiter.allow(f"ai:user:{user.id}", limit=30, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many AI requests. Try again in a minute.")

    api_key = request.headers.get("x-pytutor-openai-key")
    if not (api_key and api_key.strip()):
        raise HTTPException(status_code=400, detail="AI key missing. Add your OpenAI key in Settings.")

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

    text = ai.chat(
        ai.make_explain_prompt(exercise_title=exercise.title, prompt_md=exercise.prompt_md, code=code),
        api_key=api_key,
    )
    return {"text": text}


@app.post("/api/ai/review")
def api_ai_review(request: Request, payload: dict = Body(...)):
    user = _require_user(request)
    if not _rate_limiter.allow(f"ai:user:{user.id}", limit=30, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many AI requests. Try again in a minute.")

    api_key = request.headers.get("x-pytutor-openai-key")
    if not (api_key and api_key.strip()):
        raise HTTPException(status_code=400, detail="AI key missing. Add your OpenAI key in Settings.")

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

    text = ai.chat(ai.make_review_prompt(exercise_title=exercise.title, code=code), api_key=api_key)
    return {"text": text}


def main() -> None:
    host = os.environ.get("PYTUTOR_HOST") or os.environ.get("HOST") or "0.0.0.0"
    port_raw = os.environ.get("PYTUTOR_PORT") or os.environ.get("PORT") or "8010"
    try:
        port = int(port_raw)
    except ValueError:
        port = 8010
    uvicorn.run(app, host=host, port=port)
