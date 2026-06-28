# Job Raider - Manual Verification Checklist

## Overview

This checklist provides a comprehensive manual testing guide to verify all features work as intended. Use this checklist before releases, after major changes, or when troubleshooting issues.

**Date:** 2026-06-27
**Version:** Phase 44

---

## Section 1: Application Startup & Infrastructure

### Docker Services
- [ ] All Docker containers start successfully
  - Run: `docker compose up -d`
  - Verify: `docker compose ps` shows all services as "healthy"
- [ ] Backend container is healthy
  - Verify: `docker logs job-raider-backend` shows no errors
- [ ] Frontend container is healthy
  - Verify: `docker logs job-raider-frontend` shows no errors
- [ ] No container restart loops
  - Verify: Containers stay running without restart

### Environment Configuration
- [ ] `.env` file exists with required API keys
- [ ] API keys are valid and working
  - ANTHROPIC_API_KEY for Claude
  - RAPIDAPI_KEY for JSearch
- [ ] Backend responds to health check
  - Run: `curl http://localhost:8000/health`
  - Verify: Returns `{"status": "healthy"}`
- [ ] Frontend loads without errors
  - Navigate to: `http://localhost:3000`
  - Verify: Page loads, no console errors

---

## Section 2: Authentication & Authorization

### Authentication Status
- [ ] Authentication status is logged on backend startup
  - Run: `docker logs job-raider-backend`
  - Verify: See "Authentication ENABLED/DISABLED" message
- [ ] API calls work without auth in local dev mode
  - Verify: Job search works without API key in local mode
- [ ] API calls work with auth when API_KEY is set
  - Set API_KEY in .env
  - Run: `curl -H "X-API-Key: test" http://localhost:8000/api/jobs/search`
  - Verify: Returns 200 or appropriate error

---

## Section 3: Job Search Functionality

### Basic Search
- [ ] Jobs page loads successfully
  - Navigate to: `/jobs`
  - Verify: Search form is visible
- [ ] Can enter keywords in search field
  - Type: "Software Engineer"
  - Verify: Input accepts text
- [ ] Can enter location in search field
  - Type: "San Francisco, CA"
  - Verify: Input accepts text
- [ ] Search button is clickable
  - Verify: Button is enabled and clickable
- [ ] Search returns results
  - Submit search with valid keywords
  - Verify: Results appear or loading indicator shows

### Search Validation
- [ ] Empty keywords show validation error
  - Leave keywords blank, click Search
  - Verify: Error message appears or toast notification
- [ ] Validation error is user-friendly
  - Verify: Message says "keywords required" or similar
- [ ] Search works with whitespace-only keywords
  - Type: "   " (spaces)
  - Verify: Validation catches empty keywords

### Filters & Options
- [ ] Experience level filter works
  - Select: "Senior" from dropdown
  - Verify: Filter is applied
- [ ] Remote toggle works
  - Click: Remote checkbox
  - Verify: Toggle state changes
- [ ] Job source selection works
  - Select: LinkedIn, JSearch, or Both
  - Verify: Selection is applied
- [ ] Fresh grad mode toggle works
  - Click: Fresh Grad checkbox
  - Verify: Toggle state changes

### Search Results
- [ ] Job cards display correctly
  - Verify: Title, company, location are visible
- [ ] Job details are accessible
  - Click: View Details on a job
  - Verify: Details modal/page opens
- [ ] Can save a job
  - Click: Save button on a job
  - Verify: Job is marked as saved
- [ ] Can hide a job
  - Click: Hide button on a job
  - Verify: Job is hidden from results
- [ ] Scam scores display correctly
  - Verify: Scam score badge shows (green/yellow/red)
- [ ] Relevance scores display correctly
  - Verify: Score percentage or bar shows

---

## Section 4: Job Details & Actions

### Job Information
- [ ] Job title displays correctly
  - Verify: Title matches job listing
- [ ] Company information displays
  - Verify: Company name is visible
- [ ] Job description is formatted
  - Verify: Description is readable, HTML is rendered
- [ ] Salary range displays
  - Verify: Salary range is shown if available
- [ ] Required skills are listed
  - Verify: Skills section shows required skills

### Job Actions
- [ ] Can mark job as applied externally
  - Click: Mark Applied button
  - Verify: Job status changes to "Applied"
- [ ] Can add notes to job
  - Click: Add Notes
  - Type: Test note
  - Verify: Note is saved
- [ ] Can generate cover letter
  - Click: Generate Cover Letter
  - Verify: Cover letter is generated
- [ ] Can view job source
  - Verify: LinkedIn/JSearch/Google indicator shows

---

## Section 5: Application Tracking

### Dashboard Overview
- [ ] Dashboard loads successfully
  - Navigate to: `/dashboard`
  - Verify: Dashboard displays
