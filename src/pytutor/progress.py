from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _progress_path() -> Path:
    return Path.home() / ".pytutor" / "progress.json"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Progress:
    completed_exercises: set[str]

    @staticmethod
    def empty() -> "Progress":
        return Progress(completed_exercises=set())


def load_progress() -> Progress:
    path = _progress_path()
    if not path.exists():
        return Progress.empty()

    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    completed = set(data.get("completed_exercises", []))
    return Progress(completed_exercises=completed)


def save_progress(progress: Progress) -> None:
    path = _progress_path()
    _ensure_parent(path)
    payload = {"completed_exercises": sorted(progress.completed_exercises)}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def mark_completed(exercise_id: str) -> None:
    progress = load_progress()
    updated = Progress(completed_exercises=set(progress.completed_exercises) | {exercise_id})
    save_progress(updated)
