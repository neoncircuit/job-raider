"""
Job Raider - Job Scam Detector

This module provides functionality to detect and filter out job scams
and fraudulent job postings.

Author: Job Raider
Date: 2026-04-20
"""

from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum
import re

from ..models.job_listing import JobListing, JobSource
from ..utils.logger import get_logger, Components


class ScamIndicator(str, Enum):
    """Types of scam indicators."""
    PAYMENT_REQUIRED = "payment_required"
    PERSONAL_EMAIL = "personal_email"
    MESSAGING_APP_ONLY = "messaging_app_only"
    UNREALISTIC_SALARY = "unrealistic_salary"
    FAKE_COMPANY = "fake_company"
    VAGUE_DESCRIPTION = "vague_description"
    POOR_GRAMMAR = "poor_grammar"
    IMMEDIATE_HIRE = "immediate_hire"
    SUSPICIOUS_TITLE = "suspicious_title"
    NO_INTERVIEW = "no_interview"
    PHISHING_LINKS = "phishing_links"


class TrustTier(str, Enum):
    """Trust tier for a job listing based on scam analysis."""

    LEGITIMATE = "legitimate"
    LOW_RISK = "low_risk"
    MODERATE_RISK = "moderate_risk"
    SUSPICIOUS = "suspicious"
    LIKELY_SCAM = "likely_scam"

    @classmethod
    def from_confidence(cls, confidence: float) -> "TrustTier":
        """
        Map a confidence score (0-1) to a trust tier.

        Args:
            confidence: Scam confidence score from 0 (safe) to 1 (certain scam).

        Returns:
            The corresponding TrustTier.
        """
        if confidence < 0.2:
            return cls.LEGITIMATE
        elif confidence < 0.4:
            return cls.LOW_RISK
        elif confidence < 0.6:
            return cls.MODERATE_RISK
        elif confidence < 0.8:
            return cls.SUSPICIOUS
        else:
            return cls.LIKELY_SCAM

    @property
    def display_name(self) -> str:
        """Human-readable name for display."""
        names = {
            TrustTier.LEGITIMATE: "Legitimate",
            TrustTier.LOW_RISK: "Low Risk",
            TrustTier.MODERATE_RISK: "Moderate Risk",
            TrustTier.SUSPICIOUS: "Suspicious",
            TrustTier.LIKELY_SCAM: "Likely Scam",
        }
        return names[self]


@dataclass
class ScamReport:
    """Report of scam analysis for a job listing."""
    is_scam: bool
    confidence: float  # 0-1
    indicators: List[ScamIndicator]
    reasons: List[str]
    risk_score: int  # 0-100


@dataclass
class TrustAnalysis:
    """
    Detailed trust analysis for a job listing.

    Provides a tiered trust rating with per-category scoring,
    specific indicators, and human-readable reasons for the rating.
    """
    tier: TrustTier
    confidence: float
    risk_score: int
    is_scam: bool
    category_scores: Dict[str, int]
    indicators: List[ScamIndicator]
    reasons: List[str]


