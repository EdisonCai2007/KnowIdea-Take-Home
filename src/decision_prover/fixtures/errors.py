from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pydantic import ValidationError


def format_location(location: tuple[object, ...]) -> str:
    parts: list[str] = []
    for item in location:
        if isinstance(item, int):
            parts.append(f"[{item}]")
        else:
            if parts and not parts[-1].endswith("]"):
                parts.append(".")
            elif parts and parts[-1].endswith("]"):
                parts.append(".")
            parts.append(str(item))

    location_text = "".join(parts)
    return location_text or "<root>"


def format_validation_errors(source_path: Path, error: ValidationError) -> list[str]:
    problems: list[str] = []
    for item in error.errors():
        location = format_location(tuple(item.get("loc", ())))
        message = item.get("msg", "validation error")
        problems.append(f"{source_path}:{location}: {message}")
    return problems


@dataclass(slots=True)
class FixtureLoadError(Exception):
    source_path: Path
    problems: tuple[str, ...]

    def __init__(self, source_path: Path, problems: Iterable[str]):
        self.source_path = source_path
        self.problems = tuple(problems)
        Exception.__init__(self, self.__str__())

    def __str__(self) -> str:
        return "\n".join(self.problems)
