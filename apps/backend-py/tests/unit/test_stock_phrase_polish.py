"""
Unit tests for stock_phrase_polish (generic-phrasing task, attempt 2).
"""

from types import SimpleNamespace
from typing import Any, List, Optional, Union

from src.generation.stock_phrase_polish import (
    MAX_SENTENCES,
    accept_sentence,
    polish_stock_phrases,
)


class FakeRouter:
    """Returns prepared answers in order and records each call."""

    def __init__(self, answers: Optional[List[Union[str, Exception]]] = None) -> None:
        """
        Keep the answers.

        Args:
            answers: Answer texts, or exceptions to raise, one per call.
        """
        self.answers = list(answers or [])
        self.calls: List[dict] = []

    def generate(self, **kwargs: Any) -> Any:
        """
        Record the call and return the next answer.

        Args:
            **kwargs: The call's arguments.

        Returns:
            An object with ``content``.

        Raises:
            Exception: When the next answer is an exception.
        """
        self.calls.append(kwargs)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return SimpleNamespace(content=answer)

    def user_prompt(self) -> str:
        """
        The user message of the first call.

        Returns:
            Its text.
        """
        return self.calls[0]["messages"][1].content


LETTER = (
    "At Foo I cut API latency by 40%.\n\n"
    "Moreover, I mentored three engineers.\n\n"
    "I would welcome a conversation about the role."
)


class TestPolish:
    """Tests for polish_stock_phrases."""

    def test_no_stock_phrase_means_no_call(self):
        """A letter without stock phrases is returned unchanged, without a call."""
        router = FakeRouter()
        text = "At Foo I cut API latency by 40%.\n\nI would welcome a conversation."
        result = polish_stock_phrases(router, text)
        assert (result.content, result.attempted, result.replaced) == (text, 0, 0)
        assert router.calls == []

    def test_replaces_only_the_target_sentence(self):
        """The new sentence replaces the old one; other text and breaks stay."""
        router = FakeRouter(["1. I also mentored three engineers."])
        result = polish_stock_phrases(router, LETTER)
        assert result.content == (
            "At Foo I cut API latency by 40%.\n\n"
            "I also mentored three engineers.\n\n"
            "I would welcome a conversation about the role."
        )
        assert (result.attempted, result.replaced) == (1, 1)

    def test_prompt_names_only_the_phrases_found(self):
        """The prompt names the letter's phrase, not the rest of the list."""
        router = FakeRouter(["1. I also mentored three engineers."])
        polish_stock_phrases(router, LETTER)
        prompt = router.user_prompt()
        assert "Stock phrase to remove: 'moreover'" in prompt
        assert "team player" not in prompt
        assert router.calls[0]["temperature"] == 0.2

    def test_keeps_the_old_sentence_when_a_stock_phrase_remains(self):
        """A rewrite with another stock phrase is not used."""
        router = FakeRouter(["1. Furthermore, I mentored three engineers."])
        result = polish_stock_phrases(router, LETTER)
        assert result.content == LETTER
        assert (result.attempted, result.replaced) == (1, 0)

    def test_keeps_the_old_sentence_when_a_number_is_new(self):
        """A rewrite with a number the old sentence did not have is not used."""
        router = FakeRouter(["1. I mentored three engineers for 2 years."])
        result = polish_stock_phrases(router, LETTER)
        assert result.content == LETTER

    def test_wrong_line_count_keeps_the_letter(self):
        """An answer without exactly the asked numbers keeps the whole letter."""
        router = FakeRouter(["1. I also mentored three engineers.\n2. Extra line."])
        result = polish_stock_phrases(router, LETTER)
        assert result.content == LETTER
        assert (result.attempted, result.replaced) == (1, 0)

    def test_error_keeps_the_letter(self):
        """A router error keeps the letter as written."""
        router = FakeRouter([RuntimeError("down")])
        result = polish_stock_phrases(router, LETTER)
        assert result.content == LETTER
        assert (result.attempted, result.replaced) == (1, 0)

    def test_greeting_is_kept(self):
        """A greeting joined to a sentence is not sent and not changed."""
        router = FakeRouter(["1. I built the billing service."])
        text = "Dear team, moreover, I built the billing service.\n\nI would welcome a call."
        result = polish_stock_phrases(router, text)
        assert "1. moreover, I built the billing service." in router.user_prompt()
        assert result.content == (
            "Dear team, I built the billing service.\n\nI would welcome a call."
        )

    def test_classic_keeps_a_traditional_opening(self):
        """Classic letters may keep a stock opening, so nothing is sent."""
        router = FakeRouter()
        text = "Dear Hiring Manager,\n\nI am writing to apply for the role.\n\nSincerely,\nAlex"
        result = polish_stock_phrases(router, text, style="classic")
        assert result.content == text
        assert router.calls == []

    def test_at_most_max_sentences_are_sent(self):
        """Only the first MAX_SENTENCES target sentences are sent."""
        sentences = [f"Moreover, item {i} shipped." for i in range(MAX_SENTENCES + 2)]
        router = FakeRouter([""])
        result = polish_stock_phrases(router, " ".join(sentences))
        assert result.attempted == MAX_SENTENCES

    def test_whitespace_inside_a_sentence_may_differ(self):
        """A sentence with a line break inside it is still found and replaced."""
        router = FakeRouter(["1. I also mentored three engineers."])
        text = "At Foo I cut latency.\n\nMoreover, I mentored\nthree engineers."
        result = polish_stock_phrases(router, text)
        assert (
            result.content
            == "At Foo I cut latency.\n\nI also mentored three engineers."
        )


class TestAcceptSentence:
    """Tests for accept_sentence."""

    def test_accepts_a_plain_rewrite(self):
        """A shorter sentence with the same facts is accepted."""
        assert accept_sentence(
            "Moreover, I cut latency by 40%.", "I cut latency by 40%."
        )

    def test_rejects_empty(self):
        """An empty rewrite is rejected."""
        assert not accept_sentence("Moreover, I cut latency.", "  ")

    def test_rejects_much_longer(self):
        """A rewrite longer than 1.5 times plus 5 words is rejected."""
        old = "Moreover, I cut latency."
        assert not accept_sentence(old, " ".join(["word"] * 12))
        assert accept_sentence(old, " ".join(["word"] * 11))
