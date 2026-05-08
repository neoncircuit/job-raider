"""
Profile page - Upload resume, view, and edit user profile.

Provides resume file upload, structured profile display broken
into sections (contact, target, skills, projects, experience,
education), and an inline edit form.
"""

from __future__ import annotations

from typing import Any, Dict

import streamlit as st

from src.utils.session_state import (
    get_api_client,
    get_profile_data,
    set_profile_data,
    clear_profile_data,
)
from src.utils.error_handling import show_connection_error, show_api_error
from src.utils.formatting import format_date
from src.api.client import APIError, ConnectionError


def render() -> None:
    """Render the Profile management page."""
    st.header("Profile")

    client = get_api_client()

    # Section A: Resume upload
    _render_upload(client)

    st.divider()

    # Section B: Profile display
    _render_profile_display(client)

    st.divider()

    # Section C: Profile editor
    _render_profile_editor(client)


def _render_upload(client) -> None:
    """Render the resume upload section.

    Args:
        client: The API client instance.
    """
    st.subheader("Upload Resume")

    uploaded_file = st.file_uploader(
        "Choose a resume file",
        type=["pdf", "docx", "doc"],
        help="Upload a PDF or DOCX resume to extract your profile.",
    )

    if uploaded_file is not None and st.button("Upload & Parse"):
        try:
            with st.spinner("Parsing resume..."):
                result = client.upload_resume(
                    uploaded_file.read(), uploaded_file.name
                )
                clear_profile_data()
                st.success(f"Resume uploaded: {result.get('message', 'Success')}")
                st.rerun()
        except ConnectionError:
            show_connection_error()
        except APIError as e:
            show_api_error(e)


def _render_profile_display(client) -> None:
    """Render the profile data display sections.

    Args:
        client: The API client instance.
    """
    st.subheader("Current Profile")

    profile = get_profile_data()
    if not profile:
        try:
            profile = client.get_profile()
            set_profile_data(profile)
        except ConnectionError:
            show_connection_error()
            return
        except APIError as e:
            if e.status_code == 404:
                st.info("No profile found. Upload a resume to create one.")
                return
            show_api_error(e)
            return

    # Contact info
    contact = profile.get("contact_info", {})
    if contact:
        with st.expander("Contact Information", expanded=True):
            col1, col2 = st.columns(2)
            col1.markdown(f"**Name:** {contact.get('name', 'N/A')}")
            col1.markdown(f"**Email:** {contact.get('email', 'N/A')}")
            col2.markdown(f"**Phone:** {contact.get('phone', 'N/A')}")
            col2.markdown(f"**Location:** {contact.get('location', 'N/A')}")
            urls = [
                f"[LinkedIn]({u})" if (u := contact.get("linkedin_url")) else None,
                f"[GitHub]({u})" if (u := contact.get("github_url")) else None,
                f"[Portfolio]({u})" if (u := contact.get("portfolio_url")) else None,
            ]
            url_str = " | ".join(u for u in urls if u)
            if url_str:
                st.markdown(url_str)

    # Target job
    target = profile.get("target_job", {})
    if target:
        with st.expander("Target Job Preferences"):
            st.markdown(f"**Keywords:** {', '.join(target.get('keywords', []))}")
            st.markdown(f"**Locations:** {', '.join(target.get('locations', []))}")
            st.markdown(f"**Experience:** {', '.join(target.get('experience_levels', []))}")
            st.markdown(f"**Remote:** {'Yes' if target.get('remote_preference') else 'No'}")
            st.markdown(f"**Constraint Mode:** {target.get('constraint_mode', 'boost').title()}")

    # Apprenticeship contract
    apprenticeship = profile.get("apprenticeship")
    if apprenticeship:
        with st.expander("Apprenticeship / Traineeship Contract", expanded=True):
            st.markdown(f"**Required Field:** {apprenticeship.get('field', 'N/A')}")
            st.markdown(f"**Sponsoring Employer:** {apprenticeship.get('employer', 'N/A')}")
            duration = apprenticeship.get('duration_months')
            st.markdown(f"**Remaining Duration:** {f'{duration} months' if duration else 'N/A'}")
            st.markdown(f"**Start Date:** {apprenticeship.get('start_date', 'N/A')}")
            st.markdown(f"**End Date:** {apprenticeship.get('end_date', 'N/A')}")
            st.markdown(f"**Active:** {'Yes' if apprenticeship.get('is_active') else 'No'}")

    # Skills
    skills = profile.get("skills", [])
    if skills:
        with st.expander(f"Skills ({len(skills)})"):
            for skill in skills:
                name = skill.get("name", "Unknown")
                category = skill.get("category", "")
                proficiency = skill.get("proficiency", "")
                years = skill.get("years_experience", 0)
                st.markdown(f"- **{name}** ({category}) - {proficiency}, {years}y")

    # Work experience
    experience = profile.get("work_experience", [])
    if experience:
        with st.expander(f"Work Experience ({len(experience)})"):
            for exp in experience:
                title = exp.get("title", "Unknown")
                company = exp.get("company", "Unknown")
                start = format_date(exp.get("start_date"))
                end = format_date(exp.get("end_date")) or "Present"
                st.markdown(f"**{title}** at {company} ({start} - {end})")
                desc = exp.get("description")
                if desc:
                    st.caption(desc)

    # Education
    education = profile.get("education", [])
    if education:
        with st.expander(f"Education ({len(education)})"):
            for edu in education:
                degree = edu.get("degree", "Unknown")
                field = edu.get("field_of_study", "")
                school = edu.get("institution", "Unknown")
                grad = format_date(edu.get("graduation_date"))
                st.markdown(f"**{degree}** in {field} - {school} ({grad})")


