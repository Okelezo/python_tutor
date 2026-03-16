from __future__ import annotations

import json
import os
from pathlib import Path

from .models import Track


def content_root() -> Path:
    override = os.environ.get("PYTUTOR_CONTENT_ROOT")
    if override:
        return Path(override).expanduser().resolve()

    def find_from(start: Path) -> Path | None:
        start = start.resolve()
        for p in (start, *start.parents):
            candidate = p / "content"
            if (candidate / "tracks").exists():
                return candidate
        return None

    found = find_from(Path.cwd())
    if found is not None:
        return found

    found = find_from(Path(__file__).resolve())
    if found is not None:
        return found

    return Path.cwd() / "content"


def list_tracks() -> list[str]:
    tracks_dir = content_root() / "tracks"
    if not tracks_dir.exists():
        return []
    return sorted([p.stem for p in tracks_dir.glob("*.json")])


def load_track(track_id: str) -> Track:
    path = content_root() / "tracks" / f"{track_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return Track.model_validate(data)
