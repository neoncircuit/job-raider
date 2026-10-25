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
        "You must pay $380 to start working",
        "Pay the $90 kit to start working tonight",
        "You pay a deposit to start working from home",
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
        "Starter kit\n- You must buy equipment from our vendor before day one",
        "Responsibilities\n- Answer calls from customers\n- Process orders in our system\n- Log each call in the sheet\n- You must buy the equipment from our approved vendor first",
        "What you do\n* Open the shop\n* Count the till\n* Buy the equipment from the named shop",
        "Day-one list\n1. Collect the badge\n2. Buy equipment at the stall we name",
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
        "Telegram: @hr_desk_sg",
        "Add me on Telegram, handle hrfast",
    ],
    "whatsapp": [
        "WhatsApp the manager to start.",
        "Apply on WhatsApp only.",
        "Text the hiring desk on WhatsApp.",
        "Interested candidates pls WhatsApp 9123 4567",
        "WhatsApp: +65 8123 4567 for details",
        "Kindly reach out to our HR on WhatsApp",
        "WhatsApp - 65-9123-0000 after lunch",
    ],
    "signal": [
        "Contact us on Signal tonight.",
        "We hire only through Signal.",
        "Send the signed form on Signal.",
        "Reach our desk on Signal tonight",
        "Signal +1-415-555-0199 after 6pm",
    ],
    "kik": [
        "Message the recruiter on Kik.",
        "Kik us your availability tonight.",
        "Apply via Kik and wait for the kit list.",
        "Add me on Kik after you send the form",
        "Kik: user_id 44921",
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
        "IMMEDIATE HIRING for warehouse packers, apply now",
        "Immediate hiring! Start this week",
        "We are immediately hiring store clerks this weekend",
    ],
    "start.*today": [
        "Start today after you message us.",
        "You can start today from home.",
        "Pay the fee and start today.",
        "Starting today, slots are limited",
        "Starting today if you message the desk",
    ],
    "no.*interview": [
        "No interview required, start tomorrow.",
        "No interview, we hire from the form.",
        "There is no interview for this role.",
        "No interviews needed, just send your IC",
        "no interview required, start tomorrow",
        "No interviews whatsoever, send the form tonight",
    ],
    "skip.*interview": [
        "Skip the interview and begin today.",
        "You may skip interview and start.",
        "We skip interview for remote clerks.",
        "Skip interviews and fill the seat tonight",
        "You can skip interviews after the form",
    ],
    "bitcoin": [
        "Pay the deposit in bitcoin.",
        "Send bitcoin to this wallet.",
        "Fees are in bitcoin only.",
        "Your first pay comes in bitcoin to a wallet we set up",
    ],
    "gift cards": [
        "Buy gift cards and send the codes.",
        "Pay with gift cards from the store.",
        "We accept gift cards as the starter fee.",
        "Buy Google Play gift cards and keep the receipt",
        "Purchase two $100 Steam gift cards for the client",
        "Buy three $50 iTunes gift cards and photo the backs",
        "Purchase a pair of $200 App Store gift cards before the call",
    ],
}

