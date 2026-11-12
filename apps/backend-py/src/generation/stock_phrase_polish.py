"""
Job Raider - Stock Phrase Polish

Rewrites only the sentences of a cover letter that contain a stock phrase
(``generic_phrasing``), after the letter is written. One LLM call gets the
letter as context and a numbered list of the target sentences, each with only
the phrase it uses. Listing all stock phrases in the writer prompt made the
local model use more of them (generic-phrasing task, attempt 1), so this step
names only the phrases that the letter already has.

Each new sentence is checked before it replaces the old one: no stock phrase,
no number that the old sentence did not have, and not much longer. When a
check fails, the old sentence stays. A wrong answer format or an error keeps
the whole letter as it was written. A greeting joined to a sentence
("Dear team, I ...") is never sent and never changed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..llm.base import Message, MessageType
from ..llm.router import TaskType
from ..utils.logger import Components, get_logger
from .cover_letter_grounding import split_letter_sentences
from .generic_phrasing import GROUP_CLOSING, GROUP_OPENING, find_generic_phrases

MAX_SENTENCES = 5
POLISH_TEMPERATURE = 0.2
POLISH_MAX_TOKENS = 600
LENGTH_FACTOR = 1.5
LENGTH_SLACK_WORDS = 5

_GREETING = re.compile(r"^Dear [^,.!?]{1,60},\s*")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_ANSWER_LINE = re.compile(r"^\s*(\d+)\s*[.)]\s*(.+?)\s*$")

_SYSTEM_PROMPT = (
    "You edit cover letters. You rewrite single sentences so that they say the "
    "same thing in plain, specific words. You never add facts."
)

logger = get_logger(Components.GENERATION)


@dataclass(frozen=True)
class PolishResult:
    """
    The result of one polish step.

    Attributes:
        content: The letter after the step (the input when nothing changed).
        attempted: The number of sentences sent to the model.
        replaced: The number of sentences that were replaced.
    """

    content: str
    attempted: int
    replaced: int


def _skipped_groups(style: str) -> frozenset[str]:
    """
    The phrase groups that a letter style may use.

    Args:
        style: ``modern`` or ``classic``.

    Returns:
        The opening and closing groups for a classic letter, else no group.
    """
    if style == "classic":
        return frozenset({GROUP_OPENING, GROUP_CLOSING})
    return frozenset()


def _phrases_in(text: str, skipped: frozenset[str]) -> List[str]:
    """
    The stock phrases in a text, without the skipped groups.

    Args:
        text: A sentence or a letter.
        skipped: Groups to ignore.

    Returns:
        The phrases found, each once, most frequent first.
    """
    return [
        hit.phrase
        for hit in find_generic_phrases(text).hits
        if hit.group not in skipped
    ]


def _targets(content: str, style: str) -> List[Tuple[str, List[str]]]:
    """
    Pick the sentences to rewrite.

    Args:
        content: The letter.
        style: ``modern`` or ``classic``.

    Returns:
        Up to ``MAX_SENTENCES`` entries: the sentence text (without a joined
        greeting) and the stock phrases in it.
    """
    skipped = _skipped_groups(style)
    targets: List[Tuple[str, List[str]]] = []
    for sentence in split_letter_sentences(content):
        body = _GREETING.sub("", sentence, count=1)
        phrases = _phrases_in(body, skipped)
        if phrases:
            targets.append((body, phrases))
        if len(targets) == MAX_SENTENCES:
            break
    return targets


def _build_messages(
    content: str, targets: List[Tuple[str, List[str]]]
) -> List[Message]:
    """
    Build the polish prompt.

    Args:
        content: The letter, given as context.
        targets: The sentences to rewrite, from ``_targets``.

    Returns:
        The system and user messages.
    """
    lines = "\n".join(
        f"{i}. {body}\n   Stock phrase to remove: "
        + ", ".join(f"'{p}'" for p in phrases)
        for i, (body, phrases) in enumerate(targets, start=1)
    )
    user = (
        "COVER LETTER (context only):\n"
        f"{content}\n\n"
        "SENTENCES TO REWRITE:\n"
        f"{lines}\n\n"
        "Rewrite each numbered sentence without its stock phrase. Keep the same "
        "meaning. Use only facts that are already in the letter. Do not add new "
        "facts, numbers, technologies, names, or claims. Do not make the "
        "sentence longer than it needs to be.\n"
        f"Answer with exactly {len(targets)} lines, in the form '1. new sentence'. "
        "Write nothing else."
    )
    return [
        Message(role=MessageType.SYSTEM, content=_SYSTEM_PROMPT),
        Message(role=MessageType.USER, content=user),
    ]


def _parse_answer(text: str, count: int) -> Optional[List[str]]:
    """
    Read the numbered sentences from the model's answer.

    Args:
        text: The model's answer.
        count: The number of sentences asked for.

    Returns:
        The new sentences in order, or None when the answer does not have
        exactly the numbers 1 to ``count``, each once.
    """
    found: Dict[int, str] = {}
    for line in (text or "").splitlines():
        match = _ANSWER_LINE.match(line)
        if not match:
            continue
        number = int(match.group(1))
        if number in found:
            return None
        found[number] = match.group(2).strip().strip('"').strip()
    if sorted(found) != list(range(1, count + 1)):
        return None
    return [found[i] for i in range(1, count + 1)]


def accept_sentence(old: str, new: str, skipped: frozenset[str] = frozenset()) -> bool:
    """
    Decide whether a rewritten sentence may replace the old one.

    Args:
        old: The sentence from the letter.
        new: The rewritten sentence.
        skipped: Phrase groups the letter style may use.

    Returns:
        True when the new sentence is not empty, has no stock phrase, has no
        number that the old sentence did not have, and has at most
        ``LENGTH_FACTOR`` times the old word count plus ``LENGTH_SLACK_WORDS``.
    """
    if not new.strip():
        return False
    if _phrases_in(new, skipped):
        return False
    if not set(_NUMBER.findall(new)) <= set(_NUMBER.findall(old)):
        return False
    return len(new.split()) <= LENGTH_FACTOR * len(old.split()) + LENGTH_SLACK_WORDS


def _replace_once(content: str, old: str, new: str) -> Tuple[str, bool]:
    """
    Replace the first occurrence of a sentence, with any whitespace between words.

    Args:
        content: The letter.
        old: The sentence to replace (whitespace may differ from the letter).
        new: The replacement.

    Returns:
        The new letter, and whether the sentence was found.
    """
    pattern = r"\s+".join(re.escape(word) for word in old.split())
    updated, count = re.subn(pattern, lambda _: new, content, count=1)
    return updated, bool(count)


def polish_stock_phrases(
    router: Any, content: str, style: str = "modern", model: Optional[str] = None
) -> PolishResult:
    """
    Rewrite the sentences of a letter that contain a stock phrase.

    Args:
        router: The LLM router (``generate`` on the cover-letter route).
        content: The letter as written.
        style: ``modern`` or ``classic``; classic keeps a traditional opening
            and closing.
        model: Optional writer model override, as for the letter.

    Returns:
        The letter after the step, with the counts of sentences sent and
        replaced. The input letter comes back on any error.
    """
    targets = _targets(content, style)
    if not targets:
        return PolishResult(content=content, attempted=0, replaced=0)
    try:
        response = router.generate(
            messages=_build_messages(content, targets),
            task_type=TaskType.COVER_LETTER_WRITING,
            model=model,
            temperature=POLISH_TEMPERATURE,
            max_tokens=POLISH_MAX_TOKENS,
            think=False,
        )
        answers = _parse_answer(getattr(response, "content", ""), len(targets))
    except Exception as exc:  # noqa: BLE001 - keep the letter as written
        logger.warning("Stock phrase polish failed: %s", type(exc).__name__)
        return PolishResult(content=content, attempted=len(targets), replaced=0)
    if answers is None:
        logger.info("Stock phrase polish: answer format not usable, letter kept")
        return PolishResult(content=content, attempted=len(targets), replaced=0)

    skipped = _skipped_groups(style)
    replaced = 0
    for (body, _phrases), new in zip(targets, answers):
        if not accept_sentence(body, new, skipped):
            continue
        content, found = _replace_once(content, body, new)
        replaced += int(found)
    logger.info(
        "Stock phrase polish: %d of %d sentences replaced", replaced, len(targets)
    )
    return PolishResult(content=content, attempted=len(targets), replaced=replaced)
