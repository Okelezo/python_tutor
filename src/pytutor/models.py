from __future__ import annotations

from pydantic import BaseModel, Field


class Exercise(BaseModel):
    id: str
    title: str
    prompt_md: str
    starter_code: str
    tests_code: str
    hints: list[str] = Field(default_factory=list)
    solution_code: str | None = None


class Lesson(BaseModel):
    id: str
    title: str
    content_md: str
    exercises: list[Exercise] = Field(default_factory=list)


class Track(BaseModel):
    id: str
    title: str
    level: str
    description: str
    lessons: list[Lesson]


class GradeResult(BaseModel):
    passed: bool
    output: str
    failed_test: str | None = None
