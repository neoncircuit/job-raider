"""
Job Raider - LLM Trust Analyzer

Enhanced trust analysis using LLM to evaluate subtle scam signals
that rule-based regex checks cannot detect. Generates human-readable
summaries explaining the trust rating.

Author: Job Raider
Date: 2026-05-06
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from .scam_detector import (
    JobScamDetector,
    TrustAnalysis,
    TrustTier,
    ScamIndicator,
)
from ..models.job_listing import JobListing
from ..utils.logger import get_logger, Components


@dataclass
class DetailedTrustAnalysis:
    """
    Enhanced trust analysis with LLM-generated summary.

    Extends the rule-based TrustAnalysis with additional LLM-detected
    signals and a human-readable explanation paragraph.
    """
    tier: TrustTier
    confidence: float
    risk_score: int
    is_scam: bool
    category_scores: Dict[str, int]
    indicators: List[ScamIndicator]
    reasons: List[str]
    llm_summary: Optional[str] = None
    llm_indicators: List[str] = field(default_factory=list)
    llm_confidence_adjustment: float = 0.0


SYSTEM_PROMPT = """You are a job posting trust analyst. Given a job listing and its rule-based
trust analysis, evaluate the listing for subtle scam signals that regex patterns miss.

Focus on:
1. Pressure tactics ("apply NOW", "limited positions", "only X left")
2. Vague responsibilities paired with unrealistic perks (high salary + "no experience needed")
3. Mismatch between job title and listed qualifications
4. Pyramid/MLM indicators ("recruit others", "build your team", "downline")
5. Identity harvesting signals (SSN upfront, bank info, ID copy before interview)
6. Company verification issues (recently created, no web presence, name mimics real company)
7. Unusual application flow (personal email only, external form that asks for sensitive info)

CRITICAL RULES:
- Use ONLY information from the job listing provided
- Never fabricate signals that are not present
- If the listing appears legitimate, say so clearly
- Be specific about what triggered each concern

Return a JSON object:
{
    "summary": "1-3 sentence explanation of the trust rating",
    "additional_indicators": ["list of concern strings, or empty if none"],
    "confidence_adjustment": 0.0
}

The confidence_adjustment should be between -0.1 (more trustworthy than rules suggest)
and +0.2 (more suspicious than rules suggest). Only adjust if you find strong evidence
the rules missed."""

USER_PROMPT_TEMPLATE = """Analyze this job listing for trust signals:

TITLE: {title}
COMPANY: {company}
LOCATION: {location}
DESCRIPTION: {description}

RULE-BASED ANALYSIS:
- Risk Score: {risk_score}/100
- Tier: {tier}
- Confidence: {confidence}
- Indicators: {indicators}
- Reasons: {reasons}

Provide your analysis as JSON."""


class TrustAnalyzer:
    """
    Enhanced trust analyzer combining rule-based and LLM analysis.

    First runs the rule-based scam detector, then optionally enhances
    the results with LLM-powered analysis for subtle signals.
    """

    def __init__(
        self,
        llm_router: Optional[Any] = None,
        threshold: float = 0.7,
    ) -> None:
        """
        Initialize the trust analyzer.

        Args:
            llm_router: Optional LLM router for enhanced analysis.
            threshold: Confidence threshold for marking as scam.
        """
        self.llm_router = llm_router
        self.detector = JobScamDetector(threshold=threshold)
        self.logger = get_logger(Components.SCORING)

    def analyze(
        self,
        job: JobListing,
        deep: bool = False,
    ) -> DetailedTrustAnalysis:
        """
        Perform trust analysis on a job listing.

        Args:
            job: Job listing to analyze.
            deep: If True, run LLM-enhanced analysis.

        Returns:
            DetailedTrustAnalysis with tier, reasons, and optional LLM summary.
        """
        trust = self.detector.analyze(job)

        result = DetailedTrustAnalysis(
            tier=trust.tier,
            confidence=trust.confidence,
            risk_score=trust.risk_score,
            is_scam=trust.is_scam,
            category_scores=trust.category_scores,
            indicators=trust.indicators,
            reasons=trust.reasons,
        )

        if deep and self.llm_router:
            llm_result = self._run_llm_analysis(job, trust)
            if llm_result:
                result.llm_summary = llm_result.get("summary")
                result.llm_indicators = llm_result.get("additional_indicators", [])
                result.llm_confidence_adjustment = llm_result.get(
                    "confidence_adjustment", 0.0
                )

                # Apply confidence adjustment if significant
                adjusted = max(
                    0.0,
                    min(1.0, result.confidence + result.llm_confidence_adjustment),
                )
                if abs(adjusted - result.confidence) > 0.05:
                    result.confidence = round(adjusted, 3)
                    result.tier = TrustTier.from_confidence(result.confidence)
                    result.is_scam = result.confidence >= self.detector.threshold
                    result.risk_score = min(int(result.confidence * 100), 100)

        return result

    def _run_llm_analysis(
        self,
        job: JobListing,
        trust: TrustAnalysis,
    ) -> Optional[Dict[str, Any]]:
        """
        Run LLM-powered analysis for subtle scam signals.

        Args:
            job: Job listing to analyze.
            trust: Existing rule-based trust analysis.

        Returns:
            Dict with summary, additional_indicators, and confidence_adjustment,
            or None if LLM is unavailable.
        """
        try:
            from ..llm.router import TaskType

            indicators_str = ", ".join(i.value for i in trust.indicators) or "None"
            reasons_str = "; ".join(trust.reasons) or "None"
            description = (job.description or "")[:2000]

            prompt = USER_PROMPT_TEMPLATE.format(
                title=job.title,
                company=job.company,
                location=job.location or "Not specified",
                description=description,
                risk_score=trust.risk_score,
                tier=trust.tier.display_name,
                confidence=f"{trust.confidence:.1%}",
                indicators=indicators_str,
                reasons=reasons_str,
            )

            response = self.llm_router.generate(
                task_type=TaskType.TRUST_ANALYSIS,
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
            )

            if not response:
                return None

            # Parse JSON response
            text = response.strip()
            if "{" in text:
                import json

                try:
                    json_str = text[text.index("{") : text.rfind("}") + 1]
                    return json.loads(json_str)
                except (json.JSONDecodeError, ValueError):
                    self.logger.warning("Failed to parse LLM trust analysis response")
                    return {"summary": text, "additional_indicators": [], "confidence_adjustment": 0.0}

            return None

        except Exception as e:
            self.logger.warning(f"LLM trust analysis failed: {e}")
            return None