# Must-match phrases that fail on the current code (FR1 run).
MUST_MATCH_XFAIL: Dict[Tuple[str, str], str] = {
    ("pay.*to.*work", "You must pay $380 to start working"): "B1 fix round: class 3",
    (
        "pay.*to.*work",
        "Pay the $90 kit to start working tonight",
    ): "B1 fix round: class 3",
    (
        "pay.*to.*work",
        "You pay a deposit to start working from home",
    ): "B1 fix round: class 3",
    (
        "buy.*equipment",
        "Responsibilities\n- Answer calls from customers\n- Process orders in our system\n- Log each call in the sheet\n- You must buy the equipment from our approved vendor first",
    ): "B1 fix round: class 4",
    ("telegram", "Telegram: @hr_desk_sg"): "B1 fix round: class 2",
    (
        "whatsapp",
        "Interested candidates pls WhatsApp 9123 4567",
    ): "B1 fix round: class 2",
    ("whatsapp", "WhatsApp: +65 8123 4567 for details"): "B1 fix round: class 2",
    ("whatsapp", "WhatsApp - 65-9123-0000 after lunch"): "B1 fix round: class 2",
    ("signal", "Signal +1-415-555-0199 after 6pm"): "B1 fix round: class 2",
    (
        "immediate.*hire",
        "IMMEDIATE HIRING for warehouse packers, apply now",
    ): "B1 fix round: class 1",
    ("immediate.*hire", "Immediate hiring! Start this week"): "B1 fix round: class 1",
    (
        "immediate.*hire",
        "We are immediately hiring store clerks this weekend",
    ): "B1 fix round: class 1",
    ("start.*today", "Starting today, slots are limited"): "B1 fix round: class 1",
    (
        "start.*today",
        "Starting today if you message the desk",
    ): "B1 fix round: class 1",
    (
        "no.*interview",
        "No interviews needed, just send your IC",
    ): "B1 fix round: class 1",
    (
        "no.*interview",
        "No interviews whatsoever, send the form tonight",
    ): "B1 fix round: class 1",
    (
        "skip.*interview",
        "Skip interviews and fill the seat tonight",
    ): "B1 fix round: class 1",
    (
        "skip.*interview",
        "You can skip interviews after the form",
    ): "B1 fix round: class 1",
    (
        "gift cards",
        "Buy Google Play gift cards and keep the receipt",
    ): "B1 fix round: class 5",
    (
        "gift cards",
        "Purchase two $100 Steam gift cards for the client",
    ): "B1 fix round: class 5",
    (
        "gift cards",
        "Buy three $50 iTunes gift cards and photo the backs",
    ): "B1 fix round: class 5",
    (
        "gift cards",
        "Purchase a pair of $200 App Store gift cards before the call",
    ): "B1 fix round: class 5",
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
        ("We never ask you to pay to start work", "B1 fix round: class 6"),
        ("Pay is weekly. You start working after the walk-through.", None),
        ("At no point do we ask you to pay to start work", "B1 fix round: class 6"),
        ("No candidate is asked to pay to start work", "B1 fix round: class 6"),
    ],
    "payment.*required": [
        (
            "Payment is monthly. Overtime is required on weekends.",
            "R3 payment.*required",
        ),
        ("Direct deposit is the usual payment method.", None),
        ("Required documents are a resume and a work permit.", None),
        ("Payment terms: net 30. A degree is required.", "P1"),
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
        (
            "Kit list\n- The shop will buy from our store\n- Equipment arrives on day one",
            "B1 fix round: class 4",
        ),
        (
            "Onboarding\n* We never ask you to buy equipment\n* The bench is already stocked",
            None,
        ),
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
        ("You will work on Telegram bots for our customers", "B1 fix round: class 6"),
        ("Build chat features on Telegram for shops", "B1 fix round: class 6"),
    ],
    "whatsapp": [
        ("WhatsApp Business API", "R3 whatsapp"),
        ("The team ships a WhatsApp Business API connector.", "R3 whatsapp"),
        ("Call the duty phone during office hours.", None),
        (
            "Build chat features on WhatsApp and Messenger for retail clients",
            "B1 fix round: class 6",
        ),
        ("You will work on WhatsApp stickers for the brand", "B1 fix round: class 6"),
    ],
    "signal": [
        ("signal processing", "R3 signal"),
        ("We measure the signal-to-noise of the radar feed.", "R3 signal"),
        ("The radio desk handles inbound calls.", None),
        ("A paper or a thesis on signal processing is useful", "B1 fix round: class 6"),
        (
            "Experience on signal integrity for high-speed boards",
            "B1 fix round: class 6",
        ),
        ("Experience on signal chains for radio benches", "B1 fix round: class 6"),
        ("We ship a Signal Desktop plugin for support teams", None),
    ],
    "kik": [
        ("The Nairobi desk needs a Kikuyu speaker.", "R3 kik"),
        ("The fabric is a cotton kikoi wrap for the shop floor.", "R3 kik"),
        ("Email the recruiter your availability.", None),
        (
            "The Kik Messenger SDK is used in the consumer app",
            "B1 fix round: class 6",
        ),
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
        ("Hiring is done after two on-site interviews", None),
    ],
    "start.*today": [
        (
            "Applications start on Monday. Today the team is in the office.",
            "R3 start.*today",
        ),
        ("The start date is the first Monday of next month.", None),
        ("Today the warehouse runs a safety drill.", None),
        ("Today the clerk starts the safety walk after the offer", None),
    ],
    "no.*interview": [
        (
            "No travel is needed. Interviews are on site.",
            "R3 no.*interview",
        ),
        ("Interviews are on site.", None),
        ("The first meeting is a site walk.", None),
        (
            "There is no interview fee; interviews are free and on site",
            "B1 fix round: class 6",
        ),
        (
            "We know interviews can be stressful, so we share the questions",
            "P1",
        ),
        ("There is no interview cost; the panel is free", "B1 fix round: class 6"),
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
        ("Our team builds wallets for bitcoin and ether", "P1"),
    ],
    "gift cards": [
        (
            "never asks a candidate to pay a fee, buy equipment, or send gift cards",
            "R3 gift cards",
        ),
        ("Staff may receive gift cards at the year-end party.", "R3 gift cards"),
        ("We reimburse approved tool purchases.", None),
        ("Staff get gift cards at the year-end party", "P1"),
        ("We will never ask you to purchase gift cards", None),
        ("The cafe sells gift cards at the counter for birthdays", None),
    ],
}


