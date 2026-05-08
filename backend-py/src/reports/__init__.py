"""
Job Raider - Reports Module

This module provides reporting functionality for pipeline effectiveness,
cost analysis, and outcome metrics.

Author: Job Raider
Date: 2026-04-21
"""

from .report_generator import (
    PipelineReport,
    ReportGenerator,
    DashboardData,
    generate_report,
    save_dashboard_data,
)

__all__ = [
    "PipelineReport",
    "ReportGenerator",
    "DashboardData",
    "generate_report",
    "save_dashboard_data",
]
