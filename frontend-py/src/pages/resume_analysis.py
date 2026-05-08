"""
Resume Analysis page - Upload resume and view detailed analysis.

Provides resume upload, analysis display with visualizations,
and actionable insights for resume improvement.
"""

from __future__ import annotations

from typing import Any, Dict

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from src.utils.session_state import get_api_client
from src.utils.error_handling import show_connection_error, show_api_error
from src.utils.formatting import format_score
from src.api.client import APIError, ConnectionError


def render() -> None:
    """Render the Resume Analysis page."""
    st.header("Resume Analysis")
    st.markdown("Upload your resume to get detailed insights and improvement recommendations.")

    client = get_api_client()

    # Section A: Resume upload and analysis
    _render_upload_and_analyze(client)

    st.divider()

    # Section B: Analysis results (if available)
    if "analysis_result" in st.session_state:
        _render_analysis_results()


def _render_upload_and_analyze(client) -> None:
    """Render the resume upload and analysis section.

    Args:
        client: The API client instance.
    """
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Upload Resume for Analysis")
        uploaded_file = st.file_uploader(
            "Choose a resume file",
            type=["pdf", "docx", "doc"],
            help="Upload a PDF or DOCX resume for detailed analysis.",
        )

    with col2:
        st.subheader("Analysis Options")
        job_description = st.text_area(
            "Job Description (Optional)",
            help="Paste a job description here for job-specific analysis",
            height=150,
        )

        if job_description:
            st.info("Job-specific analysis will be performed")

    if uploaded_file is not None and st.button("Analyze Resume", use_container_width=True, type="primary"):
        try:
            with st.spinner("Analyzing resume... This may take a few minutes."):
                result = client.analyze_resume(
                    file_bytes=uploaded_file.read(),
                    filename=uploaded_file.name,
                    job_description=job_description if job_description else None,
                )

                st.session_state.analysis_result = result
                st.session_state.analysis_file = uploaded_file.name

                st.success("Analysis complete!")
                st.rerun()

        except ConnectionError:
            show_connection_error()
        except APIError as e:
            show_api_error(e)


def _render_analysis_results() -> None:
    """Render the analysis results."""
    analysis = st.session_state.analysis_result
    file_name = st.session_state.analysis_file

    st.subheader(f"Analysis Results: {file_name}")

    # Overall metrics
    _render_overall_metrics(analysis)

    st.divider()

    # Executive summary
    _render_summary(analysis)

    st.divider()

    # Key strengths and improvements
    _render_strengths_and_improvements(analysis)

    st.divider()

    # Detailed sections
    tab1, tab2, tab3 = st.tabs(["Skills Assessment", "Experience Insights", "Project Insights"])

    with tab1:
        _render_skills_assessment(analysis)

    with tab2:
        _render_experience_insights(analysis)

    with tab3:
        _render_project_insights(analysis)

    st.divider()

    # Recommendations and next steps
    _render_recommendations(analysis)

    # Export options
    _render_export_options()


def _render_overall_metrics(analysis: Dict[str, Any]) -> None:
    """Render overall metrics and summary.

    Args:
        analysis: Analysis result dictionary.
    """
    col1, col2, col3 = st.columns(3)

    # Overall score
    overall_score = analysis.get("overall_score", 0)
    col1.metric("Overall Score", format_score(overall_score))

    # Alignment score (if available)
    if analysis.get("target_alignment_score") is not None:
        alignment_score = analysis.get("target_alignment_score", 0)
        col2.metric("Target Alignment", format_score(alignment_score))
    else:
        col2.metric("Analysis Type", analysis.get("analysis_type", "general").title())

    # Competitive edge
    competitive_edge = analysis.get("competitive_edge", "Unknown")
    col3.metric("Competitive Edge", competitive_edge)

    # Score gauge
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=overall_score,
        title={"text": "Resume Score"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "darkblue"},
            "steps": [
                {"range": [0, 50], "color": "lightgray"},
                {"range": [50, 70], "color": "gray"},
                {"range": [70, 90], "color": "lightblue"},
                {"range": [90, 100], "color": "blue"},
            ],
            "threshold": {
                "line": {"color": "red", "width": 4},
                "thickness": 0.75,
                "value": 70,
            },
        },
    ))

    fig.update_layout(height=300, margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)


def _render_summary(analysis: Dict[str, Any]) -> None:
    """Render executive summary.

    Args:
        analysis: Analysis result dictionary.
    """
    st.subheader("Executive Summary")
    st.write(analysis.get("summary", "No summary available"))


def _render_strengths_and_improvements(analysis: Dict[str, Any]) -> None:
    """Render key strengths and improvements.

    Args:
        analysis: Analysis result dictionary.
    """
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Key Strengths")
        strengths = analysis.get("key_strengths", [])
        if strengths:
            for strength in strengths:
                st.markdown(f":white_check_mark: {strength}")
        else:
            st.info("No specific strengths identified")

    with col2:
        st.subheader("Key Improvements")
        improvements = analysis.get("key_improvements", [])
        if improvements:
            for improvement in improvements:
                st.markdown(f":arrow_right: {improvement}")
        else:
            st.info("No specific improvements suggested")


