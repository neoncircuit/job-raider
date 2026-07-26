"""
Unit tests for LinkedIn description extraction.
"""

from bs4 import BeautifulSoup

from src.scrapers.linkedin_scraper import LinkedInScraper


class TestLinkedInDescriptionExtraction:
    """Description parsers for LinkedIn detail pages."""

    def test_extracts_jobposting_json_ld(self) -> None:
        """JSON-LD JobPosting description is preferred over missing CSS nodes."""
        html = """
        <html><body>
        <script type="application/ld+json">
        {
          "@type": "JobPosting",
          "title": "Software Engineer",
          "description": "<p>Build reliable APIs and data pipelines for customers worldwide.</p><ul><li>Python</li><li>SQL</li></ul>"
        }
        </script>
        </body></html>
        """
        scraper = LinkedInScraper()
        soup = BeautifulSoup(html, "html.parser")
        text = scraper._extract_description(soup)
        assert text is not None
        assert "Build reliable APIs" in text
        assert "Python" in text

    def test_falls_back_to_css_selector(self) -> None:
        """CSS markup selector still works when JSON-LD is absent."""
        html = """
        <html><body>
        <div class="show-more-less-html__markup">
          <p>Design and ship features across the full stack for our platform.</p>
          <p>Collaborate with product and design partners daily.</p>
        </div>
        </body></html>
        """
        scraper = LinkedInScraper()
        soup = BeautifulSoup(html, "html.parser")
        text = scraper._extract_description(soup)
        assert text is not None
        assert "full stack" in text
