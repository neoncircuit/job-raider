# Notes: linkedin-country-hosts

Planned 2026-11-13. Review section to be added when the task is done.

## Build and checks (2026-11-13, scratch clone)

- `src/linkedin/profile_url.py`: a host is allowed when it is `linkedin.com`, `www.linkedin.com`, or a full match of `[a-z]{2}\.linkedin\.com` (the host is lowercased first). After the https, host, and credentials checks, a country host is changed to `www.linkedin.com` (`urlunparse`, path, query, and fragment stay). `validate_linkedin_profile_url` uses the navigation check, so both get the rule.
- Tests: `TestLinkedInCountryHosts` in `tests/unit/test_local_first_guards.py`, next to the existing profile URL tests: sg, uk, de profile URLs and an `SG.` navigation URL come back on www; www and bare linkedin.com unchanged; 11 rejections (look-alike hosts, other subdomains, http, credentials, a non-profile path).
- Red step: 4 fail (the accept cases); 12 pass with and without the change (guards). Mutants: suffix check, `search` instead of `fullmatch`, no rewrite to www, country URL returned before the credentials check: 4 of 4 caught.
- Full checks: black and ruff clean, mypy gate 177 known and 0 new, pytest 2,315 passed.

- Clone commit `4da227f` on top of `fd342c7`. Applied and pushed (user approved, 2026-11-13): `main` fast-forwarded to `4da227f`; `git diff` against it is empty; pushed with the pins archive commit.

## CI (2026-11-13)

- CI run 43437917686 passed: 12 jobs passed, `Build Docker Image` skipped (push run). Mypy gate 177 known and 0 new; Vitest 379 passed; E2E 45 and demo E2E 18 passed; the backend test job passed.

## Review

LinkedIn URLs on a two-letter country host (such as `sg.linkedin.com`) are accepted for profile and navigation URLs and stored and opened as `www.linkedin.com`. The Step 2 security rule stays: the host must match in full, and look-alike hosts, other subdomains, http, and credentials are rejected. The open question from Step 2 is closed.