def _render_profile_editor(client) -> None:
    """Render the profile edit form.

    Args:
        client: The API client instance.
    """
    with st.expander("Edit Profile"):
        with st.form("profile_edit_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Name")
                email = st.text_input("Email")
                phone = st.text_input("Phone")
                location = st.text_input("Location")
            with col2:
                linkedin = st.text_input("LinkedIn URL")
                github = st.text_input("GitHub URL")
                portfolio = st.text_input("Portfolio URL")
                remote_pref = st.checkbox("Remote Preference", value=True)

            st.divider()
            constraint_mode = st.selectbox(
                "Apprenticeship Constraint Mode",
                options=["boost", "filter"],
                format_func=lambda x: f"{x.title()} - {'Boost matching jobs' if x == 'boost' else 'Exclude non-matching jobs'}",
                help="How apprenticeship contract constraints affect job matching",
            )

            st.markdown("**Apprenticeship / Traineeship Contract** *(optional)*")
            app_col1, app_col2 = st.columns(2)
            with app_col1:
                app_field = st.text_input("Required Field", placeholder="e.g. AI/ML, Healthcare")
                app_employer = st.text_input("Sponsoring Employer", placeholder="e.g. Company Name")
                app_start = st.text_input("Start Date", placeholder="YYYY-MM")
            with app_col2:
                app_duration = st.number_input("Duration (months)", min_value=0, step=1)
                app_end = st.text_input("End Date", placeholder="YYYY-MM")
                app_active = st.checkbox("Contract Active", value=True)

            submitted = st.form_submit_button("Update Profile", use_container_width=True)

            if submitted:
                updates: Dict[str, Any] = {}
                if name:
                    updates["name"] = name
                if email:
                    updates["email"] = email
                if phone:
                    updates["phone"] = phone
                if location:
                    updates["location"] = location
                if linkedin:
                    updates["linkedin_url"] = linkedin
                if github:
                    updates["github_url"] = github
                if portfolio:
                    updates["portfolio_url"] = portfolio
                updates["remote_preference"] = remote_pref
                updates["constraint_mode"] = constraint_mode

                # Apprenticeship fields (only send if field is provided)
                if app_field:
                    updates["apprenticeship_field"] = app_field
                    updates["apprenticeship_duration_months"] = app_duration if app_duration > 0 else None
                    updates["apprenticeship_employer"] = app_employer or None
                    updates["apprenticeship_start_date"] = app_start or None
                    updates["apprenticeship_end_date"] = app_end or None
                    updates["apprenticeship_is_active"] = app_active

                try:
                    client.update_profile(updates)
                    clear_profile_data()
                    st.success("Profile updated successfully.")
                    st.rerun()
                except ConnectionError:
                    show_connection_error()
                except APIError as e:
                    show_api_error(e)
