"""
Scam suite: the pipeline scam decision on labeled postings.

A dataset folder has ``cases.jsonl`` (one posting per line with its expected
label and indicator groups). Stage A adds the case model and the runner.
``src/scoring/`` does not change in Stage A.
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...models.job_listing import JobListing
from ..run_metadata import BACKEND_DIR

SUITE = "scam"
DEFAULT_DATASET_DIR = BACKEND_DIR / "tests" / "fixtures" / "eval" / "scam"

INDICATOR_GROUPS: FrozenSet[str] = frozenset(
    {
        "payment",
        "contact",
        "urgency",
        "compensation",
        "listing_quality",
    }
)

CASE_GROUPS: FrozenSet[str] = frozenset(
    {
        "legit_fixture",
        "legit_written",
        "hard_negative",
        "scam_payment",
        "scam_contact",
        "scam_urgency",
        "scam_compensation",
        "scam_listing",
    }
)

SCAM_CASE_GROUPS: FrozenSet[str] = frozenset(
    group for group in CASE_GROUPS if group.startswith("scam_")
)
LEGIT_CASE_GROUPS: FrozenSet[str] = CASE_GROUPS - SCAM_CASE_GROUPS

ExpectedLabel = Literal["scam", "legit"]


class ScamCase(BaseModel):
    """One labeled job posting for the scam evaluation set."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    job: Dict[str, Any]
    expected: ExpectedLabel
    indicator_groups: List[str] = Field(default_factory=list)
    source: str
    note: str = ""

    @field_validator("case_id")
    @classmethod
    def _valid_case_id(cls, value: str) -> str:
        """
        Require ``<group>__<short_name>`` with a known group.

        Args:
            value: Case identifier.

        Returns:
            The same identifier.

        Raises:
            ValueError: When the prefix is missing or unknown.
        """
        if "__" not in value:
            raise ValueError(f"case_id must be <group>__<short_name>: {value}")
        group = value.split("__", 1)[0]
        if group not in CASE_GROUPS:
            raise ValueError(f"unknown case group: {group}")
        return value

    @field_validator("indicator_groups")
    @classmethod
    def _known_indicator_groups(cls, value: List[str]) -> List[str]:
        """
        Reject indicator names that the guide does not define.

        Args:
            value: Indicator group names.

        Returns:
            The same list.

        Raises:
            ValueError: When a name is not an indicator group.
        """
        unknown = sorted(set(value) - INDICATOR_GROUPS)
        if unknown:
            raise ValueError(f"unknown indicator groups: {unknown}")
        return value

    @field_validator("source")
    @classmethod
    def _valid_source(cls, value: str) -> str:
        """
        Accept a fixture pointer or ``written``.

        Args:
            value: Source string.

        Returns:
            The same string.

        Raises:
            ValueError: When the source form is not allowed.
        """
        if value == "written" or value.startswith("fixture:"):
            return value
        raise ValueError(f"source must be written or fixture:<path>: {value}")

    @model_validator(mode="after")
    def _label_matches_group(self) -> "ScamCase":
        """
        Check that the label, the groups, and the case prefix agree.

        Args:
            self: Validated case.

        Returns:
            The same case.

        Raises:
            ValueError: When the prefix, the expected label, or the
                indicator list disagree.
        """
        group = self.case_id.split("__", 1)[0]
        if group in SCAM_CASE_GROUPS and self.expected != "scam":
            raise ValueError(f"{self.case_id}: scam_* cases must have expected=scam")
        if group in LEGIT_CASE_GROUPS and self.expected != "legit":
            raise ValueError(
                f"{self.case_id}: legit_* and hard_negative cases must have "
                "expected=legit"
            )
        if self.expected == "scam" and not self.indicator_groups:
            raise ValueError(f"{self.case_id}: a scam must list indicator groups")
        if self.expected == "legit" and self.indicator_groups:
            raise ValueError(
                f"{self.case_id}: a legitimate posting must have empty "
                "indicator_groups"
            )
        JobListing.model_validate(self.job)
        return self