class JobScamDetector:
    """
    Detect job scams and fraudulent postings.

    Uses rule-based and pattern-based detection to identify
    common job scam indicators.
    """

    # Suspicious patterns
    SUSPICIOUS_PATTERNS = {
        "payment": [
            r"pay.*to.*work",
            r"payment.*required",
            r"buy.*equipment",
            r"wire.*transfer",
            r"cryptocurrency.*payment",
            r"bitcoin.*required",
        ],
        "messaging": [
            r"telegram",
            r"whatsapp",
            r"signal",
            r"kik",
            r"discord.*only",
            r"text.*only",
        ],
        "email": [
            r"@gmail\.com",
            r"@yahoo\.com",
            r"@hotmail\.com",
            r"@outlook\.com",
            r"reply.*to.*personal",
        ],
        "immediate": [
            r"immediate.*hire",
            r"start.*today",
            r"no.*interview",
            r"skip.*interview",
        ],
        "unrealistic": [
            r"\$\d{3,}\s*\+\s*per\s*hour",
            r"\$\d{4,}\s+per\s+week",
        ],
    }

    # Scam company patterns
    SUSPICIOUS_COMPANY_PATTERNS = [
        r"Confidential",
        r"Private",
        r"Hidden",
        r"Anonymous",
    ]

    # Legitimate company domains (for verification)
    KNOWN_COMPANY_DOMAINS = {
        "google.com", "amazon.com", "microsoft.com", "apple.com",
        "meta.com", "netflix.com", "twitter.com", "salesforce.com",
        # Add more as needed
    }

    def __init__(self, threshold: float = 0.7):
        """
        Initialize the scam detector.

        Args:
            threshold: Confidence threshold for marking as scam (0-1)
        """
        self.threshold = threshold
        self.logger = get_logger(Components.SCORING)

    def detect(self, job: JobListing) -> ScamReport:
        """
        Analyze a job listing for scam indicators.

        Args:
            job: Job listing to analyze

        Returns:
            ScamReport with analysis results
        """
        analysis = self.analyze(job)
        return ScamReport(
            is_scam=analysis.is_scam,
            confidence=analysis.confidence,
            indicators=analysis.indicators,
            reasons=analysis.reasons,
            risk_score=analysis.risk_score,
        )

    def analyze(self, job: JobListing) -> TrustAnalysis:
        """
        Perform detailed trust analysis on a job listing.

        Runs all category checks independently, captures per-category
        scores, and maps the overall confidence to a trust tier.

        Args:
            job: Job listing to analyze

        Returns:
            TrustAnalysis with tier, per-category scores, and reasons.
        """
        indicators: List[ScamIndicator] = []
        reasons: List[str] = []
        category_scores: Dict[str, int] = {}

        # Check title
        title_score, title_reasons = self._check_title(job)
        category_scores["title"] = title_score
        for reason in title_reasons:
            reasons.append(reason)
            indicators.append(ScamIndicator.SUSPICIOUS_TITLE)

        # Check description
        desc_score, desc_reasons, desc_indicators = self._check_description(job)
        category_scores["description"] = desc_score
        reasons.extend(desc_reasons)
        indicators.extend(desc_indicators)

        # Check company
        company_score, company_reasons, company_indicators = self._check_company(job)
        category_scores["company"] = company_score
        reasons.extend(company_reasons)
        indicators.extend(company_indicators)

        # Check salary
        salary_score, salary_reasons = self._check_salary(job)
        category_scores["salary"] = salary_score
        for reason in salary_reasons:
            reasons.append(reason)
            indicators.append(ScamIndicator.UNREALISTIC_SALARY)

        # Check contact info
        contact_score, contact_reasons, contact_indicators = self._check_contact(job)
        category_scores["contact"] = contact_score
        reasons.extend(contact_reasons)
        indicators.extend(contact_indicators)

        # Calculate totals
        risk_score = min(sum(category_scores.values()), 100)
        confidence = min(risk_score / 100.0, 1.0)
        is_scam = confidence >= self.threshold
        tier = TrustTier.from_confidence(confidence)

        # Remove duplicate indicators
        indicators = list(dict.fromkeys(indicators))

        return TrustAnalysis(
            tier=tier,
            confidence=round(confidence, 3),
            risk_score=risk_score,
            is_scam=is_scam,
            category_scores=category_scores,
            indicators=indicators,
            reasons=reasons,
        )

    def _check_title(self, job: JobListing) -> tuple[int, List[str]]:
        """
        Check job title for suspicious patterns.

        Args:
            job: Job listing

        Returns:
            Tuple of (score, list of reasons)
        """
        score = 0
        reasons = []

        title_lower = job.title.lower()

        # Suspicious title patterns
        suspicious_patterns = [
            (r"earn.*\$\d+.*hour", 40, "Unrealistic hourly rate claim"),
            (r"data.*entry.*typist", 30, "Generic low-skill title with high pay"),
            (r"work.*from.*home.*assistant", 25, "Generic WFH title"),
            (r"customer.*service.*remote", 20, "Generic remote CS title"),
            (r"social.*media.*evaluator", 25, "Unusual role"),
        ]

        for pattern, points, reason in suspicious_patterns:
            if re.search(pattern, title_lower, re.IGNORECASE):
                score += points
                reasons.append(reason)

        # Check for vague titles
        if len(job.title) < 10:
            score += 15
            reasons.append("Title is too short/vague")

        # Check for excessive caps or special chars
        if sum(1 for c in job.title if c.isupper()) / len(job.title) > 0.3:
            score += 10
            reasons.append("Excessive capitalization in title")

        return score, reasons

    def _check_description(self, job: JobListing) -> tuple[int, List[str], List[ScamIndicator]]:
        """
        Check job description for scam indicators.

        Args:
            job: Job listing

        Returns:
            Tuple of (score, reasons, indicators)
        """
        score = 0
        reasons = []
        indicators = []

        if not job.description:
            score += 30
            reasons.append("No description provided")
            indicators.append(ScamIndicator.VAGUE_DESCRIPTION)
            return score, reasons, indicators

        desc_lower = job.description.lower()

        # Check for payment requirements
        for category, patterns in self.SUSPICIOUS_PATTERNS.items():
            if category == "payment":
                for pattern in patterns:
                    if re.search(pattern, desc_lower, re.IGNORECASE):
                        score += 50
                        reasons.append(f"Mentions payment: {pattern}")
                        indicators.append(ScamIndicator.PAYMENT_REQUIRED)

        # Check for messaging app only
        for category, patterns in self.SUSPICIOUS_PATTERNS.items():
            if category == "messaging":
                for pattern in patterns:
                    if re.search(pattern, desc_lower, re.IGNORECASE):
                        score += 40
                        reasons.append(f"Requires messaging app: {pattern}")
                        indicators.append(ScamIndicator.MESSAGING_APP_ONLY)

        # Check for immediate hire language
        for category, patterns in self.SUSPICIOUS_PATTERNS.items():
            if category == "immediate":
                for pattern in patterns:
                    if re.search(pattern, desc_lower, re.IGNORECASE):
                        score += 30
                        reasons.append(f"Immediate hire language: {pattern}")
                        indicators.append(ScamIndicator.IMMEDIATE_HIRE)
                        indicators.append(ScamIndicator.NO_INTERVIEW)

        # Check for poor grammar
        grammar_issues = self._check_grammar(job.description)
        if grammar_issues > 5:
            score += min(grammar_issues * 5, 20)
            reasons.append(f"Poor grammar ({grammar_issues} issues)")
            indicators.append(ScamIndicator.POOR_GRAMMAR)

        # Check for vague descriptions
        if len(job.description) < 100:
            score += 20
            reasons.append("Description is too short")
            if ScamIndicator.VAGUE_DESCRIPTION not in indicators:
                indicators.append(ScamIndicator.VAGUE_DESCRIPTION)

        return score, reasons, indicators

    def _check_company(self, job: JobListing) -> tuple[int, List[str], List[ScamIndicator]]:
        """
        Check company for legitimacy.

        Args:
            job: Job listing

        Returns:
            Tuple of (score, reasons, indicators)
        """
        score = 0
        reasons = []
        indicators = []

        company_lower = job.company.lower()

        # Check for suspicious company names
        for pattern in self.SUSPICIOUS_COMPANY_PATTERNS:
            if re.search(pattern, company_lower, re.IGNORECASE):
                score += 30
                reasons.append(f"Suspicious company name: {pattern}")
                indicators.append(ScamIndicator.FAKE_COMPANY)

        # Check if company name is too generic
        generic_patterns = [r"company\s*\d+", r"organization\s*\d+"]
        for pattern in generic_patterns:
            if re.search(pattern, company_lower, re.IGNORECASE):
                score += 15
                reasons.append("Generic company name")
                if ScamIndicator.FAKE_COMPANY not in indicators:
                    indicators.append(ScamIndicator.FAKE_COMPANY)

        # Could add company lookup API here for verification
        # For now, just basic checks

        return score, reasons, indicators

    def _check_salary(self, job: JobListing) -> tuple[int, List[str]]:
        """
        Check if salary is realistic.

        Args:
            job: Job listing

        Returns:
            Tuple of (score, reasons)
        """
        score = 0
        reasons = []

        if not job.salary_range:
            return score, reasons

        # Check for unrealistic hourly rates
        if job.salary_range.max_amount:
            hourly_rate = job.salary_range.max_amount
            if job.salary_range.period == "hourly":
                if hourly_rate > 100:
                    score += 40
                    reasons.append(f"Unrealistic hourly rate: ${hourly_rate}/hr")
            elif job.salary_range.period == "annual":
                # Convert annual to hourly (roughly)
                approx_hourly = hourly_rate / 2080
                if approx_hourly > 75:
                    score += 30
                    reasons.append(f"High implied hourly rate: ~${approx_hourly:.0f}/hr")

        return score, reasons

    def _check_contact(self, job: JobListing) -> tuple[int, List[str], List[ScamIndicator]]:
        """
        Check contact information for legitimacy.

        Args:
            job: Job listing

        Returns:
            Tuple of (score, reasons, indicators)
        """
        score = 0
        reasons = []
        indicators = []

        # Check if contact email is personal
        if job.recruiter_email:
            email_lower = job.recruiter_email.lower()
            for pattern in self.SUSPICIOUS_PATTERNS["email"]:
                if re.search(pattern, email_lower):
                    score += 20
                    reasons.append(f"Uses personal email: {job.recruiter_email}")
                    indicators.append(ScamIndicator.PERSONAL_EMAIL)

        # Check if no company email/domain is provided
        if not job.recruiter_email and job.company:
            # Try to infer company email from company name
            expected_domain = job.company.lower().replace(" ", "").replace(",", "") + ".com"
            if expected_domain not in str(job.source_url or "").lower():
                score += 10
                reasons.append("No company email provided")

        return score, reasons, indicators

    def _check_grammar(self, text: str) -> int:
        """
        Check text for grammar issues.

        Args:
            text: Text to check

        Returns:
            Number of grammar issues found
        """
        issues = 0

        # Check for multiple consecutive spaces
        if re.search(r'\s{3,}', text):
            issues += 1

        # Check for missing punctuation at end of sentences
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if line and not line[-1] in '.!?':
                # Might be a bullet point or heading, but count it
                if len(line.split()) > 5:  # Only check actual sentences
                    issues += 1

        # Check for all caps
        words = text.split()
        all_caps = sum(1 for word in words if word.isupper() and len(word) > 2)
        if all_caps / len(words) > 0.2:
            issues += 1

        return issues

    def batch_detect(
        self,
        jobs: List[JobListing],
    ) -> List[ScamReport]:
        """
        Detect scams in a batch of job listings.

        Args:
            jobs: List of job listings to analyze

        Returns:
            List of ScamReports
        """
        reports = []

        for job in jobs:
            report = self.detect(job)
            reports.append(report)

        # Log summary
        scam_count = sum(1 for r in reports if r.is_scam)
        self.logger.info(
            f"Scam detection: {scam_count}/{len(jobs)} listings flagged as potential scams"
        )

        return reports

    def filter_scams(
        self,
        jobs: List[JobListing],
    ) -> List[JobListing]:
        """
        Filter out scam job listings.

        Args:
            jobs: List of job listings

        Returns:
            List of legitimate job listings
        """
        filtered = []

        for job in jobs:
            report = self.detect(job)
            if not report.is_scam:
                filtered.append(job)
            else:
                self.logger.warning(
                    f"Filtered potential scam: {job.title} at {job.company} "
                    f"(confidence: {report.confidence:.2f})"
                )

        return filtered


