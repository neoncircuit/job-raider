"""
Unit tests for assessment generation prompt template layout.
"""

from pathlib import Path

import yaml


class TestAssessmentTemplateNonce:
    """Session nonce appears after CONTEXT in the user template."""

    def test_nonce_after_context_in_yaml(self) -> None:
        """Loaded template places SESSION NONCE after CONTEXT block."""
        config_path = (
            Path(__file__).resolve().parents[2] / "config" / "prompt_templates.yaml"
        )
        with open(config_path, "r", encoding="utf-8") as handle:
            templates = yaml.safe_load(handle)

        user_template = templates["prompts"]["assessment_generation"]["user"]
        context_idx = user_template.index("CONTEXT:")
        nonce_idx = user_template.index("SESSION NONCE:")
        assert nonce_idx > context_idx

    def test_nonce_after_json_schema_instructions(self) -> None:
        """Nonce is at the end after JSON schema instructions."""
        config_path = (
            Path(__file__).resolve().parents[2] / "config" / "prompt_templates.yaml"
        )
        with open(config_path, "r", encoding="utf-8") as handle:
            templates = yaml.safe_load(handle)

        user_template = templates["prompts"]["assessment_generation"]["user"]
        schema_marker = "Return a JSON array of question objects"
        nonce_idx = user_template.index("SESSION NONCE:")
        assert nonce_idx > user_template.index(schema_marker)
