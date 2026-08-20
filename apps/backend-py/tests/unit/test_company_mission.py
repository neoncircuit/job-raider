"""
Unit tests for company mission verify-against-JD-facts helpers.

Network-free: candidates are synthetic MissionCandidate objects.
"""

from __future__ import annotations

from src.generation.company_mission import (
    MissionCandidate,
    build_search_query,
    detect_collision_phrases,
    extract_jd_facts,
    extractive_paraphrase,
    verify_mission_candidates,
)


def test_extract_jd_facts_prefers_curated_phrases() -> None:
    """
    When curated jd_facts are present, ignore narrative JD token mining.
    """
    facts = extract_jd_facts(
        jd_text="Akro AI Singapore document intelligence startup unrelated industrial brands",
        jd_facts=["Singapore", "document intelligence", "pre-seed"],
    )
    assert facts == ["singapore", "document intelligence", "pre-seed"]
    assert "unrelated" not in facts
    assert "industrial" not in facts


def test_extract_jd_facts_mines_text_when_no_curated() -> None:
    """
    Without curated facts, mine meaningful tokens from JD text.
    """
    facts = extract_jd_facts(jd_text="Singapore document intelligence startup")
    assert "singapore" in facts
    assert "document" in facts
    assert "intelligence" in facts


def test_build_search_query_includes_disambiguators() -> None:
    """
    Search query should include company plus JD disambiguators.
    """
    query = build_search_query(
        "Akro AI",
        jd_facts=["Singapore", "document intelligence", "pre-seed"],
    )
    assert "Akro AI" in query
    assert "singapore" in query.lower()
    assert "mission" in query.lower()


def test_verify_passes_clear_agri_candidate() -> None:
    """
    Positive-control page with matching name and agri facts should pass.
    """
    candidate = MissionCandidate(
        url="https://example.com/gar",
        title="Golden Agri-Resources",
        text=(
            "Golden Agri-Resources is a leading palm oil agribusiness based in "
            "Singapore with sustainability and plantation initiatives."
        ),
    )
    result = verify_mission_candidates(
        "Golden Agri-Resources",
        [candidate],
        jd_facts=["Singapore", "palm oil", "agribusiness", "sustainability"],
    )
    assert result.status == "pass"
    assert result.skip_reason == ""
    assert result.source_url == candidate.url
    assert result.fact_match_ratio >= 0.35


def test_verify_skips_akro_mils_collision() -> None:
    """
    Akro-Mils storage page must not pass when JD facts are AI / Singapore.
    """
    wrong = MissionCandidate(
        url="https://example.com/akro-mils",
        title="Akro-Mils Storage Bins and Shelving",
        text=(
            "Akro-Mils manufactures plastic bins, shelving, and industrial storage "
            "for material handling. Storage bins for warehouses."
        ),
        snippet="Akro-Mils shelving and storage bins",
    )
    result = verify_mission_candidates(
        "Akro AI",
        [wrong],
        jd_facts=[
            "Singapore",
            "document intelligence",
            "artificial intelligence",
            "AI",
            "pre-seed",
        ],
    )
    assert result.status == "skip"
    assert result.skip_reason
    assert (
        "ambiguous" in result.skip_reason.lower()
        or "collision" in result.skip_reason.lower()
    )
    assert detect_collision_phrases(wrong.text)


def test_verify_skips_parent_only_without_far_east_facts() -> None:
    """
    Global Naval Group page without Far East / Singapore should not clear gate.
    """
    parent = MissionCandidate(
        url="https://example.com/naval-group",
        title="Naval Group — Defence Naval Systems",
        text=(
            "Naval Group is a French defence company specialising in naval systems "
            "and submarines for international markets."
        ),
    )
    result = verify_mission_candidates(
        "Naval Group Far East",
        [parent],
        jd_facts=["Singapore", "Far East", "Pte Ltd", "defence", "naval"],
    )
    assert result.status == "skip"
    assert result.skip_reason
    assert (
        "threshold" in result.skip_reason.lower()
        or "ambiguous" in result.skip_reason.lower()
    )


def test_verify_passes_subsidiary_specific_page() -> None:
    """
    Subsidiary page mentioning Far East / Singapore / defence should pass.
    """
    sub = MissionCandidate(
        url="https://example.com/ngfe",
        title="Naval Group Far East Pte Ltd",
        text=(
            "Naval Group Far East Pte Ltd is the Singapore subsidiary supporting "
            "naval defence programmes in the Far East region."
        ),
    )
    result = verify_mission_candidates(
        "Naval Group Far East",
        [sub],
        jd_facts=["Singapore", "Far East", "Pte Ltd", "defence", "naval"],
    )
    assert result.status == "pass"


def test_verify_empty_candidates_has_legible_reason() -> None:
    """
    Skip with no candidates must still return a non-blank reason.
    """
    result = verify_mission_candidates(
        "Akro AI",
        [],
        jd_facts=["Singapore", "AI"],
    )
    assert result.status == "skip"
    assert len(result.skip_reason.strip()) > 10


def test_extractive_paraphrase_rewrites_attribution() -> None:
    """
    Extractive paraphrase should attribute the company, not copy opener only.
    """
    brief = extractive_paraphrase(
        "We are a leading palm oil agribusiness. Our plantations support sustainability.",
        "Golden Agri-Resources",
    )
    assert "Golden Agri-Resources" in brief
    assert len(brief) > 20


def test_pick_excerpt_skips_footer_boilerplate() -> None:
    """
    Excerpt selection should prefer substantive sentences over cookie footers.
    """
    from src.generation.company_mission import _pick_excerpt

    text = (
        "Golden Agri-Resources is a leading palm oil agribusiness with "
        "sustainability programmes across Singapore plantations. "
        "Manage Consent We use cookies to improve your experience. "
        "Phone: +65 6590 0800 Fax: +65 6590 0887 All rights reserved."
    )
    excerpt = _pick_excerpt(text, ["singapore", "palm oil", "sustainability"])
    assert "palm oil" in excerpt.lower() or "sustainability" in excerpt.lower()
    assert "manage consent" not in excerpt.lower()
    assert "we use cookies" not in excerpt.lower()


def test_extract_main_content_prefers_article() -> None:
    """
    Main-content extraction should keep article body and drop nav/footer.
    """
    from src.generation.company_mission_search import extract_main_content_text

    html = """
    <html><body>
      <nav>Home Careers</nav>
      <main><article>
        <p>Naval Group Far East supports the Republic of Singapore Navy
        with maintenance for Formidable frigates.</p>
      </article></main>
      <footer>Copyright All rights reserved Follow us</footer>
      <div class="cookie-banner">We use cookies Accept</div>
    </body></html>
    """
    text = extract_main_content_text(html)
    assert "Formidable frigates" in text
    assert "Home Careers" not in text
    assert "We use cookies" not in text


def test_resolve_disabled_returns_disabled_status() -> None:
    """
    When enable flag is false, resolve must not search and status is disabled.
    """
    from src.generation.company_mission_search import resolve_company_mission

    result = resolve_company_mission("Golden Agri-Resources", enabled=False)
    assert result.status == "disabled"
    assert result.brief == ""
    assert result.to_mission_context()["status"] == "disabled"
