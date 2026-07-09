"""
Job Raider - Reports and Dashboard

This module provides reporting functionality for pipeline effectiveness,
cost analysis, and outcome metrics.

Author: Job Raider
Date: 2026-04-21
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..metrics.cost_tracker import CostTracker, PipelineCostSummary
from ..metrics.outcome_tracker import ConversionMetrics, OutcomeTracker
from ..utils.logger import Components, get_logger


@dataclass
class PipelineReport:
    """Complete pipeline execution report."""

    timestamp: datetime
    period_days: int
    cost_summary: PipelineCostSummary
    outcome_metrics: ConversionMetrics
    effectiveness_score: float
    recommendations: List[str]


class ReportGenerator:
    """
    Generate reports for pipeline effectiveness.

    Combines cost tracking and outcome tracking to provide
    comprehensive insights into pipeline performance.
    """

    def __init__(
        self,
        cost_tracker: Optional[CostTracker] = None,
        outcome_tracker: Optional[OutcomeTracker] = None,
        output_dir: str = "data/reports",
    ):
        """
        Initialize report generator.

        Args:
            cost_tracker: Cost tracker instance
            outcome_tracker: Outcome tracker instance
            output_dir: Directory for reports
        """
        self.cost_tracker = cost_tracker or CostTracker()
        self.outcome_tracker = outcome_tracker or OutcomeTracker()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(Components.SCRAPERS)

    def generate_daily_report(self) -> PipelineReport:
        """Generate daily pipeline report."""
        return self._generate_report(days=1)

    def generate_weekly_report(self) -> PipelineReport:
        """Generate weekly pipeline report."""
        return self._generate_report(days=7)

    def generate_monthly_report(self) -> PipelineReport:
        """Generate monthly pipeline report."""
        return self._generate_report(days=30)

    def _generate_report(self, days: int) -> PipelineReport:
        """Generate report for specified period."""
        # Get cost statistics
        cost_stats = self.cost_tracker.get_aggregate_stats(days=days)

        # Get outcome metrics
        outcome_metrics = self.outcome_tracker.get_conversion_metrics(days=days)

        # Calculate effectiveness score
        effectiveness = self._calculate_effectiveness_score(cost_stats, outcome_metrics)

        # Generate recommendations
        recommendations = self._generate_recommendations(cost_stats, outcome_metrics)

        return PipelineReport(
            timestamp=datetime.now(),
            period_days=days,
            cost_summary=PipelineCostSummary(
                total_cost_usd=cost_stats.get("total_cost_usd", 0),
                total_calls=cost_stats.get("total_calls", 0),
                total_tokens=cost_stats.get("total_tokens", 0),
                total_duration_seconds=0,
                by_task_type={},
                by_model={},
                by_provider={},
                cache_hit_rate=0,
            ),
            outcome_metrics=outcome_metrics,
            effectiveness_score=effectiveness,
            recommendations=recommendations,
        )

    def _calculate_effectiveness_score(
        self,
        cost_stats: Dict[str, Any],
        outcome_metrics: ConversionMetrics,
    ) -> float:
        """
        Calculate overall pipeline effectiveness score.

        Args:
            cost_stats: Cost statistics
            outcome_metrics: Outcome metrics

        Returns:
            Score from 0-100
        """
        score = 0

        # Cost efficiency (30 points)
        # Target: <$1 per application
        total_apps = outcome_metrics.total_applications
        total_cost = cost_stats.get("total_cost_usd", 0)

        if total_apps > 0:
            cost_per_app = total_cost / total_apps
            if cost_per_app < 0.50:
                score += 30
            elif cost_per_app < 1.00:
                score += 20
            elif cost_per_app < 2.00:
                score += 10

        # Offer rate (40 points)
        # Target: >5% offer rate
        offer_rate = outcome_metrics.offer_rate
        if offer_rate >= 0.10:  # 10%
            score += 40
        elif offer_rate >= 0.05:  # 5%
            score += 30
        elif offer_rate >= 0.02:  # 2%
            score += 20
        elif offer_rate >= 0.01:  # 1%
            score += 10

        # Interview rate (20 points)
        # Target: >20% screening rate
        screening_rate = outcome_metrics.screening_rate
        if screening_rate >= 0.30:
            score += 20
        elif screening_rate >= 0.20:
            score += 15
        elif screening_rate >= 0.10:
            score += 10
        elif screening_rate >= 0.05:
            score += 5

        # Activity level (10 points)
        # Target: At least 10 applications per week (when normalized)
        weekly_apps = total_apps / (7 / max(cost_stats.get("period_days", 1), 1))
        if weekly_apps >= 10:
            score += 10
        elif weekly_apps >= 5:
            score += 5

        return min(score, 100)

    def _generate_recommendations(
        self,
        cost_stats: Dict[str, Any],
        outcome_metrics: ConversionMetrics,
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        # Cost recommendations
        total_apps = outcome_metrics.total_applications
        if total_apps > 0:
            cost_per_app = cost_stats.get("total_cost_usd", 0) / total_apps

            if cost_per_app > 2.00:
                recommendations.append(
                    f"High cost per application (${cost_per_app:.2f}). "
                    "Ensure Ollama is being used for selection and scoring."
                )

        # Outcome recommendations
        if outcome_metrics.offer_rate < 0.02:
            recommendations.append(
                f"Low offer rate ({outcome_metrics.offer_rate:.1%}). "
                "Consider raising the minimum score threshold to target better matches."
            )

        if outcome_metrics.screening_rate < 0.10:
            recommendations.append(
                f"Low screening rate ({outcome_metrics.screening_rate:.1%}). "
                "Review job descriptions and ensure profile skills are accurately represented."
            )

        # Activity recommendations
        if total_apps < 10:
            recommendations.append(
                "Low application volume. Consider expanding job sources or keywords."
            )

        if not recommendations:
            recommendations.append(
                "Pipeline is performing well. Keep monitoring metrics."
            )

        return recommendations

    def save_report(
        self, report: PipelineReport, filename: Optional[str] = None
    ) -> str:
        """
        Save report to file.

        Args:
            report: Report to save
            filename: Optional filename (auto-generated if None)

        Returns:
            Path to saved report
        """
        if filename is None:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pipeline_report_{timestamp_str}.json"

        filepath = self.output_dir / filename

        report_data = {
            "timestamp": report.timestamp.isoformat(),
            "period_days": report.period_days,
            "effectiveness_score": report.effectiveness_score,
            "recommendations": report.recommendations,
            "cost_summary": {
                "total_cost_usd": report.cost_summary.total_cost_usd,
                "total_calls": report.cost_summary.total_calls,
                "total_tokens": report.cost_summary.total_tokens,
                "by_task_type": {
                    k.value: v for k, v in report.cost_summary.by_task_type.items()
                },
                "by_model": report.cost_summary.by_model,
                "by_provider": {
                    k.value: v for k, v in report.cost_summary.by_provider.items()
                },
            },
            "outcome_metrics": {
                "total_applications": report.outcome_metrics.total_applications,
                "screening_rate": report.outcome_metrics.screening_rate,
                "technical_rate": report.outcome_metrics.technical_rate,
                "onsite_rate": report.outcome_metrics.onsite_rate,
                "offer_rate": report.outcome_metrics.offer_rate,
                "acceptance_rate": report.outcome_metrics.acceptance_rate,
                "avg_time_to_offer": report.outcome_metrics.avg_time_to_offer,
                "avg_time_to_reject": report.outcome_metrics.avg_time_to_reject,
            },
        }

        with open(filepath, "w") as f:
            json.dump(report_data, f, indent=2)

        self.logger.info(f"Report saved to: {filepath}")

        return str(filepath)

    def generate_html_report(
        self, report: PipelineReport, filename: Optional[str] = None
    ) -> str:
        """
        Generate HTML report.

        Args:
            report: Report to convert
            filename: Optional filename (auto-generated if None)

        Returns:
            Path to saved HTML report
        """
        if filename is None:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pipeline_report_{timestamp_str}.html"

        filepath = self.output_dir / filename

        html = self._render_html_report(report)

        with open(filepath, "w") as f:
            f.write(html)

        self.logger.info(f"HTML report saved to: {filepath}")

        return str(filepath)

    def _render_html_report(self, report: PipelineReport) -> str:
        """Render HTML report."""
        # Determine score color
        score = report.effectiveness_score
        if score >= 80:
            score_color = "#22c55e"  # green
            score_label = "Excellent"
        elif score >= 60:
            score_color = "#eab308"  # yellow
            score_label = "Good"
        elif score >= 40:
            score_color = "#f97316"  # orange
            score_label = "Fair"
        else:
            score_color = "#ef4444"  # red
            score_label = "Poor"

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Job Raider - Pipeline Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #1f2937;
            border-bottom: 2px solid #3b82f6;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #374151;
            margin-top: 30px;
        }}
        .score-card {{
            background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
            color: white;
            padding: 30px;
            border-radius: 8px;
            text-align: center;
            margin: 30px 0;
        }}
        .score-value {{
            font-size: 72px;
            font-weight: bold;
            color: {score_color};
        }}
        .score-label {{
            font-size: 24px;
            margin-top: 10px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .metric-card {{
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 20px;
        }}
        .metric-label {{
            font-size: 14px;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .metric-value {{
            font-size: 32px;
            font-weight: bold;
            color: #1f2937;
            margin-top: 5px;
        }}
        .recommendations {{
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 20px;
            border-radius: 4px;
        }}
        .recommendations ul {{
            margin: 10px 0 0 0;
            padding-left: 20px;
        }}
        .recommendations li {{
            margin: 5px 0;
        }}
        .timestamp {{
            color: #6b7280;
            font-size: 14px;
            text-align: right;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Job Raider - Pipeline Report</h1>
        <p class="timestamp">Generated: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>

        <div class="score-card">
            <div class="score-value">{report.effectiveness_score:.0f}</div>
            <div class="score-label">{score_label} - Effectiveness Score</div>
        </div>

        <h2>Period: {report.period_days} Days</h2>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Total Applications</div>
                <div class="metric-value">{report.outcome_metrics.total_applications}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Total Cost</div>
                <div class="metric-value">${report.cost_summary.total_cost_usd:.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Cost Per Application</div>
                <div class="metric-value">
                    ${report.cost_summary.total_cost_usd / max(report.outcome_metrics.total_applications, 1):.2f}
                </div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Screening Rate</div>
                <div class="metric-value">{report.outcome_metrics.screening_rate:.1%}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Offer Rate</div>
                <div class="metric-value">{report.outcome_metrics.offer_rate:.1%}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Avg Days to Offer</div>
                <div class="metric-value">{f"{report.outcome_metrics.avg_time_to_offer:.0f}d" if report.outcome_metrics.avg_time_to_offer > 0 else "N/A"}</div>
            </div>
        </div>

        <h2>Recommendations</h2>
        <div class="recommendations">
            <ul>
        """

        for rec in report.recommendations:
            html += f"<li>{rec}</li>"

        html += """
            </ul>
        </div>
    </div>
</body>
</html>
"""

        return html


