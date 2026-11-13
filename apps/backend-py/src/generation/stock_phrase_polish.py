"""
Job Raider - Stock Phrase Polish

Rewrites only the sentences that contain a stock phrase (``generic_phrasing``),
after a cover letter or a CV is written. One LLM call gets the document as
context and a numbered list of the target sentences, each with only the phrase
it uses. Listing all stock phrases in the writer prompt made the local model
use more of them (generic-phrasing task, attempt 1), so this step names only
the phrases that the document already has.

Each new sentence is checked before it replaces the old one: no stock phrase,
no number that the old sentence did not have, and not much longer. When a
check fails, the old sentence stays. A wrong answer format or an error keeps
the whole document as it was written. A greeting joined to a sentence
("Dear team, I ...") is never sent and never changed.

The core works on a list of texts: a letter is one text; a CV is its prose
fields (summary, bullets, project descriptions). Each accepted sentence goes
back into its own text. Skill names, titles, companies, and dates of a CV are
never sent.
"""

from __future__ import annotations

import copy
import dataclasses
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

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


@dataclass(frozen=True)
class _Document:
    """
    The words that name the document in the polish prompt.

    Attributes:
        plural: The documents the editor edits (system prompt).
        label: The context heading.
        noun: The document in the instructions.
    """

    plural: str
    label: str
    noun: str


_LETTER = _Document(plural="cover letters", label="COVER LETTER", noun="letter")
_CV = _Document(plural="CVs", label="CV", noun="CV")

# One target: the index of its text, the sentence (without a joined
# greeting), and the stock phrases in it.
_Target = Tuple[int, str, List[str]]


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
        text: A sentence or a document.
        skipped: Groups to ignore.

    Returns:
        The phrases found, each once, most frequent first.
    """
    return [
        hit.phrase
        for hit in find_generic_phrases(text).hits
        if hit.group not in skipped
    ]


def _targets(texts: Sequence[str], skipped: frozenset[str]) -> List[_Target]:
    """
    Pick the sentences to rewrite, over all texts in order.

    Args:
        texts: The texts of the document.
        skipped: Phrase groups the document may use.

    Returns:
        Up to ``MAX_SENTENCES`` targets.
    """
    targets: List[_Target] = []
    for index, text in enumerate(texts):
        for sentence in split_letter_sentences(text):
            body = _GREETING.sub("", sentence, count=1)
            phrases = _phrases_in(body, skipped)
            if phrases:
                targets.append((index, body, phrases))
            if len(targets) == MAX_SENTENCES:
                return targets
    return targets


def _build_messages(
    context: str, targets: List[_Target], document: _Document
) -> List[Message]:
    """
    Build the polish prompt.

    Args:
        context: The document, given as context.
        targets: The sentences to rewrite, from ``_targets``.
        document: The words that name the document.

    Returns:
        The system and user messages.
    """
    system = (
        f"You edit {document.plural}. You rewrite single sentences so that they "
        "say the same thing in plain, specific words. You never add facts."
    )
    lines = "\n".join(
        f"{i}. {body}\n   Stock phrase to remove: "
        + ", ".join(f"'{p}'" for p in phrases)
        for i, (_, body, phrases) in enumerate(targets, start=1)
    )
    user = (
        f"{document.label} (context only):\n"
        f"{context}\n\n"
        "SENTENCES TO REWRITE:\n"
        f"{lines}\n\n"
        "Rewrite each numbered sentence without its stock phrase. Keep the same "
        f"meaning. Use only facts that are already in the {document.noun}. Do not "
        "add new facts, numbers, technologies, names, or claims. Do not make the "
        "sentence longer than it needs to be.\n"
        f"Answer with exactly {len(targets)} lines, in the form '1. new sentence'. "
        "Write nothing else."
    )
    return [
        Message(role=MessageType.SYSTEM, content=system),
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
        old: The sentence from the document.
        new: The rewritten sentence.
        skipped: Phrase groups the document may use.

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
        content: The text.
        old: The sentence to replace (whitespace may differ from the text).
        new: The replacement.

    Returns:
        The new text, and whether the sentence was found.
    """
    pattern = r"\s+".join(re.escape(word) for word in old.split())
    updated, count = re.subn(pattern, lambda _: new, content, count=1)
    return updated, bool(count)


