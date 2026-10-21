"""
Load labeled evaluation cases and hash datasets (Step 3.1).

Cases are JSONL files: one JSON object per line, validated by a Pydantic
model. The dataset hash ignores line endings, so a Windows checkout and a
Linux checkout of the same files give the same hash.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import List, Type, TypeVar

from pydantic import BaseModel, ValidationError

CaseT = TypeVar("CaseT", bound=BaseModel)


def load_jsonl(path: Path, model: Type[CaseT]) -> List[CaseT]:
    """
    Load and validate one case per non-blank line.

    Args:
        path: JSONL file.
        model: Pydantic model for one case.

    Returns:
        Validated cases in file order.

    Raises:
        ValueError: When a line is not valid JSON or fails validation. The
            message names the file and the line number.
    """
    cases: List[CaseT] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            cases.append(model.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ValueError(f"{path.name} line {number}: {exc}") from exc
    return cases


def dataset_sha256(*paths: Path) -> str:
    """
    SHA-256 of one or more dataset files, independent of line endings.

    Each file contributes its name and its content with CRLF changed to LF,
    in the given order.

    Args:
        *paths: Dataset files.

    Returns:
        Hex digest (64 characters).
    """
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


def text_sha256(*parts: str) -> str:
    """
    SHA-256 of text parts, for example the templates of a prompt.

    Parts are separated, so ``("a", "b")`` and ``("ab",)`` differ.

    Args:
        *parts: Text parts in order.

    Returns:
        Hex digest (64 characters).
    """
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()