class DashboardData:
    """
    Prepare data for dashboard visualization.

    Provides structured data for creating dashboards with
    tools like Grafana, Streamlit, or custom web dashboards.
    """

    @staticmethod
    def get_cost_trend(days: int = 30) -> List[Dict[str, Any]]:
        """Get cost trend over time."""
        # This would load from saved cost run files
        # For now, return placeholder
        return [
            {"date": "2026-04-20", "cost_usd": 0.50, "applications": 10},
            {"date": "2026-04-19", "cost_usd": 0.45, "applications": 9},
            {"date": "2026-04-18", "cost_usd": 0.60, "applications": 12},
        ]

    @staticmethod
    def get_funnel_data(days: int = 30) -> Dict[str, int]:
        """Get application funnel data."""
        tracker = OutcomeTracker()
        metrics = tracker.get_conversion_metrics(days)

        return {
            "applied": metrics.total_applications,
            "screening": int(metrics.total_applications * metrics.screening_rate),
            "technical": int(metrics.total_applications * metrics.technical_rate),
            "onsite": int(metrics.total_applications * metrics.onsite_rate),
            "offer": int(metrics.total_applications * metrics.offer_rate),
        }

    @staticmethod
    def get_company_performance(days: int = 90) -> List[Dict[str, Any]]:
        """Get performance by company."""
        tracker = OutcomeTracker()
        return tracker.get_company_stats(min_applications=3)


# Convenience functions
def generate_report(period_days: int = 7) -> PipelineReport:
    """Generate a report for the specified period."""
    generator = ReportGenerator()
    return generator._generate_report(period_days)


def save_dashboard_data(output_dir: str = "data/reports") -> None:
    """Save data for dashboard visualization."""
    dashboard = DashboardData()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save trend data
    trend = dashboard.get_cost_trend()
    with open(output_path / "cost_trend.json", "w") as f:
        json.dump(trend, f, indent=2)

    # Save funnel data
    funnel = dashboard.get_funnel_data()
    with open(output_path / "funnel.json", "w") as f:
        json.dump(funnel, f, indent=2)

    # Save company performance
    companies = dashboard.get_company_performance()
    with open(output_path / "company_performance.json", "w") as f:
        json.dump(companies, f, indent=2)