- [ ] Statistics display correctly
  - Verify: Total applications count shows
  - Verify: Active applications count shows
  - Verify: Saved jobs count shows
- [ ] Recent applications list shows
  - Verify: Recent applications are listed
  - Verify: Each application shows status
- [ ] Quick action buttons work
  - Click: "Search Jobs" button
  - Verify: Navigates to jobs page

### Application Management
- [ ] Can view all applications
  - Navigate to: Applications section
  - Verify: All applications list shows
- [ ] Can filter applications by status
  - Select: "Applied" filter
  - Verify: List updates to show only applied jobs
- [ ] Can update application status
  - Click: Update Status on an application
  - Verify: Status changes successfully
- [ ] Can add notes to application
  - Click: Add Note
  - Type: Follow-up note
  - Verify: Note is saved
- [ ] Can hide application
  - Click: Hide application
  - Verify: Application is hidden from list

### Application Statuses
- [ ] All status types are available
  - Verify: Applied, Interviewing, Offer, Rejected, etc.
- [ ] Status badges display correctly
  - Verify: Color-coded badges show
- [ ] Can filter by multiple statuses
  - Select: Multiple status checkboxes
  - Verify: Filter works correctly

---

## Section 6: Profile Management

### Profile Viewing
- [ ] Profile page loads successfully
  - Navigate to: `/profile`
  - Verify: Profile displays
- [ ] Contact information shows
  - Verify: Name, email, phone are visible
- [ ] Skills section displays
  - Verify: Skills are listed with proficiency levels
- [ ] Experience section displays
  - Verify: Work experience is shown
- [ ] Education section displays
  - Verify: Education history is shown
- [ ] Projects section displays
  - Verify: Projects are listed with technologies

### Profile Editing
- [ ] Can edit contact information
  - Click: Edit on contact section
  - Update: Name or email
  - Verify: Changes are saved
- [ ] Can add/edit skills
  - Click: Add Skill
  - Enter: Skill name and proficiency
  - Verify: Skill is added to profile
- [ ] Can add/edit experience
  - Click: Add Experience
  - Fill: Job details
  - Verify: Experience is added to profile
- [ ] Can add/edit education
  - Click: Add Education
  - Fill: School and degree details
  - Verify: Education is added to profile
- [ ] Can upload resume
  - Click: Upload Resume
  - Select: PDF file
  - Verify: File is uploaded successfully

### Profile Visualizations
- [ ] Skills visualization displays
  - Verify: Skills chart or graph shows
- [ ] Experience timeline displays
  - Verify: Work experience timeline shows
- [ ] Profile completeness score shows
  - Verify: Completeness percentage displays
- [ ] Visualizations are interactive
  - Hover: Over charts
  - Verify: Tooltips or details show

---

### LinkedIn Profile Analysis

- [ ] LinkedIn Analysis page loads
  - Navigate to: `/linkedin-analysis`
  - Verify: Page displays with four tabs (LinkedIn URL, Search Profiles, Paste Profile Text, Fill Sections Manually)
- [ ] LinkedIn URL tab accepts a profile URL
  - Enter: `https://www.linkedin.com/in/janedoe`
  - Verify: URL is accepted and analyze button is enabled
- [ ] URL-based analysis fetches and analyzes profile text when credentials are configured
  - Submit: A valid LinkedIn profile URL
  - Verify: Analysis results load (overall score, section scores, insights)
- [ ] URL-based analysis falls back gracefully without credentials
  - Ensure: `LINKEDIN_EMAIL` and `LINKEDIN_PASSWORD` are not set
  - Submit: A LinkedIn profile URL with no other input
  - Verify: UI shows a service-unavailable or fallback message, or the request proceeds using only the provided text
- [ ] Search Profiles tab accepts search input
  - Fill: Keywords, name, title, company, or location
  - Verify: Input is accepted and search button is enabled
- [ ] People search returns selectable result cards when credentials are configured
  - Submit: A search with valid keywords
  - Verify: Result cards with name, headline, location, and profile URL appear
- [ ] Selecting a search result copies the URL into the URL tab
  - Click: Use this profile on a result card
  - Verify: The LinkedIn URL tab is active and the profile URL is filled in
- [ ] People search shows unavailable message without credentials
  - Ensure: `LINKEDIN_EMAIL` and `LINKEDIN_PASSWORD` are not set
  - Submit: Any people search
  - Verify: A 503 / unavailable message is shown
- [ ] Raw-text paste tab accepts input
  - Paste: Sample LinkedIn profile text
  - Verify: Input is accepted and analyze button is enabled
- [ ] Structured form tab accepts input
  - Fill: Headline, summary, experience, education, skills
  - Verify: Form fields accept input
