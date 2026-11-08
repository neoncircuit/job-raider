"""
Job Raider - Outcome Analytics

This module defines the conversion, pipeline, and streak metrics of the
outcome tracker.
"""

from datetime import datetime, timedelta
from typing import Any, Dict

from .outcome_models import (
    ApplicationStatus,
    ConversionMetrics,
    InterviewStage,
    Outcome,
)
from .outcome_storage import OutcomeStorage


class OutcomeAnalytics(OutcomeStorage):
    """
    Conversion, pipeline, and streak metrics.
    """

    def get_conversion_metrics(
        self,
        days: int = 90,
    ) -> ConversionMetrics:
        """
        Calculate conversion metrics.

        Args:
            days: Number of days to look back

        Returns:
            ConversionMetrics object
        """
        cutoff = datetime.now() - timedelta(days=days)
        recent_apps = [o for o in self._outcomes.values() if o.applied_date >= cutoff]

        if not recent_apps:
            return ConversionMetrics(
                total_applications=0,
                screening_rate=0.0,
                technical_rate=0.0,
                onsite_rate=0.0,
                offer_rate=0.0,
                acceptance_rate=0.0,
                avg_time_to_offer=0.0,
                avg_time_to_reject=0.0,
            )

        total = len(recent_apps)

        # Calculate rates
        screening = len([o for o in recent_apps if o.has_interview])
        technical = len(
            [
                o
                for o in recent_apps
                if any(i.stage == InterviewStage.TECHNICAL for i in o.interviews)
            ]
        )
        onsite = len(
            [
                o
                for o in recent_apps
                if any(i.stage == InterviewStage.ONSITE for i in o.interviews)
            ]
        )
        offers = len([o for o in recent_apps if o.final_outcome == Outcome.OFFER])
        accepted = len(
            [
                o
                for o in recent_apps
                if o.current_status == ApplicationStatus.OFFER_ACCEPTED
            ]
        )

        # Time to outcome
        time_to_offer = []
        time_to_reject = []

        for o in recent_apps:
            if o.final_outcome == Outcome.OFFER:
                # Find when offer was received
                for note in reversed(o.timeline_notes):
                    if "offer" in note.get("note", "").lower():
                        try:
                            offer_date = datetime.fromisoformat(note["timestamp"])
                            time_to_offer.append((offer_date - o.applied_date).days)
                        except (ValueError, TypeError):
                            pass
                        break

            elif o.final_outcome == Outcome.REJECT:
                # Use last update
                if o.timeline_notes:
                    try:
                        last_date = datetime.fromisoformat(
                            o.timeline_notes[-1]["timestamp"]
                        )
                        time_to_reject.append((last_date - o.applied_date).days)
                    except (ValueError, TypeError):
                        pass

        return ConversionMetrics(
            total_applications=total,
            screening_rate=screening / total if total > 0 else 0,
            technical_rate=technical / total if total > 0 else 0,
            onsite_rate=onsite / total if total > 0 else 0,
            offer_rate=offers / total if total > 0 else 0,
            acceptance_rate=accepted / offers if offers > 0 else 0,
            avg_time_to_offer=(
                sum(time_to_offer) / len(time_to_offer) if time_to_offer else 0
            ),
            avg_time_to_reject=(
                sum(time_to_reject) / len(time_to_reject) if time_to_reject else 0
            ),
        )

    def get_pipeline_effectiveness(
        self,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Analyze pipeline effectiveness.

        Args:
            days: Number of days to analyze

        Returns:
            Effectiveness metrics
        """
        metrics = self.get_conversion_metrics(days)

        # Calculate scores
        funnel_score = (
            metrics.screening_rate * 0.2
            + metrics.technical_rate * 0.3
            + metrics.onsite_rate * 0.3
            + metrics.offer_rate * 0.2
        )

        # Get offer details
        offers = [
            o for o in self._outcomes.values() if o.final_outcome == Outcome.OFFER
        ]

        avg_salary = None
        if offers:
            salaries = []
            for o in offers:
                if o.offer and o.offer.salary_min:
                    salaries.append(o.offer.salary_min)
            if salaries:
                avg_salary = sum(salaries) / len(salaries)

        return {
            "period_days": days,
            "total_applications": metrics.total_applications,
            "funnel_score": funnel_score,
            "conversion_rates": {
                "screening": f"{metrics.screening_rate:.1%}",
                "technical": f"{metrics.technical_rate:.1%}",
                "onsite": f"{metrics.onsite_rate:.1%}",
                "offer": f"{metrics.offer_rate:.1%}",
            },
            "time_metrics": {
                "avg_days_to_offer": metrics.avg_time_to_offer,
                "avg_days_to_reject": metrics.avg_time_to_reject,
            },
            "offer_metrics": {
                "total_offers": sum(
                    1
                    for o in self._outcomes.values()
                    if o.final_outcome == Outcome.OFFER
                ),
                "avg_salary": avg_salary,
                "acceptance_rate": f"{metrics.acceptance_rate:.1%}",
            },
        }

    def get_streak_metrics(self) -> Dict[str, Any]:
        """
        Get current streak metrics.

        Returns:
            Streak information
        """
        # Sort by date
        sorted_outcomes = sorted(
            self._outcomes.values(),
            key=lambda x: x.applied_date,
            reverse=True,
        )

        current_rejection_streak = 0
        current_interview_streak = 0
        days_since_last_offer = None

        last_offer_date = None
        for outcome in sorted_outcomes:
            if outcome.final_outcome == Outcome.OFFER:
                last_offer_date = outcome.applied_date
                break

        if last_offer_date:
            days_since_last_offer = (datetime.now() - last_offer_date).days

        for outcome in sorted_outcomes:
            if outcome.final_outcome == Outcome.REJECT:
                current_rejection_streak += 1
            else:
                break

        for outcome in sorted_outcomes:
            if outcome.has_interview:
                current_interview_streak += 1
            else:
                break

        return {
            "current_rejection_streak": current_rejection_streak,
            "current_interview_streak": current_interview_streak,
            "days_since_last_offer": days_since_last_offer,
        }
