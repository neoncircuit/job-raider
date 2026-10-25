"""
Phrase tests for the R3 patterns on ``JobScamDetector`` and ``ScamFilter``.

Each listed pattern has at least three must-match phrases (real scam wording)
and at least three must-not phrases (ordinary posting wording). Each phrase
is checked alone on one line and inside a short posting with line breaks.
The check uses the compiled pattern or the reject substring, not the full
``detect()`` score.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import pytest

from src.scoring.scam_detector import JobScamDetector, ScamFilter

# (pattern, source). source is "detector" or "reject".
LISTED_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("pay.*to.*work", "detector"),
    ("payment.*required", "detector"),
    ("buy.*equipment", "detector"),
    ("wire.*transfer", "detector"),
    ("cryptocurrency.*payment", "detector"),
    ("bitcoin.*required", "detector"),
    ("telegram", "detector"),
    ("whatsapp", "detector"),
    ("signal", "detector"),
    ("kik", "detector"),
    ("discord.*only", "detector"),
    ("text.*only", "detector"),
    ("immediate.*hire", "detector"),
    ("start.*today", "detector"),
    ("no.*interview", "detector"),
    ("skip.*interview", "detector"),
    ("bitcoin", "reject"),
    ("gift cards", "reject"),
)

# Real scam wording that the current patterns must still catch.
MUST_MATCH: Dict[str, List[str]] = {
    "pay.*to.*work": [
        "Pay $50 to start work this week.",
        "You pay a small fee to work from home.",
        "Pay the kit cost to work with us.",
    ],
    "payment.*required": [
        "A training payment is required before day one.",
        "Payment required to receive the laptop.",
        "An upfront payment is required for the starter pack.",
    ],
    "buy.*equipment": [
        "Buy the equipment from our vendor before you start.",
        "You must buy equipment from the list we send.",
        "Candidates buy equipment and send the receipt.",
    ],
    "wire.*transfer": [
        "Send a wire transfer to hold the seat.",
        "We ask for a wire transfer of $200.",
        "Complete the wire transfer to unlock training.",
    ],
    "cryptocurrency.*payment": [
        "Compensation is a cryptocurrency payment each Friday.",
        "Send a cryptocurrency payment to confirm the seat.",
        "We use a cryptocurrency payment for the deposit.",
    ],
    "bitcoin.*required": [
        "A bitcoin deposit is required.",
        "Bitcoin is required to unlock the portal.",
        "A small bitcoin payment is required first.",
    ],
    "telegram": [
        "Message us on Telegram to begin.",
        "Apply only through Telegram.",
        "Send your CV on Telegram @hiredesk.",
    ],
    "whatsapp": [
        "WhatsApp the manager to start.",
        "Apply on WhatsApp only.",
        "Text the hiring desk on WhatsApp.",
    ],
    "signal": [
        "Contact us on Signal tonight.",
        "We hire only through Signal.",
        "Send the signed form on Signal.",
    ],
    "kik": [
        "Message the recruiter on Kik.",
        "Kik us your availability tonight.",
        "Apply via Kik and wait for the kit list.",
    ],
    "discord.*only": [
        "Discord only for all hiring chat.",
        "We use Discord only, no email.",
        "Contact is Discord only after you pay.",
    ],
    "text.*only": [
        "Text only, do not call the office.",
        "Apply by text only to this number.",
        "This role is text only from the first day.",
    ],
    "immediate.*hire": [
        "Immediate hire, start this week.",
        "This is an immediate hire role.",
        "Immediate hire after you pay the fee.",
    ],
    "start.*today": [
        "Start today after you message us.",
        "You can start today from home.",
        "Pay the fee and start today.",
    ],
    "no.*interview": [
        "No interview required, start tomorrow.",
        "No interview, we hire from the form.",
        "There is no interview for this role.",
    ],
    "skip.*interview": [
        "Skip the interview and begin today.",
        "You may skip interview and start.",
        "We skip interview for remote clerks.",
    ],
    "bitcoin": [
        "Pay the deposit in bitcoin.",
        "Send bitcoin to this wallet.",
        "Fees are in bitcoin only.",
    ],
    "gift cards": [
        "Buy gift cards and send the codes.",
        "Pay with gift cards from the store.",
        "We accept gift cards as the starter fee.",
    ],
}

# Ordinary posting wording. xfail_reason is set when the current code matches.
# reason None means the current code already leaves the phrase alone.
MUST_NOT: Dict[str, List[Tuple[str, Optional[str]]]] = {
    "pay.*to.*work": [
        (
            "competitive pay and the chance to work on the night radar",
            "R3 pay.*to.*work",
        ),
        (
            "Pay is monthly. You get the chance to work on the quay chart.",
            "R3 pay.*to.*work",
        ),
        ("The role pays a monthly salary for office work.", None),
    ],
    "payment.*required": [
        (
            "Payment is monthly. Overtime is required on weekends.",
            "R3 payment.*required",
        ),
        ("Direct deposit is the usual payment method.", None),
        ("Required documents are a resume and a work permit.", None),
    ],
    "buy.*equipment": [
        (
            "never asks a candidate to pay a fee, buy equipment, or send gift cards",
            "R3 buy.*equipment",
        ),
        (
            "You may buy from our store. Equipment is supplied on day one.",
            "R3 buy.*equipment",
        ),
        ("The company supplies all tools on day one.", None),
    ],
    "wire.*transfer": [
        (
            "We send the first week by wire. Transfer of knowledge starts in week two.",
            "R3 wire.*transfer",
        ),
        ("Payroll lands in your bank account each Friday.", None),
        ("A transfer window of two weeks applies to this desk.", None),
    ],
    "cryptocurrency.*payment": [
        (
            "We accept no cryptocurrency. Payment is by bank transfer.",
            "R3 cryptocurrency.*payment",
        ),
        ("Salary is paid in Singapore dollars.", None),
        ("A research paper on cryptocurrency is not part of the work.", None),
    ],
    "bitcoin.*required": [
        (
            "We do not use bitcoin. Experience is required.",
            "R3 bitcoin.*required",
        ),
        ("No digital-asset deposit is asked of staff.", None),
        ("Required experience is five years in payments.", None),
    ],
    "telegram": [
        ("We publish product alerts on the Telegram Bot API.", "R3 telegram"),
        ("Staff read the public Telegram channel for store hours.", "R3 telegram"),
        ("Write to the hiring desk at careers@example.com.", None),
    ],
    "whatsapp": [
        ("WhatsApp Business API", "R3 whatsapp"),
        ("The team ships a WhatsApp Business API connector.", "R3 whatsapp"),
        ("Call the duty phone during office hours.", None),
    ],
    "signal": [
        ("signal processing", "R3 signal"),
        ("We measure the signal-to-noise of the radar feed.", "R3 signal"),
        ("The radio desk handles inbound calls.", None),
    ],
    "kik": [
        ("The Nairobi desk needs a Kikuyu speaker.", "R3 kik"),
        ("The fabric is a cotton kikoi wrap for the shop floor.", "R3 kik"),
        ("Email the recruiter your availability.", None),
    ],
    "discord.*only": [
        (
            "Join our Discord. Only full-time roles are listed.",
            "R3 discord.*only",
        ),
        ("Team chat is on the company intranet.", None),
        ("The handbook is the only source for leave rules.", None),
    ],
    "text.*only": [
        (
            "The job text is on the site. Only applicants with a portfolio need apply.",
            "R3 text.*only",
        ),
        ("Apply on the company website.", None),
        ("The only interview is a desk walk-through.", None),
    ],
    "immediate.*hire": [
        (
            "We have an immediate need. Hire decisions come after two interviews.",
            "R3 immediate.*hire",
        ),
        ("We fill the seat after two interviews.", None),
        ("An immediate start is possible after the offer letter.", None),
    ],
    "start.*today": [
        (
            "Applications start on Monday. Today the team is in the office.",
            "R3 start.*today",
        ),
        ("The start date is the first Monday of next month.", None),
        ("Today the warehouse runs a safety drill.", None),
    ],
    "no.*interview": [
        (
            "No travel is needed. Interviews are on site.",
            "R3 no.*interview",
        ),
        ("Interviews are on site.", None),
        ("The first meeting is a site walk.", None),
    ],
    "skip.*interview": [
        (
            "You may skip the online form. Interviews are required.",
            "R3 skip.*interview",
        ),
        ("Every shortlisted person attends an interview.", None),
        ("Do not skip the safety briefing.", None),
    ],
    "bitcoin": [
        ("a licensed bitcoin exchange", "R3 bitcoin"),
        ("The treasury team watches bitcoin prices for a research note.", "R3 bitcoin"),
        ("Salary is paid in Singapore dollars.", None),
    ],
    "gift cards": [
        (
            "never asks a candidate to pay a fee, buy equipment, or send gift cards",
            "R3 gift cards",
        ),
        ("Staff may receive gift cards at the year-end party.", "R3 gift cards"),
        ("We reimburse approved tool purchases.", None),
    ],
}


def _pattern_hits(pattern: str, source: str, text: str) -> bool:
    """
    Return whether ``pattern`` hits ``text`` the same way production does.

    Args:
        pattern: Detector regex or reject substring.
        source: ``detector`` or ``reject``.
        text: Phrase or short posting.

    Returns:
        True when the current production check would fire.
    """
    if source == "reject":
        return pattern.lower() in text.lower()
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _wrap_in_posting(phrase: str) -> str:
    """
    Place ``phrase`` inside a short posting that uses line breaks.

    Args:
        phrase: The phrase under test.

    Returns:
        A four-line posting.
    """
    return (
        "Harbour clerk\n"
        "Keep the quay chart current.\n"
        f"{phrase}\n"
        "Send the form through the company site."
    )


def _source_for(pattern: str) -> str:
    """
    Return the production source of a listed pattern.

    Args:
        pattern: Pattern string.

    Returns:
        ``detector`` or ``reject``.
    """
    for listed, source in LISTED_PATTERNS:
        if listed == pattern:
            return source
    raise KeyError(pattern)


def _match_params() -> List[Any]:
    """
    Build must-match cases for each pattern and each layout.

    Returns:
        Pytest parameters.
    """
    rows: List[pytest.ParameterSet] = []
    for pattern, phrases in MUST_MATCH.items():
        source = _source_for(pattern)
        for index, phrase in enumerate(phrases):
            for layout, text in (
                ("alone", phrase),
                ("posting", _wrap_in_posting(phrase)),
            ):
                rows.append(
                    pytest.param(
                        pattern,
                        source,
                        text,
                        id=f"{pattern}::match::{index}::{layout}",
                    )
                )
    return rows


def _must_not_params() -> List[Any]:
    """
    Build must-not cases, with a strict xfail when the current code hits.

    Returns:
        Pytest parameters.
    """
    rows: List[pytest.ParameterSet] = []
    for pattern, phrases in MUST_NOT.items():
        source = _source_for(pattern)
        for index, (phrase, reason) in enumerate(phrases):
            for layout, text in (
                ("alone", phrase),
                ("posting", _wrap_in_posting(phrase)),
            ):
                marks = ()
                if reason:
                    marks = (pytest.mark.xfail(strict=True, reason=reason),)
                rows.append(
                    pytest.param(
                        pattern,
                        source,
                        text,
                        marks=marks,
                        id=f"{pattern}::not::{index}::{layout}",
                    )
                )
    return rows


class TestListedPatternsExist:
    """The B1 list is present on the detector and the filter."""

    def test_detector_list_contains_each_regex(self) -> None:
        """Each detector pattern on the B1 list is in ``SUSPICIOUS_PATTERNS``."""
        listed = {
            pattern for pattern, source in LISTED_PATTERNS if source == "detector"
        }
        found = {
            pattern
            for patterns in JobScamDetector.SUSPICIOUS_PATTERNS.values()
            for pattern in patterns
        }
        assert listed <= found

    def test_reject_list_contains_each_substring(self) -> None:
        """Each reject substring on the B1 list is in ``REJECT_PATTERNS``."""
        listed = {pattern for pattern, source in LISTED_PATTERNS if source == "reject"}
        assert listed <= set(ScamFilter.REJECT_PATTERNS)

    def test_each_pattern_has_three_phrases_each_way(self) -> None:
        """Every listed pattern has at least three must-match and must-not phrases."""
        listed = {pattern for pattern, _source in LISTED_PATTERNS}
        assert set(MUST_MATCH) == listed
        assert set(MUST_NOT) == listed
        for pattern in listed:
            assert len(MUST_MATCH[pattern]) >= 3
            assert len(MUST_NOT[pattern]) >= 3


class TestMustMatchPhrases:
    """Scam wording that B1 must keep."""

    @pytest.mark.parametrize("pattern,source,text", _match_params())
    def test_must_match_hits(self, pattern: str, source: str, text: str) -> None:
        """
        A must-match phrase hits the listed pattern.

        Args:
            pattern: Detector regex or reject substring.
            source: ``detector`` or ``reject``.
            text: Phrase alone or inside a short posting.
        """
        assert _pattern_hits(pattern, source, text) is True


class TestMustNotPhrases:
    """Ordinary wording that B1 must stop matching."""

    @pytest.mark.parametrize("pattern,source,text", _must_not_params())
    def test_must_not_misses(self, pattern: str, source: str, text: str) -> None:
        """
        A must-not phrase does not hit the listed pattern.

        Args:
            pattern: Detector regex or reject substring.
            source: ``detector`` or ``reject``.
            text: Phrase alone or inside a short posting.
        """
        assert _pattern_hits(pattern, source, text) is False
