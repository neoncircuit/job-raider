"""
Job Raider - Easy Apply Form Filler

Automates filling and submitting LinkedIn Easy Apply forms using Playwright,
combining form parsing, question answering, and browser automation.

Author: Job Raider
Date: 2026-05-04
"""

import random
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from playwright.sync_api import Page

from ..submission.applied_tracker import AppliedJobsTracker
from ..utils.logger import Components, get_logger
from .answer_engine import QuestionAnswerEngine
from .form_models import (
    AnswerConfidence,
    FormFillResult,
    FormQuestion,
    QuestionAnswer,
    QuestionType,
)
from .form_parser import EasyApplyFormParser
from .safety import SafetyController
from .session import LinkedInSession


class EasyApplyFormFiller:
    """
    Automate filling and submitting LinkedIn Easy Apply forms.

    Coordinates form parsing, answer generation, and Playwright
    interaction to complete the entire Easy Apply flow for a single job.
    """

    # Selectors for the Easy Apply flow
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

    DISMISS_BUTTON_SELECTORS = [
        "button[aria-label='Dismiss']",
        "button:has-text('Done')",
        "button:has-text('Go to jobs page')",
    ]

    CONFIRMATION_SELECTORS = [
        "div.jobs-easy-apply-success",
        "span:has-text('Application submitted')",
        "div:has-text('Your application was sent')",
    ]

    def __init__(
        self,
        session: LinkedInSession,
        answer_engine: QuestionAnswerEngine,
        safety_controller: Optional[SafetyController] = None,
        screenshot_dir: str = "data/screenshots",
        semi_auto: bool = False,
    ) -> None:
        """
        Initialize the form filler.

        Args:
            session: Authenticated LinkedIn session.
            answer_engine: Engine for generating answers to form questions.
            safety_controller: Rate limiting controller.
            screenshot_dir: Directory for saving screenshots.
            semi_auto: If True, pause before submission for manual review.
        """
        self.session = session
        self.engine = answer_engine
        self.safety = safety_controller or SafetyController()
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.semi_auto = semi_auto
        self.parser = EasyApplyFormParser()
        self.tracker = AppliedJobsTracker()
        self.logger = get_logger(Components.SUBMISSION)

    def apply_to_job(
        self,
        job_id: str,
        job_title: str,
        company: str,
    ) -> FormFillResult:
        """
        Complete the Easy Apply flow for a single job.

        Navigates to the job, parses the form, generates answers,
        fills all fields, and submits the application.

        Args:
            job_id: LinkedIn job ID.
            job_title: Job title for logging and tracking.
            company: Company name for logging and tracking.

        Returns:
            FormFillResult with success status and details.
        """
        result = FormFillResult(
            job_id=job_id,
            job_title=job_title,
            company=company,
        )

        try:
            # Safety check
            if not self.safety.can_apply():
                result.error_message = "Safety limit reached, cannot apply"
                result.success = False
                return result

            # Navigate to the job
            page = self.session.navigate_to_job(job_id)
            time.sleep(random.uniform(2, 4))

            # Take pre-application screenshot
            result.screenshot_paths.append(
                str(self._take_screenshot(page, f"pre_apply_{job_id}"))
            )

            # Click Easy Apply button
            if not self._click_element(page, self.EASY_APPLY_BUTTON_SELECTORS):
                result.error_message = "Easy Apply button not found"
                result.success = False
                return result

            page.wait_for_timeout(2000)

            # Fill form step by step
            total_answered = 0
            total_skipped = 0
            low_confidence: List[QuestionAnswer] = []
            steps_completed = 0

            while True:
                steps_completed += 1

                # Parse current step
                questions = self._parse_visible_fields(page)

                if questions:
                    # Generate answers
                    answers = [self.engine.answer_question(q) for q in questions]

                    # Fill each field
                    for answer in answers:
                        if (
                            answer.answer_value
                            and answer.confidence != AnswerConfidence.UNKNOWN
                        ):
                            filled = self._fill_field(page, answer)
                            if filled:
                                total_answered += 1
                            else:
                                total_skipped += 1
                        else:
                            total_skipped += 1

                        if answer.confidence in (
                            AnswerConfidence.LOW,
                            AnswerConfidence.UNKNOWN,
                        ):
                            low_confidence.append(answer)

                # Take step screenshot
                result.screenshot_paths.append(
                    str(self._take_screenshot(page, f"step_{steps_completed}_{job_id}"))
                )

                # Check for Next/Review/Submit buttons
                has_next = self._has_element(page, self.NEXT_BUTTON_SELECTORS)
                has_review = self._has_element(page, self.REVIEW_BUTTON_SELECTORS)
                has_submit = self._has_element(page, self.SUBMIT_BUTTON_SELECTORS)

                if has_submit:
                    # Final step - submit
                    break
                elif has_review:
                    self._click_element(page, self.REVIEW_BUTTON_SELECTORS)
                    page.wait_for_timeout(1500)
                    break
                elif has_next:
                    self._click_element(page, self.NEXT_BUTTON_SELECTORS)
                    page.wait_for_timeout(random.uniform(1500, 3000))
                else:
                    # No navigation buttons found - try submitting
                    break

                # Safety limit on steps
                if steps_completed >= 10:
                    self.logger.warning(f"Too many steps ({steps_completed}), stopping")
                    break

            # Semi-auto mode: pause for manual review
            if self.semi_auto:
                self.logger.info(
                    f"SEMI-AUTO MODE: Pausing before submit for {job_title} at {company}. "
                    f"Review the browser and press Enter in console to continue..."
                )
                input("Press Enter to submit or Ctrl+C to cancel...")

            # Take pre-submit screenshot
            result.screenshot_paths.append(
                str(self._take_screenshot(page, f"pre_submit_{job_id}"))
            )

            # Click Submit
            submit_clicked = self._click_element(page, self.SUBMIT_BUTTON_SELECTORS)
            if not submit_clicked:
                # Try review first then submit
                self._click_element(page, self.REVIEW_BUTTON_SELECTORS)
                page.wait_for_timeout(1500)
                submit_clicked = self._click_element(page, self.SUBMIT_BUTTON_SELECTORS)

            if submit_clicked:
                page.wait_for_timeout(3000)

                # Verify submission
                submitted = self._verify_submission(page)

                if submitted:
                    result.success = True
                    result.submission_timestamp = datetime.now()
                    self.safety.record_application()
                    self.tracker.mark_applied(job_id, job_title, company)
                    self.logger.info(
                        f"Successfully applied to {job_title} at {company}"
                    )
                else:
                    result.success = False
                    result.error_message = "Could not confirm submission"
                    self.logger.warning(
                        f"Could not confirm submission for {job_title} at {company}"
                    )
            else:
                result.success = False
                result.error_message = "Submit button not found or not clickable"

            # Take post-submit screenshot
            result.screenshot_paths.append(
                str(self._take_screenshot(page, f"post_submit_{job_id}"))
            )

            # Dismiss confirmation dialog
            self._click_element(page, self.DISMISS_BUTTON_SELECTORS)

            result.steps_completed = steps_completed
            result.questions_answered = total_answered
            result.questions_skipped = total_skipped
            result.low_confidence_answers = low_confidence

            return result

        except Exception as e:
            self.logger.error(f"Error applying to {job_title} at {company}: {e}")
            result.error_message = str(e)
            result.success = False
            return result

    def _parse_visible_fields(self, page: Page) -> List[FormQuestion]:
        """
        Parse form fields currently visible in the modal.

        Args:
            page: Playwright page.

        Returns:
            List of detected FormQuestion objects.
        """
        return self.parser._scan_for_fields(page)

    def _fill_field(self, page: Page, answer: QuestionAnswer) -> bool:
        """
        Fill a single form field based on question type.

        Args:
            page: Playwright page.
            answer: The answer to fill in.

        Returns:
            True if the field was filled successfully.
        """
        question = answer.question
        selector = question.field_selector

        if not selector:
            self.logger.debug(f"No selector for question: {question.question_text}")
            return False

        try:
            if question.question_type == QuestionType.TEXT:
                return self._fill_text_field(page, selector, answer.answer_value)
            elif question.question_type == QuestionType.DROPDOWN:
                return self._select_dropdown(
                    page, selector, answer.answer_value, question.options
                )
            elif question.question_type == QuestionType.RADIO:
                return self._click_radio(
                    page, selector, answer.answer_value, question.options
                )
            elif question.question_type == QuestionType.CHECKBOX:
                return self._check_checkbox(page, selector, answer.answer_value)
            elif question.question_type == QuestionType.DATE:
                return self._fill_text_field(page, selector, answer.answer_value)
            elif question.question_type == QuestionType.NUMERIC:
                return self._fill_text_field(page, selector, answer.answer_value)
            else:
                self.logger.debug(
                    f"Unsupported question type: {question.question_type}"
                )
                return False
        except Exception as e:
            self.logger.warning(f"Failed to fill field '{question.question_text}': {e}")
            return False

    def _fill_text_field(self, page: Page, selector: str, value: str) -> bool:
        """
        Fill a text input or textarea.

        Args:
            page: Playwright page.
            selector: CSS selector for the input.
            value: Value to type.

        Returns:
            True if filled successfully.
        """
        element = page.query_selector(selector)
        if not element:
            return False

        element.click()
        element.fill("")
        element.type(value, delay=random.randint(30, 80))
        return True

    def _select_dropdown(
        self, page: Page, selector: str, value: str, options: List[str]
    ) -> bool:
        """
        Select a value from a dropdown using fuzzy matching.

        Args:
            page: Playwright page.
            selector: CSS selector for the select element.
            value: Target value to select.
            options: Available options in the dropdown.

        Returns:
            True if an option was selected.
        """
        element = page.query_selector(selector)
        if not element:
            return False

        # Try exact match first
        matched = self._fuzzy_match(value, options)
        if matched:
            element.select_option(label=matched)
            return True

        # Try clicking the select and then the option
        element.click()
        page.wait_for_timeout(500)
        for option in options:
            if self._fuzzy_match(value, [option]):
                option_elem = page.query_selector(f"option:has-text('{option}')")
                if option_elem:
                    option_elem.click()
                    return True

        return False

    def _click_radio(
        self, page: Page, selector: str, value: str, options: List[str]
    ) -> bool:
        """
        Click the appropriate radio button.

        Args:
            page: Playwright page.
            selector: CSS selector for the radio group.
            value: Target value.
            options: Available radio options.

        Returns:
            True if a radio was clicked.
        """
        matched = self._fuzzy_match(value, options)
        if matched:
            # Try finding the label that contains the matched text
            label = page.query_selector(f"label:has-text('{matched}')")
            if label:
                label.click()
                return True

        # Try boolean yes/no matching
        value_lower = value.lower().strip()
        if value_lower in ("yes", "true", "1"):
            yes_radio = page.query_selector(
                "input[type='radio'][value='Yes'], "
                "input[type='radio'][value='yes'], "
                "label:has-text('Yes')"
            )
            if yes_radio:
                yes_radio.click()
                return True
        elif value_lower in ("no", "false", "0"):
            no_radio = page.query_selector(
                "input[type='radio'][value='No'], "
                "input[type='radio'][value='no'], "
                "label:has-text('No')"
            )
            if no_radio:
                no_radio.click()
                return True

        return False

    def _check_checkbox(self, page: Page, selector: str, value: str) -> bool:
        """
        Check or uncheck a checkbox.

        Args:
            page: Playwright page.
            selector: CSS selector for the checkbox.
            value: "Yes"/"True" to check, anything else to uncheck.

        Returns:
            True if the checkbox state was set.
        """
        element = page.query_selector(selector)
        if not element:
            return False

        should_check = value.lower().strip() in ("yes", "true", "1", "on")
        is_checked = element.is_checked()

        if should_check != is_checked:
            element.click()
            return True

        return True  # Already in correct state

    def _verify_submission(self, page: Page) -> bool:
        """
        Verify that the application was successfully submitted.

        Args:
            page: Playwright page after clicking submit.

        Returns:
            True if submission confirmation is detected.
        """
        for selector in self.CONFIRMATION_SELECTORS:
            elem = page.query_selector(selector)
            if elem:
                return True

        # Check if "Applied" badge appeared
        page_text = page.inner_text("body")
        if "application was sent" in page_text.lower():
            return True
        if "applied" in page_text.lower() and "already" not in page_text.lower():
            return True

        return False

    def _take_screenshot(self, page: Page, name: str) -> Path:
        """
        Capture a screenshot for audit trail.

        Args:
            page: Playwright page.
            name: Screenshot name.

        Returns:
            Path to the saved screenshot.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.screenshot_dir / f"{name}_{timestamp}.png"
        try:
            page.screenshot(path=str(path), full_page=False)
        except Exception:
            pass
        return path

    def _has_element(self, page: Page, selectors: List[str]) -> bool:
        """
        Check if any of the given selectors match a visible element.

        Args:
            page: Playwright page.
            selectors: List of CSS selectors to try.

        Returns:
            True if any selector matches.
        """
        for selector in selectors:
            elem = page.query_selector(selector)
            if elem and elem.is_visible():
                return True
        return False

    def _click_element(self, page: Page, selectors: List[str]) -> bool:
        """
        Click the first matching element from a list of selectors.

        Dismisses overlays before clicking and falls back to force click.

        Args:
            page: Playwright page.
            selectors: List of CSS selectors to try.

        Returns:
            True if an element was clicked.
        """
        # Dismiss any overlaying dialogs first
        for sel in [
            "div[data-testid='interop-shadowdom'] button",
            "button:has-text('Accept')",
            "button:has-text('Dismiss')",
            "button:has-text('Got it')",
            "button[aria-label='Dismiss']",
        ]:
            try:
                elem = page.query_selector(sel)
                if elem and elem.is_visible():
                    elem.click(force=True, timeout=2000)
                    page.wait_for_timeout(300)
            except Exception:
                continue

        for selector in selectors:
            try:
                elem = page.query_selector(selector)
                if elem and elem.is_visible():
                    try:
                        elem.click(timeout=5000)
                        return True
                    except Exception:
                        try:
                            elem.click(force=True, timeout=5000)
                            return True
                        except Exception:
                            continue
            except Exception:
                continue
        return False

    @staticmethod
    def _fuzzy_match(target: str, options: List[str]) -> Optional[str]:
        """
        Find the best matching option for a target value.

        Args:
            target: The desired value.
            options: Available options.

        Returns:
            Best matching option, or None.
        """
        target_lower = target.lower().strip()

        # Exact match
        for opt in options:
            if opt.lower().strip() == target_lower:
                return opt

        # Contains match
        for opt in options:
            if target_lower in opt.lower() or opt.lower() in target_lower:
                return opt

        # Keyword match
        target_words = set(target_lower.split())
        best_match = None
        best_score = 0

        for opt in options:
            opt_words = set(opt.lower().split())
            overlap = len(target_words & opt_words)
            if overlap > best_score:
                best_score = overlap
                best_match = opt

        return best_match if best_score > 0 else None