def _polish_texts(
    router: Any,
    texts: Sequence[str],
    *,
    context: str,
    task_type: TaskType,
    document: _Document,
    skipped: frozenset[str] = frozenset(),
    model: Optional[str] = None,
) -> Tuple[List[str], int, int]:
    """
    Rewrite the sentences with stock phrases across a list of texts.

    Args:
        router: The LLM router.
        texts: The texts of the document.
        context: The whole document, given to the model as context.
        task_type: The route to call.
        document: The words that name the document in the prompt.
        skipped: Phrase groups the document may use.
        model: Optional model override.

    Returns:
        The texts after the step (the input texts on any error), the number
        of sentences sent, and the number replaced.
    """
    result = list(texts)
    targets = _targets(result, skipped)
    if not targets:
        return result, 0, 0
    try:
        response = router.generate(
            messages=_build_messages(context, targets, document),
            task_type=task_type,
            model=model,
            temperature=POLISH_TEMPERATURE,
            max_tokens=POLISH_MAX_TOKENS,
            think=False,
        )
        answers = _parse_answer(getattr(response, "content", ""), len(targets))
    except Exception as exc:  # noqa: BLE001 - keep the document as written
        logger.warning("Stock phrase polish failed: %s", type(exc).__name__)
        return result, len(targets), 0
    if answers is None:
        logger.info(
            "Stock phrase polish: answer format not usable, %s kept", document.noun
        )
        return result, len(targets), 0

    replaced = 0
    for (index, body, _phrases), new in zip(targets, answers):
        if not accept_sentence(body, new, skipped):
            continue
        result[index], found = _replace_once(result[index], body, new)
        replaced += int(found)
    logger.info(
        "Stock phrase polish (%s): %d of %d sentences replaced",
        document.noun,
        replaced,
        len(targets),
    )
    return result, len(targets), replaced


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
    texts, attempted, replaced = _polish_texts(
        router,
        [content],
        context=content,
        task_type=TaskType.COVER_LETTER_WRITING,
        document=_LETTER,
        skipped=_skipped_groups(style),
        model=model,
    )
    return PolishResult(content=texts[0], attempted=attempted, replaced=replaced)


def polish_resume_stock_phrases(
    router: Any, resume: Any, model: Optional[str] = None
) -> Tuple[Any, PolishResult]:
    """
    Rewrite the sentences of a CV's prose that contain a stock phrase.

    The prose fields are the summary, the experience highlights, and the
    project descriptions and highlights. Skill names, titles, companies, and
    dates are never sent or changed.

    Args:
        router: The LLM router (``generate`` on the ``resume_writing`` route).
        resume: A ``GeneratedResume`` (any dataclass with the same fields).
        model: Optional model override.

    Returns:
        A copy of the CV after the step (the same values when nothing
        changed), and the counts; ``PolishResult.content`` holds the prose
        after the step, one field per line.
    """
    holder: Dict[str, Any] = {"summary": resume.summary or ""}
    experience = copy.deepcopy(list(resume.experience))
    projects = copy.deepcopy(list(resume.projects))
    # Each prose field as (container, key): written back as container[key].
    slots: List[Tuple[Any, Any]] = [(holder, "summary")]
    for item in experience:
        slots.extend(
            (item["highlights"], i) for i in range(len(item.get("highlights") or []))
        )
    for item in projects:
        if item.get("description"):
            slots.append((item, "description"))
        slots.extend(
            (item["highlights"], i) for i in range(len(item.get("highlights") or []))
        )
    texts = [str(container[key]) for container, key in slots]

    new_texts, attempted, replaced = _polish_texts(
        router,
        texts,
        context="\n".join(text for text in texts if text),
        task_type=TaskType.RESUME_WRITING,
        document=_CV,
        model=model,
    )
    for (container, key), value in zip(slots, new_texts):
        container[key] = value
    updated = dataclasses.replace(
        resume,
        summary=holder["summary"],
        experience=experience,
        projects=projects,
    )
    outcome = PolishResult(
        content="\n".join(text for text in new_texts if text),
        attempted=attempted,
        replaced=replaced,
    )
    return updated, outcome