def _live_pattern(key: str) -> str:
    """
    Return the production pattern that now stands in for a B1a key.

    Args:
        key: Original B1a pattern string.

    Returns:
        The live regex or reject pattern.
    """
    grouped = JobScamDetector.SUSPICIOUS_PATTERNS
    detector_keys = [
        pattern for pattern, source in LISTED_PATTERNS if source == "detector"
    ]
    order = {
        "payment": detector_keys[:6],
        "messaging": detector_keys[6:12],
        "immediate": detector_keys[12:16],
    }
    for group, keys in order.items():
        if key in keys:
            return grouped[group][keys.index(key)]
    reject_keys = [pattern for pattern, source in LISTED_PATTERNS if source == "reject"]
    if key in reject_keys:
        for pattern in ScamFilter.REJECT_PATTERNS:
            token = key.split()[0]
            if pattern == key or token in pattern:
                return pattern
    raise KeyError(key)


def _pattern_hits(pattern: str, source: str, text: str) -> bool:
    """
    Return whether ``pattern`` hits ``text`` the same way production does.

    Args:
        pattern: B1a key; the live production pattern is used.
        source: ``detector`` or ``reject``.
        text: Phrase or short posting.

    Returns:
        True when the current production check would fire.
    """
    live = _live_pattern(pattern)
    if source == "reject":
        return ScamFilter.reject_pattern_hits(live, text)
    return re.search(live, text, flags=re.IGNORECASE) is not None


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
            xfail_reason = MUST_MATCH_XFAIL.get((pattern, phrase))
            marks = (
                [pytest.mark.xfail(strict=True, reason=xfail_reason)]
                if xfail_reason
                else []
            )
            for layout, text in (
                ("alone", phrase),
                ("posting", _wrap_in_posting(phrase)),
            ):
                rows.append(
                    pytest.param(
                        pattern,
                        source,
                        text,
                        marks=marks,
                        id=f"{pattern}::match::{index}::{layout}",
                    )
                )
    return rows


def _must_not_params() -> List[Any]:
    """
    Build must-not cases for each pattern and each layout.

    Returns:
        Pytest parameters.
    """
    rows: List[Any] = []
    for pattern, phrases in MUST_NOT.items():
        source = _source_for(pattern)
        for index, (phrase, reason) in enumerate(phrases):
            marks = (
                [pytest.mark.xfail(strict=True, reason=reason)]
                if reason and reason.startswith("B1 fix round")
                else []
            )
            for layout, text in (
                ("alone", phrase),
                ("posting", _wrap_in_posting(phrase)),
            ):
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
        """Each detector slot on the B1 list still has a live pattern."""
        listed = [
            pattern for pattern, source in LISTED_PATTERNS if source == "detector"
        ]
        for key in listed:
            live = _live_pattern(key)
            token = key.split("*")[0].rstrip(".")
            assert token in live.replace(r"\b", "").lower()

    def test_reject_list_contains_each_substring(self) -> None:
        """Each reject slot on the B1 list still has a live pattern."""
        listed = [pattern for pattern, source in LISTED_PATTERNS if source == "reject"]
        for key in listed:
            live = _live_pattern(key)
            assert key.split()[0] in live.lower()

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
