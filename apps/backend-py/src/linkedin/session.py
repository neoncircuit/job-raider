"""
Job Raider - LinkedIn Session Manager

Manages an authenticated Playwright browser session for LinkedIn,
with cookie persistence and anti-bot measures.

Author: Job Raider
Date: 2026-05-04
"""

import json
import random
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)
from pydantic import BaseModel, Field

from ..utils.logger import Components, get_logger


class LinkedInSessionConfig(BaseModel):
    """Configuration for a LinkedIn browser session."""

    email: str = Field(description="LinkedIn account email")
    password: str = Field(description="LinkedIn account password")
    headless: bool = Field(default=True, description="Run browser in headless mode")
    cookie_path: str = Field(
        default="data/linkedin_session/cookies.json",
        description="Path to persist session cookies",
    )
    timeout_ms: int = Field(default=30000, description="Page navigation timeout in ms")
    slow_mo_ms: int = Field(
        default=100,
        description="Slows down Playwright operations by the specified ms",
    )
    user_data_dir: Optional[str] = Field(
        default="data/linkedin_session/browser_data",
        description="Persistent browser data directory (localStorage, indexedDB)",
    )


class LinkedInSession:
    """
    Manages an authenticated Playwright browser session for LinkedIn.

    Uses persistent browser contexts to maintain cookies, localStorage,
    and session state across runs. Handles login flow including detection
    of 2FA prompts and CAPTCHAs.
    """

    LOGIN_URL = "https://www.linkedin.com/login"
    FEED_URL = "https://www.linkedin.com/feed/"
    JOBS_BASE_URL = "https://www.linkedin.com/jobs/view/"

    _USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]

    def __init__(self, config: LinkedInSessionConfig) -> None:
        """
        Initialize the LinkedIn session manager.

        Args:
            config: Session configuration including credentials.
        """
        self.config = config
        self.logger = get_logger(Components.SCRAPERS)
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._is_authenticated = False

    @property
    def is_authenticated(self) -> bool:
        """
        Check if the session is currently authenticated.

        Returns:
            True if the session has been authenticated and is active.
        """
        return self._is_authenticated and self._context is not None

    def start(self) -> bool:
        """
        Launch browser and establish an authenticated session.

        Attempts to restore a previous session from persistent context data
        or saved cookies. If both fail, performs a fresh login.

        Returns:
            True if authentication succeeded.
        """
        try:
            self._launch_browser()

            # First check: persistent context may already have a valid session
            self._page.goto(self.FEED_URL, timeout=self.config.timeout_ms)
            time.sleep(2)

            if self._verify_session():
                self.logger.info("Restored LinkedIn session from persistent context")
                self._save_cookies()
                self._is_authenticated = True
                return True

            # Second check: try loading saved cookies
            if self._load_cookies():
                self._page.goto(self.FEED_URL, timeout=self.config.timeout_ms)
                time.sleep(2)

                if self._verify_session():
                    self.logger.info("Restored LinkedIn session from saved cookies")
                    self._is_authenticated = True
                    return True

            self.logger.info("Could not restore session, performing fresh login")
            return self.login()

        except Exception as e:
            self.logger.error(f"Failed to start LinkedIn session: {e}")
            return False

    def login(self) -> bool:
        """
        Perform LinkedIn login flow.

        Navigates to login page, fills credentials, and handles
        2FA/CAPTCHA detection.

        Returns:
            True if login succeeded.
        """
        if not self._page:
            self._launch_browser()

        try:
            self._page.goto(self.LOGIN_URL, timeout=self.config.timeout_ms)
            time.sleep(random.uniform(1, 2))

            # Debug: capture what page actually loaded
            current_url = self._page.url
            self.logger.info(f"Login page loaded: {current_url}")

            # Check if already logged in (session restore from persistent context)
            if "/feed/" in current_url or "/in/" in current_url:
                if self._verify_session():
                    self.logger.info("Already logged in from persistent session")
                    self._save_cookies()
                    self._is_authenticated = True
                    return True

            # Only proceed with login form if still on login page
            if "/login" not in current_url and "/checkpoint" not in current_url:
                self.logger.warning(f"Unexpected redirect during login: {current_url}")
                self.screenshot("login_unexpected_redirect")
                return False

            # Fill email (LinkedIn's current flow uses various methods)
            # Try standard selectors first, then use locator-based approach
            email_selectors = [
                "#username",
                "input[name='session_key']:not([type='hidden'])",
                "input[type='text'][autocomplete='username']",
                "input#session_key:not([type='hidden'])",
                "input[type='email']",
            ]
            email_input = None
            for sel in email_selectors:
                try:
                    email_input = self._page.wait_for_selector(sel, timeout=3000)
                    if email_input and email_input.is_visible():
                        self.logger.info(f"Found email field with selector: {sel}")
                        break
                    else:
                        email_input = None
                except Exception:
                    continue

            # Fallback: use Playwright locator (handles shadow DOM, React components)
            if not email_input:
                try:
                    email_input = self._page.get_by_role("textbox").first
                    if email_input and email_input.is_visible():
                        self.logger.info("Found email field via role locator")
                except Exception:
                    pass

            # Fallback: try setting the hidden session_key directly via JS
            if not email_input:
                try:
                    hidden_key = self._page.query_selector("input[name='session_key']")
                    if hidden_key:
                        self.logger.info(
                            "Using hidden session_key input via JS injection"
                        )
                        self._page.evaluate(f"""() => {{
                                const input = document.querySelector("input[name='session_key']");
                                if (input) {{
                                    input.type = 'text';
                                    input.value = '{self.config.email}';
                                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                }}
                            }}""")
                        email_input = hidden_key
                except Exception:
                    pass

            if not email_input:
                self.logger.error("Could not find email input field")
                self.screenshot("login_no_email_field")
                return False

            if email_input:
                email_input.fill("")
                email_input.type(self.config.email, delay=random.randint(50, 100))

            # Fill password
            password_input = (
                self._page.query_selector("#password")
                or self._page.query_selector("input[name='session_password']")
                or self._page.query_selector("input[type='password']")
            )
            if password_input and password_input.is_visible():
                password_input.fill("")
                password_input.type(self.config.password, delay=random.randint(50, 100))

            # Click sign in
            sign_in_btn = self._page.query_selector("button[type='submit']")
            if sign_in_btn:
                sign_in_btn.click()

            # Wait for navigation with fallback
            try:
                self._page.wait_for_url("**/feed/**", timeout=self.config.timeout_ms)
            except Exception:
                # Feed URL not reached - could be 2FA, CAPTCHA, or error
                pass

            time.sleep(random.uniform(2, 4))

            current_url = self._page.url

            # Check for 2FA
            if "challenge" in current_url or self._page.query_selector(
                "#input__phone_verification_pin"
            ):
                self.logger.warning(
                    "LinkedIn 2FA detected. Manual intervention may be required. "
                    "Complete the verification in the browser window."
                )
                if self.config.headless:
                    self.logger.error(
                        "Cannot handle 2FA in headless mode. "
                        "Set headless=False in config and try again."
                    )
                    return False

                # Wait up to 2 minutes for manual 2FA completion
                for _ in range(120):
                    time.sleep(1)
                    if self._verify_session():
                        self.logger.info("2FA completed successfully")
                        self._save_cookies()
                        self._is_authenticated = True
                        return True

                self.logger.error("2FA verification timed out")
                return False

            # Check for CAPTCHA
            captcha_frame = self._page.query_selector("iframe[src*='challenge']")
            if captcha_frame:
                self.logger.warning(
                    "LinkedIn CAPTCHA detected. Manual intervention may be required."
                )
                if self.config.headless:
                    self.logger.error(
                        "Cannot solve CAPTCHA in headless mode. "
                        "Set headless=False and try again."
                    )
                    return False

            # Check for login errors
            error_elem = self._page.query_selector(
                ".form__label--error, #error-for-username, #error-for-password"
            )
            if error_elem:
                error_text = error_elem.inner_text()
                self.logger.error(f"LinkedIn login failed: {error_text}")
                return False

            # Verify successful login
            if self._verify_session():
                self._save_cookies()
                self._is_authenticated = True
                self.logger.info("LinkedIn login successful")
                return True

            self.logger.error("Login verification failed")
            return False

        except Exception as e:
            self.logger.error(f"LinkedIn login error: {e}")
            return False

    def get_page(self) -> Page:
        """
        Return the active browser page for interaction.

        Returns:
            The current Playwright Page object.

        Raises:
            RuntimeError: If no active browser session.
        """
        if not self._page:
            raise RuntimeError("No active browser session. Call start() first.")
        return self._page

    def navigate_to_job(self, job_id: str) -> Page:
        """
        Navigate to a specific LinkedIn job listing page.

        Args:
            job_id: LinkedIn job ID.

        Returns:
            The page after navigation.

        Raises:
            RuntimeError: If no active session.
        """
        if not self._page:
            raise RuntimeError("No active session. Call start() first.")

        url = f"{self.JOBS_BASE_URL}{job_id}"
        self._page.goto(url, timeout=self.config.timeout_ms)
        time.sleep(random.uniform(1, 2))
        return self._page

    def navigate_to_url(self, url: str) -> Page:
        """
        Navigate to an arbitrary LinkedIn URL.

        Args:
            url: Fully qualified LinkedIn URL.

        Returns:
            The page after navigation.

        Raises:
            RuntimeError: If no active session.
        """
        if not self._page:
            raise RuntimeError("No active session. Call start() first.")

        self._page.goto(url, timeout=self.config.timeout_ms)
        time.sleep(random.uniform(1, 2))
        return self._page

    def fetch_profile_text(self, profile_url: str) -> str:
        """
        Navigate to a LinkedIn profile and extract visible text content.

        Args:
            profile_url: LinkedIn profile URL.

        Returns:
            Extracted visible text from the profile page, or an empty string
            if the content cannot be retrieved.
        """
        if not self._page:
            raise RuntimeError("No active session. Call start() first.")

        page = self.navigate_to_url(profile_url)
        try:
            page.wait_for_selector(
                "main.scaffold-layout__main, main, section.artdeco-card",
                timeout=10000,
            )
        except Exception:
            pass

        selectors = [
            "main.scaffold-layout__main",
            "main",
            "section.artdeco-card",
        ]
        for selector in selectors:
            try:
                elements = page.query_selector_all(selector)
            except Exception:
                continue
            for element in elements:
                try:
                    text = (element.inner_text() or "").strip()
                except Exception:
                    continue
                if text:
                    return text

        return page.inner_text("body") or ""

    def search_people(
        self,
        keywords: Optional[str] = None,
        name: Optional[str] = None,
        title: Optional[str] = None,
        company: Optional[str] = None,
        location: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search LinkedIn people and return result cards.

        Args:
            keywords: Free-form keywords.
            name: Person name.
            title: Job title.
            company: Company name.
            location: Location.
            limit: Maximum number of results to return.

        Returns:
            List of result dictionaries with name, headline, profile_url,
            and optional location.
        """
        if not self._page:
            raise RuntimeError("No active session. Call start() first.")

        terms = []
        if keywords:
            terms.append(keywords)
        if name:
            terms.append(name)
        if title:
            terms.append(title)
        if company:
            terms.append(company)
        if location:
            terms.append(location)

        query = " ".join(terms)
        encoded = urllib.parse.quote(query)
        url = f"https://www.linkedin.com/search/results/people/?keywords={encoded}"
        page = self.navigate_to_url(url)

        # Wait for result cards to render.
        try:
            page.wait_for_selector(
                ".search-result__info, .entity-result__content",
                timeout=self.config.timeout_ms,
            )
        except Exception:
            pass

        cards = page.query_selector_all(".search-result__info, .entity-result__content")
        results: List[Dict[str, Any]] = []
        for card in cards[:limit]:
            name_el = card.query_selector(
                ".app-aware-link span, .entity-result__title-text a"
            )
            link_el = card.query_selector("a.app-aware-link")
            headline_el = card.query_selector(
                ".entity-result__primary-subtitle, .search-result__truncate"
            )
            location_el = card.query_selector(".entity-result__secondary-subtitle")

            if not link_el:
                continue

            href = link_el.get_attribute("href") or ""
            if "/in/" not in href:
                continue

            results.append(
                {
                    "name": name_el.inner_text().strip() if name_el else "Unknown",
                    "headline": headline_el.inner_text().strip() if headline_el else "",
                    "profile_url": href.split("?")[0],
                    "location": (
                        location_el.inner_text().strip() if location_el else None
                    ),
                }
            )

        return results

    def screenshot(self, name: str) -> Path:
        """
        Capture a screenshot for debugging.

        Args:
            name: Descriptive name for the screenshot file.

        Returns:
            Path to the saved screenshot.
        """
        screenshot_dir = Path("data/screenshots")
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = screenshot_dir / f"{name}_{timestamp}.png"

        if self._page:
            self._page.screenshot(path=str(path), full_page=False)
            self.logger.debug(f"Screenshot saved: {path}")

        return path

    def verify_and_reconnect(self) -> bool:
        """
        Verify the session is still active and reconnect if needed.

        Returns:
            True if session is active.
        """
        if not self._page:
            return False

        try:
            self._page.goto(self.FEED_URL, timeout=self.config.timeout_ms)
            time.sleep(2)
            if self._verify_session():
                return True

            self.logger.info("Session expired, attempting re-login")
            return self.login()
        except Exception as e:
            self.logger.error(f"Session verification failed: {e}")
            return False

    def close(self) -> None:
        """Close browser and save session state."""
        try:
            if self._is_authenticated:
                self._save_cookies()
        except Exception:
            pass

        try:
            if self._context:
                self._context.close()
        except Exception:
            pass

        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass

        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass

        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._is_authenticated = False

    def _launch_browser(self) -> None:
        """Launch Playwright browser with persistent context."""
        self._playwright = sync_playwright().start()

        user_agent = random.choice(self._USER_AGENTS)
        viewport_width = random.randint(1280, 1920)
        viewport_height = random.randint(720, 1080)

        if self.config.user_data_dir:
            data_dir = Path(self.config.user_data_dir)
            data_dir.mkdir(parents=True, exist_ok=True)

            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(data_dir),
                headless=self.config.headless,
                slow_mo=self.config.slow_mo_ms,
                viewport={"width": viewport_width, "height": viewport_height},
                user_agent=user_agent,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            self._browser = None
        else:
            self._browser = self._playwright.chromium.launch(
                headless=self.config.headless,
                slow_mo=self.config.slow_mo_ms,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            self._context = self._browser.new_context(
                viewport={"width": viewport_width, "height": viewport_height},
                user_agent=user_agent,
            )

        self._page = self._context.new_page()

        # Remove webdriver detection
        self._page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

    def _save_cookies(self) -> None:
        """
        Persist browser cookies to disk.
        """
        if not self._context:
            return

        cookie_path = Path(self.config.cookie_path)
        cookie_path.parent.mkdir(parents=True, exist_ok=True)

        cookies = self._context.cookies()
        with open(cookie_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2)

        self.logger.debug(f"Saved {len(cookies)} cookies to {cookie_path}")

    def _load_cookies(self) -> bool:
        """
        Load cookies from disk into the browser context.

        Returns:
            True if cookies were loaded successfully.
        """
        cookie_path = Path(self.config.cookie_path)
        if not cookie_path.exists():
            return False

        try:
            with open(cookie_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)

            if not cookies:
                return False

            self._context.add_cookies(cookies)
            self.logger.debug(f"Loaded {len(cookies)} cookies from {cookie_path}")
            return True

        except (json.JSONDecodeError, OSError) as e:
            self.logger.warning(f"Failed to load cookies: {e}")
            return False

    def _verify_session(self) -> bool:
        """
        Verify the current session is authenticated by checking for the
        LinkedIn session cookie.

        Returns:
            True if a valid session is detected.
        """
        if not self._context:
            return False

        try:
            cookies = self._context.cookies()
            li_at = next((c for c in cookies if c["name"] == "li_at"), None)

            if li_at and not li_at.get("expires", 0) < time.time():
                return True

            # Fallback: check page content for auth indicators
            if self._page:
                url = self._page.url
                if "/feed/" in url or "/in/" in url or "/jobs/" in url:
                    login_wall = self._page.query_selector(
                        "form.login-form, div.authwall"
                    )
                    if not login_wall:
                        return True

            return False

        except Exception:
            return False
