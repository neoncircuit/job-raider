"""
Unit test for the enable_company_site_search setting (company-site-apply, S1).
"""

from src.api.settings import CostLimits


def test_company_site_search_is_on_by_default() -> None:
    """The company site search is on by default (decision K2a)."""
    assert CostLimits().enable_company_site_search is True
