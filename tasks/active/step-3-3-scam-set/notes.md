# Scratchpad & Notes

## Plan (from `tasks/active/step-3-measurable-claims/notes.md`, 2026-10-22)

- `tests/fixtures/eval/scam/cases.jsonl` with at least 40 postings: legitimate postings from the source fixtures; written scam texts for each indicator group (Payment, Contact, Urgency, Compensation, Listing quality); and legitimate texts that the current rules flag ("signal processing", "competitive pay and the chance to work", a WhatsApp Business API integration role, an engineering role at a bitcoin exchange).
- Baseline on that set, and locally on the Kaggle EMSCAD set (`fake_job_postings.csv`, used by `notebooks/scam_detector_evaluation.ipynb`). Split EMSCAD into a tuning part and a held-out part with a fixed seed.
- Fix R3 after the baseline: word boundaries and phrase context for the patterns in `JobScamDetector.SUSPICIOUS_PATTERNS` (`pay.*to.*work`, `signal`, `kik`, `telegram`, `whatsapp`) and the keyword list `ScamFilter.REJECT_PATTERNS` (a plain `bitcoin` match). Tune the threshold on the tuning part. Report the held-out numbers only.
- CI gate on the committed set (thresholds file). The EMSCAD run stays local and logs to MLflow. Change the notebook to call the CLI, so that the logic exists only once.
- Review source: R3 and M4 in `tasks/active/review-follow-up/review-2026-10-18.md`.

## Observations (2026-10-24, Claude, code at `4f6f77d`)

- **Two components.** `stage_filter_scams` (`src/pipeline/stages.py:291`) runs `ScamFilter.filter_collection` first (`src/scoring/scam_detector.py:579`, plain lower-case substrings in title and description), then `JobScamDetector.detect` on the rest (`scam_detector.py:109`; threshold from the pipeline config `scam_threshold`, default 0.7). `TrustAnalyzer` (`src/scoring/trust_analyzer.py`) also uses `JobScamDetector` for the trust tiers in the UI.
- **Scoring.** The detector adds points per check and divides by 100: payment pattern +50 each, messaging app +40 each, immediate-hire pattern +30 each, grammar up to +20, a description under 100 characters +20, no description +30, a suspicious company word +30, a generic company name +15, an hourly maximum over 100 +40, an annual maximum over about 156,000 +30, a personal email +20, and no recruiter email (with the company domain not in the source URL) +10. A score of 70 or more is a scam.
- **Pattern risks seen in the code** (not measured yet): `re.search` on the whole lower-case description, so `.*` spans a full line: `pay.*to.*work`, `no.*interview` (also inside "knowledge ... interview"), `text.*only`, `start.*today`, `immediate.*hire`; `signal`, `telegram`, `whatsapp`, and `kik` have no word boundaries; `ScamFilter` rejects any description with `bitcoin`. Each match adds 30 to 50 points, so two matches pass the threshold.
- **The notebook** (`apps/backend-py/notebooks/scam_detector_evaluation.ipynb`) scores only `JobScamDetector` at 0.7, sweeps the threshold, and maps EMSCAD rows to `JobListing` (cell 8). It has no saved outputs (M4). Its first cells load `.env` and run the Kaggle download; nobody runs those cells for this task.
- **Data.** `apps/backend-py/data/kaggle/` has only `.gitkeep`: the CSV is not there yet. The source fixtures have about 12 public postings (`tests/fixtures/careersatgov/` 3, `jobstreet/` 3, `mycareersfuture/` 2, `jd_paste/` 4); the search-page fixtures have teaser text only.
- **Out of scope, seen in passing:** `stage_filter_scams` reports `original_count` after the quick filter has removed postings, so the count is too small.

## Stage A review

(Claude adds the review here after Cursor's results in `handoff-stage-a.md`.)

## Blockers / Questions

- The EMSCAD baseline needs the user to put `fake_job_postings.csv` in `apps/backend-py/data/kaggle/` (decision 3 of 2026-10-22).