- [ ] Analyze returns actionable results
  - Submit: Valid profile input
  - Verify: Overall score, section scores, and prioritized insights display
- [ ] JSON export button works
  - Click: Export JSON
  - Verify: JSON file downloads with analysis data
- [ ] Sidebar navigation item is visible
  - Verify: LinkedIn Analysis link appears in sidebar
- [ ] Mobile navigation item is visible
  - Set: Mobile viewport (375px width)
  - Verify: LinkedIn Analysis link appears in mobile menu

## Section 7: DISC Assessment

### Assessment Access
- [ ] Assessment page loads
  - Navigate to: `/assessment`
  - Verify: Assessment page displays
- [ ] Can start new assessment
  - Click: Start Assessment button
  - Verify: Assessment questions appear

### Assessment Questions
- [ ] Questions display one at a time
  - Verify: Single question shows per page
- [ ] Most/Least format works
  - Select: Most and Least options
  - Verify: Selection is recorded
- [ ] Can navigate questions
  - Click: Next/Previous buttons
  - Verify: Navigation works
- [ ] Progress indicator shows
  - Verify: Question progress displays (e.g., 5/20)

### Assessment Results
- [ ] Can submit assessment
  - Complete: All questions
  - Click: Submit
  - Verify: Results page appears
- [ ] Results display correctly
  - Verify: D, I, S, C scores show
  - Verify: Profile type displays (e.g., "Influencer")
- [ ] Can view job matches
  - Click: View Matching Jobs
  - Verify: Jobs that match profile show
- [ ] Results are saved
  - Navigate away and back to assessment
  - Verify: Previous results still show

---

## Section 8: Pipeline Automation

### Pipeline Access
- [ ] Pipeline page loads
  - Navigate to: `/pipeline`
  - Verify: Pipeline page displays
- [ ] Can configure pipeline
  - Set: Keywords, locations, sources
  - Set: Dry-run mode
  - Verify: Configuration options work

### Pipeline Execution
- [ ] Can start pipeline
  - Click: Start Pipeline button
  - Verify: Pipeline starts running
- [ ] Pipeline progress shows
  - Verify: Progress indicator updates
  - Verify: Current stage displays
- [ ] Can view pipeline results
  - After: Pipeline completes
  - Verify: Results page shows
- [ ] Dry-run mode works
  - Run: Pipeline with dry-run=True
  - Verify: No actual applications submitted
- [ ] Can stop pipeline
  - Click: Stop button during execution
  - Verify: Pipeline stops gracefully

---

## Section 9: Settings & Configuration

### Settings Access
- [ ] Settings page loads
  - Navigate to: `/settings` or Settings modal
  - Verify: Settings display

### Application Settings
- [ ] Can update constraint mode
  - Select: Boost or Filter
  - Verify: Setting is saved
- [ ] Can update minimum score
  - Set: Minimum relevance score (0-100)
  - Verify: Setting is saved
- [ ] Can update scam threshold
  - Set: Scam detection threshold (0.0-1.0)
  - Verify: Setting is saved
- [ ] Can update max jobs
  - Set: Maximum jobs to present
  - Verify: Setting is saved

### Preferences
- [ ] Can toggle notifications
  - Click: Notification toggle
  - Verify: Preference is saved
- [ ] Can update theme preference
  - Select: Light or Dark theme
  - Verify: Theme changes immediately
- [ ] Can reset to defaults
  - Click: Reset to Defaults
  - Verify: All settings reset

---

## Section 10: Navigation & UI

### Main Navigation
- [ ] All navigation links work
  - Click: Jobs, Dashboard, Profile, Assessment, Pipeline, Settings
  - Verify: Each link navigates correctly
- [ ] Active page is highlighted
  - Navigate: Between pages
  - Verify: Current page is highlighted in nav
- [ ] Mobile navigation works
  - Set: Mobile viewport (375px width)
  - Verify: Menu button shows and works

### Theme Toggle
- [ ] Theme toggle button visible
  - Verify: Sun/moon icon shows in sidebar
- [ ] Can toggle between light/dark
  - Click: Theme toggle button
  - Verify: Theme switches immediately
- [ ] Theme preference persists
  - Toggle: Theme
  - Refresh: Page
  - Verify: Theme preference is remembered

### Responsive Design
- [ ] Desktop layout works (1280px+)
  - Verify: All elements visible and accessible
- [ ] Tablet layout works (768px-1024px)
  - Verify: Layout adjusts correctly
- [ ] Mobile layout works (375px-667px)
  - Verify: Mobile menu works
  - Verify: Content stacks correctly

---

## Section 11: Error Handling

### Backend Errors
- [ ] 404 errors handled gracefully
  - Navigate to: Non-existent page
  - Verify: Friendly error page shows