def _render_skills_assessment(analysis: Dict[str, Any]) -> None:
    """Render skills assessment.

    Args:
        analysis: Analysis result dictionary.
    """
    st.subheader("Skills Assessment")

    skills = analysis.get("skills_assessment", [])
    if not skills:
        st.info("No skills assessment available")
        return

    # Skills table
    display_cols = ["skill_name", "proficiency_level", "years_experience", "is_industry_relevant"]
    skills_df = pd.DataFrame(skills)[display_cols]

    # Add color coding for relevance
    def highlight_relevant(val):
        return ["background-color: #d4edda" if v else "background-color: #f8d7da" for v in val]

    styled_df = skills_df.style.apply(
        highlight_relevant,
        subset=["is_industry_relevant"],
    )

    st.dataframe(
        styled_df,
        column_config={
            "skill_name": st.column_config.TextColumn("Skill"),
            "proficiency_level": st.column_config.TextColumn("Level"),
            "years_experience": st.column_config.NumberColumn("Years", format="%.1f"),
            "is_industry_relevant": st.column_config.CheckboxColumn("Industry Relevant"),
        },
        hide_index=True,
    )

    # Skills with improvement suggestions
    skills_with_suggestions = [s for s in skills if s.get("improvement_suggestions")]

    if skills_with_suggestions:
        st.subheader("Skills to Improve")
        for skill in skills_with_suggestions:
            with st.expander(f"{skill['skill_name']} - {skill['proficiency_level']}"):
                for suggestion in skill.get("improvement_suggestions", []):
                    st.markdown(f"- {suggestion}")


def _render_experience_insights(analysis: Dict[str, Any]) -> None:
    """Render experience insights.

    Args:
        analysis: Analysis result dictionary.
    """
    st.subheader("Work Experience Insights")

    experiences = analysis.get("experience_insights", [])
    if not experiences:
        st.info("No experience insights available")
        return

    for exp in experiences:
        with st.expander(f"{exp['title']} at {exp['company']} ({exp['period']})"):
            col1, col2 = st.columns(2)

            with col1:
                if exp.get("strengths"):
                    st.markdown("**Strengths:**")
                    for strength in exp["strengths"]:
                        st.markdown(f":white_check_mark: {strength}")

                if exp.get("achievements_to_highlight"):
                    st.markdown("**Achievements to Highlight:**")
                    for achievement in exp["achievements_to_highlight"]:
                        st.markdown(f":star: {achievement}")

            with col2:
                if exp.get("gaps"):
                    st.markdown("**Areas for Growth:**")
                    for gap in exp["gaps"]:
                        st.markdown(f":arrow_right: {gap}")


def _render_project_insights(analysis: Dict[str, Any]) -> None:
    """Render project insights.

    Args:
        analysis: Analysis result dictionary.
    """
    st.subheader("Project Portfolio Analysis")

    projects = analysis.get("project_insights", [])
    if not projects:
        st.info("No project insights available")
        return

    # Impact score chart
    projects_df = pd.DataFrame(projects)

    fig = px.scatter(
        projects_df,
        x="name",
        y="impact_score",
        size="impact_score",
        color="impact_score",
        title="Project Impact Analysis",
        labels={"impact_score": "Impact Score", "name": "Project"},
        color_continuous_scale="Blues",
    )

    fig.update_layout(
        xaxis_title="Project",
        yaxis_title="Impact Score (0-100)",
        height=400,
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)

    # Project details
    for project in projects:
        with st.expander(f"{project['name']} - Impact: {project['impact_score']:.0f}/100"):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Technologies:**")
                st.markdown(", ".join(project.get("technologies", [])))

                if project.get("strengths"):
                    st.markdown("**Strengths:**")
                    for strength in project["strengths"]:
                        st.markdown(f":white_check_mark: {strength}")

            with col2:
                if project.get("improvements"):
                    st.markdown("**Potential Improvements:**")
                    for improvement in project["improvements"]:
                        st.markdown(f":arrow_right: {improvement}")


def _render_recommendations(analysis: Dict[str, Any]) -> None:
    """Render recommendations and next steps.

    Args:
        analysis: Analysis result dictionary.
    """
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Resume Improvements")
        improvements = analysis.get("resume_improvements", [])
        if improvements:
            for improvement in improvements:
                st.markdown(f"- {improvement}")
        else:
            st.info("No specific improvements suggested")

    with col2:
        st.subheader("Skill Gaps to Address")
        skill_gaps = analysis.get("skill_gaps", [])
        if skill_gaps:
            for gap in skill_gaps:
                st.markdown(f"- {gap}")
        else:
            st.info("No skill gaps identified")

    st.subheader("Next Steps")
    next_steps = analysis.get("next_steps", [])
    if next_steps:
        for i, step in enumerate(next_steps, 1):
            st.markdown(f"{i}. {step}")
    else:
        st.info("No next steps available")

    # Competitive positioning (job-specific only)
    if analysis.get("competitive_advantages") or analysis.get("competitive_gaps"):
        st.divider()
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Competitive Advantages")
            for advantage in analysis.get("competitive_advantages", []):
                st.markdown(f":white_check_mark: {advantage}")

        with col2:
            st.subheader("Competitive Gaps")
            for gap in analysis.get("competitive_gaps", []):
                st.markdown(f":arrow_right: {gap}")


def _render_export_options() -> None:
    """Render export options for analysis results."""
    st.subheader("Export Analysis")

    col1, col2 = st.columns(2)

    with col1:
        if st.button(":page_facing_up: Download as JSON", use_container_width=True):
            import json

            analysis_json = json.dumps(
                st.session_state.analysis_result,
                indent=2,
                ensure_ascii=False,
            )

            st.download_button(
                label="Click to Download",
                data=analysis_json,
                file_name=f"resume_analysis_{st.session_state.analysis_file}.json",
                mime="application/json",
            )

    with col2:
        if st.button(":clipboard: Copy Summary", use_container_width=True):
            summary = st.session_state.analysis_result.get("summary", "")
            st.toast("Summary copied to clipboard!", icon=":clipboard:")