class ScamFilter:
    """
    Quick scam filter for pre-screening.

    Fast, rule-based checks to quickly eliminate obvious scams.
    """

    # Immediate rejection patterns
    REJECT_PATTERNS = [
        "wire transfer",
        "buy supplies",
        "payment required",
        "telegram interview",
        "whatsapp interview",
        "crypto payment",
        "bitcoin",
        "gift cards",
        "direct deposit only",
    ]

    @classmethod
    def is_potential_scam(cls, job: JobListing) -> bool:
        """
        Quick check if job might be a scam.

        Args:
            job: Job listing

        Returns:
            True if potential scam
        """
        # Check title
        title_lower = job.title.lower()
        for pattern in cls.REJECT_PATTERNS:
            if pattern in title_lower:
                return True

        # Check description if available
        if job.description:
            desc_lower = job.description.lower()
            for pattern in cls.REJECT_PATTERNS:
                if pattern in desc_lower:
                    return True

        return False

    @classmethod
    def filter_collection(
        cls,
        jobs: List[JobListing],
    ) -> tuple[List[JobListing], List[JobListing]]:
        """
        Filter job listings into legitimate and potential scams.

        Args:
            jobs: List of job listings

        Returns:
            Tuple of (legitimate jobs, potential scams)
        """
        legitimate = []
        scams = []

        for job in jobs:
            if cls.is_potential_scam(job):
                scams.append(job)
            else:
                legitimate.append(job)

        return legitimate, scams
