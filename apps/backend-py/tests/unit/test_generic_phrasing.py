"""
Unit tests for generic_phrasing.find_generic_phrases (generic-phrasing task).
"""

import pytest

from src.generation.generic_phrasing import (
    GENERIC_PHRASES,
    GROUP_FILLER,
    GROUP_OPENING,
    GROUP_SELF_DESCRIPTION,
    _build_matcher,
    all_phrases,
    count_words,
    find_generic_phrases,
)


class TestMatching:
    """Tests for which text counts as a stock phrase."""

    def test_finds_phrase_case_insensitive(self):
        """A phrase matches in any letter case."""
        result = find_generic_phrases("I Am Writing To Apply for the role.")
        assert [(h.phrase, h.group) for h in result.hits] == [
            ("i am writing to apply", GROUP_OPENING)
        ]

    def test_whole_words_only(self):
        """A phrase inside a longer word does not match."""
        result = find_generic_phrases(
            "Our synergyx tool, the delvers, and invaluables."
        )
        assert result.total == 0

    def test_space_and_hyphen_are_the_same(self):
        """'results driven' matches the phrase 'results-driven', and the reverse."""
        spaced = find_generic_phrases("A results driven and team-player engineer.")
        phrases = {h.phrase for h in spaced.hits}
        assert phrases == {"results-driven", "team player"}

    def test_curly_apostrophe(self):
        """A curly apostrophe matches a straight one in the phrase."""
        result = find_generic_phrases("In today’s fast-paced world.")
        assert [h.phrase for h in result.hits] == ["in today's fast-paced"]

    def test_overlap_counts_once(self):
        """Overlapping phrases count once: the longest phrase at a position wins."""
        result = find_generic_phrases("In today's fast-paced environment, we ship.")
        assert result.total == 1
        assert result.hits[0].phrase == "in today's fast-paced"

    def test_plain_text_has_no_hits(self):
        """A specific sentence has no stock phrase."""
        result = find_generic_phrases(
            "I cut the nightly ETL run from 40 to 12 minutes at Acme."
        )
        assert result.hits == ()
        assert result.total == 0


class TestCounts:
    """Tests for counts, order, and the rate per 100 words."""

    def test_counts_repeats_and_orders_by_count(self):
        """Hits are counted per phrase, most frequent first, then by phrase."""
        text = (
            "Moreover, I am a team player. Moreover, a team player. Furthermore, yes."
        )
        result = find_generic_phrases(text)
        assert [(h.phrase, h.count) for h in result.hits] == [
            ("moreover", 2),
            ("team player", 2),
            ("furthermore", 1),
        ]
        assert result.total == 5
        assert {h.group for h in result.hits} == {GROUP_FILLER, GROUP_SELF_DESCRIPTION}

    def test_per_100_words(self):
        """The rate is the total per 100 words, rounded to 2 decimals."""
        text = "Moreover " + " ".join(["word"] * 99)
        result = find_generic_phrases(text)
        assert result.word_count == 100
        assert result.per_100_words == 1.0

    @pytest.mark.parametrize("text", ["", "   ", None])
    def test_empty_text(self, text):
        """Empty text gives no hits and a rate of 0."""
        result = find_generic_phrases(text)
        assert (result.total, result.word_count, result.per_100_words) == (0, 0, 0.0)

    def test_count_words_keeps_hyphen_and_apostrophe_words(self):
        """'results-driven' and 'today's' are one word each."""
        assert count_words("A results-driven team, today's plan.") == 5


class TestPhraseList:
    """Tests for the phrase list itself."""

    def test_every_phrase_matches_itself(self):
        """Each phrase is found in a sentence that contains it."""
        for phrase in all_phrases():
            result = find_generic_phrases(f"Start. {phrase} end.")
            assert [h.phrase for h in result.hits] == [phrase], phrase

    def test_phrases_are_lowercase_and_unique(self):
        """The list has no uppercase and no duplicate phrase."""
        phrases = all_phrases()
        assert all(p == p.lower() for p in phrases)
        assert len(phrases) == len(set(phrases))
        assert set(GENERIC_PHRASES) >= {GROUP_OPENING, GROUP_FILLER}

    def test_rejects_bad_phrase_lists(self):
        """Uppercase phrases and phrases with the same words are rejected."""
        with pytest.raises(ValueError):
            _build_matcher({"g": ("Team Player",)})
        with pytest.raises(ValueError):
            _build_matcher({"a": ("hard-working",), "b": ("hard working",)})
