from __future__ import annotations

import textwrap

import typer
from rich.console import Console
from rich.markdown import Markdown

from .content import list_tracks, load_track
from .engine import grade_submission
from .progress import load_progress, mark_completed

app = typer.Typer(no_args_is_help=True)
track_app = typer.Typer(no_args_is_help=True)
app.add_typer(track_app, name="track")

console = Console()


@track_app.command("list")
def track_list() -> None:
    tracks = list_tracks()
    if not tracks:
        console.print("No tracks found.")
        raise typer.Exit(1)
    for t in tracks:
        console.print(t)


@track_app.command("start")
def track_start(track_id: str) -> None:
    track = load_track(track_id)
    progress = load_progress()

    console.print(Markdown(f"# {track.title}\n\n{track.description}"))

    for lesson in track.lessons:
        console.print(Markdown(f"\n## {lesson.title}\n\n{lesson.content_md}"))

        for ex in lesson.exercises:
            console.print(Markdown(f"\n### Exercise: {ex.title}\n\n{ex.prompt_md}"))

            if ex.id in progress.completed_exercises:
                console.print("Already completed.")
                continue

            console.print("\nStarter code:\n")
            console.print(textwrap.indent(ex.starter_code.rstrip() + "\n", "    "))
            console.print("Paste your solution. End with a single line containing only 'EOF'.")

            lines: list[str] = []
            while True:
                line = input()
                if line.strip() == "EOF":
                    break
                lines.append(line)

            user_code = "\n".join(lines).strip() or ex.starter_code
            result = grade_submission(user_code=user_code, tests_code=ex.tests_code)

            if result.passed:
                console.print("Passed.")
                mark_completed(ex.id)
            else:
                console.print("Not yet.")

            if result.output.strip():
                console.print("\nOutput:\n")
                console.print(textwrap.indent(result.output.rstrip() + "\n", "    "))

    console.print("\nTrack complete.")
