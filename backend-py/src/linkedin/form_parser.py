"""
Job Raider - Easy Apply Form Parser

Parses LinkedIn Easy Apply modal forms into structured question data
using Playwright. Does NOT submit - only reads the form structure.

Author: Job Raider
Date: 2026-05-04
"""

from typing import List, Optional, Any

from playwright.sync_api import Page, ElementHandle

from .form_models import (
    ParsedForm,
    FormStep,
    FormQuestion,
    QuestionType,
)
from ..utils.logger import get_logger, Components


class EasyApplyFormParser:
    """
    Parse LinkedIn Easy Apply modal into structured question data.

    Reads the multi-step form structure including question types,
    options, and required fields. Uses multiple fallback selectors
    for resilience against LinkedIn DOM changes.
    """

    # Modal selectors (multiple fallbacks per element)
    MODAL_SELECTORS = [
        "div.jobs-easy-apply-modal",
        "div.jobs-unified-top-card__easy-apply",
        ".jobs-easy-apply-content",
    ]

    EASY_APPLY_BUTTON_SELECTORS = [
        "a[href*='/apply/']:has-text('Easy Apply')",
        "a[href*='apply']:has-text('easy apply')",
        "a:has-text('Easy Apply')",
        "button.jobs-apply-button",
        "a.jobs-apply-button",
        "button[data-control-name*='easy_apply']",
        "button:has-text('Easy Apply')",
        "button:has-text('Apply now')",
        "a:has-text('Apply now')",
    ]

    NEXT_BUTTON_SELECTORS = [
        "button[data-easy-apply-next-button]",
        "button[aria-label='Next']",
        "button:has-text('Next')",
    ]

    REVIEW_BUTTON_SELECTORS = [
        "button[data-easy-apply-review-button]",
        "button[aria-label='Review']",
        "button:has-text('Review')",
    ]

    SUBMIT_BUTTON_SELECTORS = [
        "button[data-easy-apply-submit-button]",
        "button[aria-label='Submit application']",
        "button:has-text('Submit')",
        "button:has-text('Submit application')",
    ]

    CLOSE_BUTTON_SELECTORS = [
        "button[aria-label='Dismiss']",
        "button[data-easy-apply-close-button]",
        "button.jobs-easy-apply-modal__close",
    ]

    # Form field selectors
    FIELD_CONTAINER_SELECTORS = [
        "div.jobs-easy-apply-form-section",
        "div.jobs-easy-apply-form-element",
        "div.fb-dash-form-element",
        "div.jobs-unified-top-card__form-element",
    ]

    def __init__(self) -> None:
        """Initialize the form parser."""
        self.logger = get_logger(Components.SCRAPERS)

    def parse_form(
        self,
        page: Page,
        job_id: str,
        job_title: str,
        company: str,
    ) -> Optional[ParsedForm]:
        """
        Parse the entire multi-step Easy Apply form.

        Opens the Easy Apply modal, iterates through each step,
        and collects all question data. Closes the modal after parsing.

        Args:
            page: Playwright page with the job listing loaded.
            job_id: LinkedIn job ID.
            job_title: Job title for metadata.
            company: Company name for metadata.

        Returns:
            ParsedForm with all steps and questions, or None if parsing fails.
        """
        try:
            # Click Easy Apply button to open modal
            if not self._click_easy_apply(page):
                self.logger.error("Could not find Easy Apply button")
                return None

            page.wait_for_timeout(2000)

            steps: List[FormStep] = []
            step_num = 1
            requires_resume = False
            requires_cover_letter = False

            while True:
                self.logger.info(f"Parsing form step {step_num}")

                step = self._parse_current_step(page, step_num)
                steps.append(step)

                # Check for resume/cover letter requirements
                if self._has_resume_upload(page):
                    requires_resume = True
                if self._has_cover_letter_field(page):
                    requires_cover_letter = True

                # Check for next/submit buttons
                has_next = self._has_element(page, self.NEXT_BUTTON_SELECTORS)
                has_review = self._has_element(page, self.REVIEW_BUTTON_SELECTORS)
                has_submit = self._has_element(page, self.SUBMIT_BUTTON_SELECTORS)

                step.has_next = has_next
                step.has_review = has_review or has_submit

                if not has_next and not has_review and not has_submit:
                    break

                if has_submit or has_review:
                    # We've reached the final step
                    break

                # Click Next to go to the next step
                if not self._click_element(page, self.NEXT_BUTTON_SELECTORS):
                    break

                page.wait_for_timeout(1500)
                step_num += 1

            # Close the modal
            self._close_modal(page)

            return ParsedForm(
                job_id=job_id,
                job_title=job_title,
                company=company,
                steps=steps,
                total_steps=len(steps),
                requires_resume=requires_resume,
                requires_cover_letter=requires_cover_letter,
            )

        except Exception as e:
            self.logger.error(f"Failed to parse Easy Apply form: {e}")
            self._close_modal(page)
            return None

    def _click_easy_apply(self, page: Page) -> bool:
        """
        Find and click the Easy Apply button on the job page.

        Args:
            page: Playwright page.

        Returns:
            True if the button was clicked.
        """
        return self._click_element(page, self.EASY_APPLY_BUTTON_SELECTORS)

    def _parse_current_step(self, page: Page, step_number: int) -> FormStep:
        """
        Parse questions from the currently visible form step.

        Args:
            page: Playwright page with the modal open.
            step_number: 1-based step index.

        Returns:
            FormStep with all detected questions.
        """
        questions: List[FormQuestion] = []

        for container_selector in self.FIELD_CONTAINER_SELECTORS:
            containers = page.query_selector_all(container_selector)
            if containers:
                for container in containers:
                    question = self._parse_field(container, page)
                    if question:
                        questions.append(question)
                break

        # Fallback: scan for any form fields in the modal
        if not questions:
            questions = self._scan_for_fields(page)

        return FormStep(
            step_number=step_number,
            questions=questions,
        )

    def _parse_field(
        self, container: ElementHandle, page: Page
    ) -> Optional[FormQuestion]:
        """
        Parse a single form field container into a FormQuestion.

        Args:
            container: Playwright element handle for the field container.
            page: Playwright page for additional queries.

        Returns:
            FormQuestion or None if the field cannot be parsed.
        """
        question_text = self._extract_question_text(container)
        if not question_text:
            return None

        question_type = self._identify_question_type(container)
        is_required = self._is_required(container)
        options = self._extract_options(container) if question_type in (
            QuestionType.DROPDOWN,
            QuestionType.RADIO,
            QuestionType.CHECKBOX,
            QuestionType.MULTI_SELECT,
        ) else []

        # Try to get a selector for Playwright interaction
        field_selector = self._get_field_selector(container, question_type)
        placeholder = self._get_placeholder(container, question_type)

        return FormQuestion(
            question_text=question_text,
            question_type=question_type,
            is_required=is_required,
            options=options,
            field_selector=field_selector,
            placeholder=placeholder,
        )

    def _extract_question_text(self, container: ElementHandle) -> Optional[str]:
        """
        Extract the label or question text from a form field container.

        Args:
            container: The field container element.

        Returns:
            Question text string, or None.
        """
        label_selectors = [
            "label",
            "span.fb-dash-form-element__label",
            "span.jobs-easy-apply-form-section__title",
            "h3",
            "legend",
            "[data-test-form-element-label]",
        ]

        for selector in label_selectors:
            label = container.query_selector(selector)
            if label:
                text = label.inner_text().strip()
                if text:
                    return text

        # Fallback: use the container's own text if short enough
        text = container.inner_text().strip()
        if text and len(text) < 200:
            return text.split("\n")[0].strip()

        return None

    def _identify_question_type(self, container: ElementHandle) -> QuestionType:
        """
        Determine the type of a form field.

        Args:
            container: The field container element.

        Returns:
            QuestionType enum value.
        """
        # File upload
        if container.query_selector("input[type='file']"):
            return QuestionType.FILE_UPLOAD

        # Select dropdown
        if container.query_selector("select"):
            return QuestionType.DROPDOWN

        # Radio buttons
        if container.query_selector("input[type='radio']"):
            return QuestionType.RADIO

        # Checkboxes
        if container.query_selector("input[type='checkbox']"):
            return QuestionType.CHECKBOX

        # Date input
        if container.query_selector("input[type='date']"):
            return QuestionType.DATE

        # Number input
        if container.query_selector("input[type='number']"):
            return QuestionType.NUMERIC

        # Textarea
        if container.query_selector("textarea"):
            return QuestionType.TEXT

        # Text input (default)
        if container.query_selector("input[type='text'], input:not([type])"):
            return QuestionType.TEXT

        return QuestionType.TEXT

    def _extract_options(self, container: ElementHandle) -> List[str]:
        """
        Extract dropdown/radio/checkbox options from a container.

        Args:
            container: The field container element.

        Returns:
            List of option text strings.
        """
        options: List[str] = []

        # Select dropdown options
        select = container.query_selector("select")
        if select:
            option_elements = select.query_selector_all("option")
            for opt in option_elements:
                text = opt.inner_text().strip()
                if text and text != "Select..." and text != "Choose an option":
                    options.append(text)
            return options

        # Radio button labels
        radio_labels = container.query_selector_all("label")
        for label in radio_labels:
            text = label.inner_text().strip()
            if text and len(text) < 200:
                options.append(text)

        # Checkbox labels (same selector, filtered by context)
        if not options:
            spans = container.query_selector_all("span")
            for span in spans:
                text = span.inner_text().strip()
                if text and 2 < len(text) < 200:
                    options.append(text)

        return options

    def _is_required(self, container: ElementHandle) -> bool:
        """
        Check if a field is marked as required.

        Args:
            container: The field container element.

        Returns:
            True if the field appears to be required.
        """
        # Check for required attribute on inputs
        required_input = container.query_selector(
            "input[required], select[required], textarea[required]"
        )
        if required_input:
            return True

        # Check for required indicator in label
        label = container.query_selector("label")
        if label:
            text = label.inner_text()
            if "*" in text or "required" in text.lower():
                return True

        # Check for aria-required
        aria_elem = container.query_selector("[aria-required='true']")
        if aria_elem:
            return True

        return False

    def _get_field_selector(
        self, container: ElementHandle, question_type: QuestionType
    ) -> Optional[str]:
        """
        Get a CSS selector for Playwright interaction with a field.

        Args:
            container: The field container.
            question_type: Type of the question.

        Returns:
            CSS selector string, or None.
        """
        selectors_map = {
            QuestionType.TEXT: "input[type='text'], input:not([type]), textarea",
            QuestionType.DROPDOWN: "select",
            QuestionType.RADIO: "input[type='radio']",
            QuestionType.CHECKBOX: "input[type='checkbox']",
            QuestionType.DATE: "input[type='date']",
            QuestionType.NUMERIC: "input[type='number']",
            QuestionType.FILE_UPLOAD: "input[type='file']",
        }

        selector = selectors_map.get(question_type)
        if selector:
            element = container.query_selector(selector)
            if element:
                # Try to get a unique selector
                element_id = element.get_attribute("id")
                if element_id:
                    return f"#{element_id}"

                name = element.get_attribute("name")
                if name:
                    return f"[name='{name}']"

                return selector

        return None

    def _get_placeholder(
        self, container: ElementHandle, question_type: QuestionType
    ) -> Optional[str]:
        """
        Get placeholder text from a form field.

        Args:
            container: The field container.
            question_type: Type of the question.

        Returns:
            Placeholder text, or None.
        """
        if question_type in (QuestionType.TEXT, QuestionType.NUMERIC):
            input_elem = container.query_selector("input, textarea")
            if input_elem:
                return input_elem.get_attribute("placeholder")
        return None

    def _scan_for_fields(self, page: Page) -> List[FormQuestion]:
        """
        Fallback: scan the modal for any recognizable form fields.

        Args:
            page: Playwright page.

        Returns:
            List of detected FormQuestion objects.
        """
        questions: List[FormQuestion] = []

        # Find all input-like elements within the modal
        for modal_selector in self.MODAL_SELECTORS:
            modal = page.query_selector(modal_selector)
            if not modal:
                continue

            inputs = modal.query_selector_all(
                "input:not([type='hidden']), select, textarea"
            )
            for inp in inputs:
                input_type = inp.get_attribute("type") or "text"
                input_id = inp.get_attribute("id") or ""
                input_name = inp.get_attribute("name") or ""

                # Try to find associated label
                label_text = ""
                if input_id:
                    label = page.query_selector(f"label[for='{input_id}']")
                    if label:
                        label_text = label.inner_text().strip()

                if not label_text and input_name:
                    label_text = input_name.replace("_", " ").replace("-", " ").title()

                if not label_text:
                    continue

                q_type = QuestionType.TEXT
                if input_type == "radio":
                    q_type = QuestionType.RADIO
                elif input_type == "checkbox":
                    q_type = QuestionType.CHECKBOX
                elif input_type == "number":
                    q_type = QuestionType.NUMERIC
                elif input_type == "date":
                    q_type = QuestionType.DATE
                elif input_type == "file":
                    q_type = QuestionType.FILE_UPLOAD
                elif inp.evaluate("el => el.tagName") == "SELECT":
                    q_type = QuestionType.DROPDOWN
                elif inp.evaluate("el => el.tagName") == "TEXTAREA":
                    q_type = QuestionType.TEXT

                selector = f"#{input_id}" if input_id else f"[name='{input_name}']"

                questions.append(
                    FormQuestion(
                        question_text=label_text,
                        question_type=q_type,
                        field_selector=selector,
                    )
                )

            break  # Only use first matching modal

        return questions

    def _has_resume_upload(self, page: Page) -> bool:
        """
        Check if the current step has a resume upload field.

        Args:
            page: Playwright page.

        Returns:
            True if resume upload is detected.
        """
        for selector in self.MODAL_SELECTORS:
            modal = page.query_selector(selector)
            if modal:
                resume_input = modal.query_selector(
                    "input[type='file'][accept*='.pdf'], "
                    "input[type='file'][accept*='.doc'], "
                    "input[data-test-resume-upload]"
                )
                return resume_input is not None
        return False

    def _has_cover_letter_field(self, page: Page) -> bool:
        """
        Check if the current step has a cover letter field.

        Args:
            page: Playwright page.

        Returns:
            True if cover letter field is detected.
        """
        for selector in self.MODAL_SELECTORS:
            modal = page.query_selector(selector)
            if modal:
                cl_textarea = modal.query_selector(
                    "textarea[name*='cover'], textarea[placeholder*='cover']"
                )
                return cl_textarea is not None
        return False

    def _has_element(self, page: Page, selectors: List[str]) -> bool:
        """
        Check if any of the given selectors match an element.

        Args:
            page: Playwright page.
            selectors: List of CSS selectors to try.

        Returns:
            True if any selector matches a visible element.
        """
        for selector in selectors:
            elem = page.query_selector(selector)
            if elem and elem.is_visible():
                return True
        return False

    def _click_element(self, page: Page, selectors: List[str]) -> bool:
        """
        Click the first matching element from a list of selectors.

        Dismisses any overlaying dialogs before clicking. Falls back to
        force click if a normal click is intercepted.

        Args:
            page: Playwright page.
            selectors: List of CSS selectors to try.

        Returns:
            True if an element was clicked.
        """
        self._dismiss_overlays(page)

        for selector in selectors:
            try:
                elem = page.query_selector(selector)
                if elem and elem.is_visible():
                    try:
                        elem.click(timeout=5000)
                        return True
                    except Exception:
                        # Overlay blocking - try force click
                        try:
                            elem.click(force=True, timeout=5000)
                            return True
                        except Exception:
                            continue
            except Exception:
                continue
        return False

    def _dismiss_overlays(self, page: Page) -> None:
        """
        Dismiss overlaying dialogs (cookie consent, notifications).

        Args:
            page: Playwright page.
        """
        overlay_dismiss_selectors = [
            "div[data-testid='interop-shadowdom'] button",
            "button[action-type='ACCEPT']",
            "button:has-text('Accept')",
            "button:has-text('Dismiss')",
            "button:has-text('Got it')",
            "button[aria-label='Dismiss']",
            "button[aria-label='Close']",
        ]
        for sel in overlay_dismiss_selectors:
            try:
                elem = page.query_selector(sel)
                if elem and elem.is_visible():
                    elem.click(force=True, timeout=2000)
                    page.wait_for_timeout(500)
            except Exception:
                continue

    def _close_modal(self, page: Page) -> None:
        """
        Close the Easy Apply modal.

        Args:
            page: Playwright page.
        """
        self._click_element(page, self.CLOSE_BUTTON_SELECTORS)
        page.wait_for_timeout(500)