- [ ] 500 errors handled gracefully
  - Verify: Error page or message displays
- [ ] API timeout handled
  - Simulate: Slow backend response
  - Verify: Loading indicator shows, then timeout message

### Frontend Errors
- [ ] JavaScript errors caught
  - Open: Browser console
  - Perform: Various actions
  - Verify: No uncaught errors in console
- [ ] Failed API calls show error messages
  - Simulate: Backend failure
  - Verify: User-friendly error toast shows
- [ ] Network errors handled
  - Disconnect: Network
  - Verify: Offline or network error message shows

---

## Section 12: Performance

### Page Load Times
- [ ] Homepage loads in < 3 seconds
  - Navigate to: `/`
  - Verify: Page loads quickly
- [ ] Jobs page loads in < 2 seconds
  - Navigate to: `/jobs`
  - Verify: Page loads quickly
- [ ] Search results appear in < 3 seconds
  - Submit: Job search
  - Verify: Results load within 3 seconds

### Interaction Speed
- [ ] Button clicks respond immediately
  - Click: Various buttons
  - Verify: No lag or delay
- [ ] Form submissions are responsive
  - Submit: Various forms
  - Verify: Feedback shows quickly
- [ ] Page transitions are smooth
  - Navigate: Between pages
  - Verify: Transitions are smooth

---

## Section 13: Browser Compatibility

### Chrome/Edge
- [ ] All features work in Chrome
  - Test: In Google Chrome or Microsoft Edge
  - Verify: No browser-specific issues
- [ ] Console is clean in Chrome
  - Open: DevTools Console
  - Verify: No errors or warnings

### Firefox
- [ ] All features work in Firefox
  - Test: In Mozilla Firefox
  - Verify: No browser-specific issues
- [ ] Console is clean in Firefox
  - Open: Browser Console
  - Verify: No errors or warnings

### Safari (if available)
- [ ] All features work in Safari
  - Test: In Safari (macOS only)
  - Verify: No browser-specific issues

---

## Section 14: Data Persistence

### Profile Data
- [ ] Profile changes persist
  - Update: Profile information
  - Refresh: Page
  - Verify: Changes are saved
- [ ] Settings persist across sessions
  - Update: Settings
  - Restart: Containers
  - Verify: Settings are remembered

### Application Data
- [ ] Saved jobs persist
  - Save: A job
  - Refresh: Page
  - Verify: Job remains saved
- [ ] Application notes persist
  - Add: Note to application
  - Refresh: Page
  - Verify: Note is saved
- [ ] Assessment results persist
  - Complete: DISC assessment
  - Refresh: Page
  - Verify: Results are saved

---

## Section 15: Security

### API Key Security
- [ ] API keys are not exposed in frontend
  - Check: Browser console and network tab
  - Verify: API keys not visible
- [ ] API keys work correctly
  - Verify: API calls succeed with valid keys
- [ ] Invalid API keys are rejected
  - Set: Invalid API key
  - Run: Search
  - Verify: 401 or 403 error shows

### Input Validation
- [ ] SQL injection attempts are blocked
  - Try: SQL injection payloads
  - Verify: Input is sanitized
- [ ] XSS attempts are blocked
  - Try: XSS payloads in text fields
  - Verify: Scripts are not executed

---

## Section 16: Documentation

### Documentation Accessibility
- [ ] README.md is up to date
  - Check: README in repo root
  - Verify: Instructions are current
- [ ] API documentation exists
  - Check: Backend API docs
  - Verify: Endpoints are documented
- [ ] Testing guide exists
  - Check: docs/testing.md
  - Verify: Testing instructions are clear

### Setup Instructions
- [ ] Setup script works
  - Run: `./setup.sh`
  - Verify: All steps complete successfully
- [ ] Fresh setup works
  - On: Fresh system
  - Run: Setup from scratch
  - Verify: Project is ready to run

---

## Section 17: Logging & Monitoring

### Backend Logs
- [ ] Backend logs are informative
  - Check: `docker logs job-raider-backend`
  - Verify: Useful information logs
- [ ] Errors are logged with context
  - Trigger: An error
  - Verify: Stack trace and context logged
- [ ] No critical errors in logs
  - Check: Backend logs
  - Verify: No ERROR or CRITICAL level issues

### Frontend Logs
- [ ] Console is clean
  - Check: Browser console
  - Verify: No error messages
- [ ] Warnings are minimal
  - Check: Browser console
  - Verify: Few or no warnings

---

## Completion Summary

**Total Checks:** ___ / ___
**Passed:** ___
**Failed:** ___
**Skipped:** ___

**Tester:** ___________________
**Date:** ___________________
**Notes:** ___________________________________________________