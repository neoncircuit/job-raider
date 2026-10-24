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

## Stage A review (2026-10-25, Claude)

Commits `26988ab`, `8615c3f`, `ad0819d`. Cursor's results are at the end of `handoff-stage-a.md`.

**Verdict.** The suites compute the right values, and the baseline reproduces. Four tests do not guard what they claim (finding 6). The written cases are not ready to be the CI guard: they are not in the voice of the people who would write them, and three patterns go through every written case. Rework the written cases and close the test gaps before Stage B (see "Recommendations"). The EMSCAD tuning baseline, which ran after the CSV arrived, shows that the current filter removes about 45 real postings for each fraud that it catches. Stage B needs a scope decision first.

### What I checked and found correct

- **Commits.** Three commits, each with only the files of its step. All new files are LF. `src/scoring/` did not change. The 14 CRLF files were not committed.
- **Order.** The MLflow store has one scam run (`6be4c68d`, 08:31 UTC = 16:31 local). It started after the A2 commit (16:29) and after the A1 commit (15:30). `data/eval/scam/` has one report. Nothing shows a detector run before the A1 commit.
- **Decision.** `decide_pipeline_scam` is the pipeline decision: `stage_filter_scams` calls `ScamFilter.filter_collection` (which calls `is_potential_scam`), then `JobScamDetector.detect` at 0.7.
- **EMSCAD mapping.** `row_to_job_listing` is notebook cell 8. Two differences, both better: an empty title becomes "Unknown" (not "nan"), and booleans are read from the CSV text.
- **Sweep.** I recomputed the 0.70 row from the per-case rows: detector only, TP 4, FP 4 (precision 0.50, recall 0.18), as reported.
- **Labels.** I read all 34 written cases. I agree with the `scam` or `legit` label of each case.
- **Reproduction.** `main.py eval scam --no-mlflow` on the same dataset SHA-256 gives the same metrics, the same 46 per-case rows, and the same sweep as the A3 report.

### Findings

1. **The scams are written by a narrator, not by a scammer (major).** At least 20 of the 22 scam texts have sentences that judge the posting from outside: "The listing says ...", "The rate cannot fit the task.", "The vacancy is a shell.", "There is nothing here a recruiter can treat as a vacancy.", "The purpose is a hook, not a hire a recruiter can defend." The guide's own Voice rule says to write each posting as its author. A real scam posting sells the job. The 22 scams have no "$" and no "!". The narration already changed one detector result: `text.*only` fired on "The text says only that ..." in `scam_listing__generic_online`. That is a narration hit, not a scam signal. Cursor's 10-case read said the cases read as real postings. The scams do not.
2. **The anti-scam sentence is a template (major).** All 12 written legitimate postings (6 `legit_written` and 6 hard negatives) have a sentence that says what the employer never asks for ("never asks an applicant to buy a radio or a pass", "No kit purchase. No remote onboarding fee.", "does not charge applicants and does not hire through messaging apps"). Only `hard_negative__antifraud_notice` needs one. A legitimate posting that says it is not a scam has its label in its text. S1 to S5 cannot see this, because the words change in each case. This is the slot lesson again (`docs/lessons.md`).
3. **Company names show the label (moderate).** Generic Work Online, Blank Card Jobs, Vague Role Board, Hollow Brand Recruit, Shadow Desk Agency, Quiet Mandate Group, InstantSeat Staffing, SameDay Hire Co, FlashRole Partners, RapidOnboard Ltd, QuickPath Hiring.
4. **Length and line structure (moderate).** Length separates the written classes completely: the written scams have 55 to 93 words, and the written legitimate postings have 115 to 248. No written posting has a line break (0 of 34). EMSCAD descriptions also have no line break (0 of 17,880), but pasted postings in the pipeline do (the `jd_paste` fixtures have 18 to 24). `.` in a pattern does not match a line break, so the line structure changes which `.*` patterns fire. A probe that put each sentence of the written cases on its own line changed 7 confidences and 3 decisions: two false positives went away (`hard_negative__signal_processing`, `hard_negative__competitive_hearthline`, both through `no.*interview`), and one true positive went away (`scam_payment__amberline_training_fee`, through `wire.*transfer`). The set needs both forms, so that a B1 fix is measured on both. Part of this is from my handoff: the 30-word floor of S8 stops very short listing-quality scams (so the detector's under-100-characters check can never fire on a written case), and I asked for 6 postings over 200 words but not for long scams.
5. **Some indicator groups are missing (minor).** `scam_contact__elmwood_gmail` asks the applicant to buy a flight on their card (payment). `scam_urgency__rapid_onboard_blur` gives only "a personal number" (contact). The guide says to list every group that the posting shows.
6. **Test gaps (moderate).** I ran six real mutations (`tests/unit/test_scam_suite.py` and `tests/unit/test_cli.py`, 49 tests; each file restored, checksums matched). Cursor's two mutations hold. Four of mine survived:

    | Mutation | Result |
    |----------|--------|
    | M1 `run_emscad_suite` returns the tuning rows for `part="heldout"` | **survived** (49 passed) |
    | M2 `main.py` does not pass `--part` to the runner | **survived** (49 passed) |
    | M3 `split_emscad` puts both labels in one bucket (no stratification) | **survived** (49 passed) |
    | M4 the sweep uses `>` in place of `>=` | **survived** (49 passed) |
    | M5 per-group recall counts a miss as a hit | caught (`comparison failed`) |
    | M6 the `fraudulent` label is inverted | caught (`test_load_emscad_maps_notebook_fields`) |

    M1 and M2 matter most: with either one, the single held-out run in Stage B would score the tuning part and nobody would see it. M4 matters because detector scores are multiples of 0.05, so many cases sit exactly on a sweep step. M3 survives because the test has 6 rows of each label and checks only that both labels are in both parts; it must check the count per label in each part.
7. **MLflow cannot tell the EMSCAD parts apart (minor).** The part is only in the JSON artifact. The run name, the tags, the params, and the dataset SHA-256 are the same for a tuning run and a held-out run. `--part heldout` also has no guard against a second run.
8. **S5 is not the stated rule (minor).** The test counts the first 4 words of each posting. The handoff asked for 4-word sentence openings. Both are inside the limit today (largest counts 1 and 3).
9. **A3 is not complete.** Cursor checked A3 in `task.md` (not committed), but the EMSCAD tuning baseline did not run because the CSV is not there. I set A3 back to open.

### What the baseline shows for Stage B (keep as the record)

- All 5 false positives are hard negatives. `no.*interview` is in 4 of the 5, and it also puts 2 clean legitimate postings at 0.40 (`no` matches inside "note" and "not"). The R3 list did not name it; it belongs in B1. The `ScamFilter` substring `gift cards` fires on the anti-fraud notice, so it belongs in B1 with `bitcoin`.
- A recall gap that is not R3: `_check_salary` reads only hourly and annual pay, so 4000 and 8000 per week score nothing (`scam_compensation__goldpeak_weekly`, `scam_compensation__wealthpath_kit_pay`, both 0.10).
- EMSCAD (checked on the CSV with counts only, 2026-10-25: SHA-256 `59253295129d8b6a27607f9904f7d4ddf4dbb0ee35e079c7eb51b58b5e62bf60`, 17,880 rows, 866 fraudulent) has no company column, so every row maps to "Unknown", and no recruiter email, so every row gets the 10 "no company email" points. The text masks emails (`#EMAIL_...#` in 889 rows; no row has a literal `@gmail.com`), URLs (4,679 rows), and phone numbers (444 rows). EMSCAD cannot measure the contact group. Only the committed set can. The largest field has 14,907 characters, so the default CSV field limit is enough.

### EMSCAD tuning baseline (A3, 2026-10-25, Claude)

Run one time with the unchanged detector, after the review mutations were restored. The held-out part did not run.

Run the EMSCAD tuning part (from `apps/backend-py`):

```bash
.venv/bin/python main.py eval emscad --part tuning
```

| Field | Value |
|-------|-------|
| Report | `apps/backend-py/data/eval/emscad/20261024T172032465209Z.json` |
| MLflow run | `99102a9ba7d841758ec33cf68291e76a` (run name `emscad-20261024T172032465209Z`; the part is only in the report, see finding 7) |
| Dataset SHA-256 (report, name plus LF content) | `a771a4eae6078269a0e57a2c5bfadc1de57f1e917885deefb8012c0a06f641a4` |
| CSV file SHA-256 | `59253295129d8b6a27607f9904f7d4ddf4dbb0ee35e079c7eb51b58b5e62bf60` |
| Git SHA | `ad0819d` (dirty: the 14 CRLF files and this review) |
| Split | seed 20261024, half held out: 8,940 tuning rows (433 fraudulent, 8,507 legitimate), 8,940 held-out rows |
| Precision | 0.0219 |
| Recall | 0.0069 |
| F1 | 0.0105 |
| False-positive rate | 0.0158 |

Confusion: TP 3, FP 134, FN 430, TN 8,373. The quick filter fired on 35 rows, and all 35 are legitimate.

Top reasons on the 134 false positives: `no company email` 134 (every row), `pay.*to.*work` 64, `no.*interview` 47, `wire.*transfer` 22, excessive capitals in the title 19, `payment.*required` 18, `text.*only` 15, `start.*today` 13.

Detector-only sweep (selected rows; the base rate of fraud is 0.048):

| Threshold | Precision | Recall | F1 | FPR |
|----------:|----------:|-------:|---:|----:|
| 0.10 | 0.048 | 1.000 | 0.092 | 1.000 |
| 0.15 | 0.059 | 0.206 | 0.092 | 0.166 |
| 0.30 | 0.044 | 0.106 | 0.062 | 0.118 |
| 0.50 | 0.026 | 0.032 | 0.029 | 0.062 |
| 0.70 | 0.029 | 0.007 | 0.011 | 0.012 |
| 0.90 | 0.043 | 0.005 | 0.008 | 0.005 |

**What this means.**

- At 0.70 the pipeline catches 3 of 433 frauds and removes 134 of 8,507 real postings: about 45 real postings for each fraud that it catches. Its precision (0.022) is below the base rate (0.048), so a flagged posting is less likely to be fraud than an average posting.
- No threshold helps. The best F1 of the detector is 0.092, which is also the F1 of flagging every row. Every row gets 0.10 from the "no company email" check.
- The rules look for forms (fees, messaging apps, urgency) that EMSCAD frauds rarely show in text, and EMSCAD masks the emails and links that the contact rules need.

**Consequence for Stage B (decide before its handoff).** The R3 fixes can cut the false positives. That is the real harm today, because the filter removes real jobs without a trace. The R3 fixes cannot give a useful recall. The Done-when line ("the README states precision and recall on the held-out EMSCAD part") will report a recall near zero unless Stage B also adds detection. There are three options:

- **(a)** Precision only: R3 fixes, then a threshold chosen for a low false-positive rate. Report the held-out numbers as they are.
- **(b)** Option (a), plus one round of new rule signals, tuned on the tuning part only.
- **(c)** Option (a), plus a learned classifier (for example TF-IDF and logistic regression) trained on the tuning part and judged one time on the held-out part. EMSCAD postings are from 2012 to 2014 and mostly from the US, so the result does not transfer directly to current postings in Singapore.

Claude's recommendation: (a) in Stage B, and (c) as its own later step if the user wants a detection number, because it changes the pipeline design.

### Recommendations

1. **Rework the written cases before Stage B (Cursor, "Stage A fixes").** Each case keeps its `case_id`, its form, and its `scam` or `legit` label.
    - Rewrite the 22 scams as the scammer would publish them, and add measurable checks to `test_scam_dataset.py`.
    - Keep the anti-scam sentence only in the anti-fraud notice and in at most 2 other postings.
    - Give neutral names to the companies that show the label.
    - Put line breaks (sections or lists) in at least half of the written postings.
    - Make the lengths overlap: some long scams, some short legitimate postings, and some listing-quality scams under 30 words. This changes the S8 floor for `scam_listing`.
    - Assign the indicator groups again from the guide before any run.
    - Then run the set one time as Baseline A3b, and keep A3 in the record.

    Why: the Stage B CI gate pins counts on this set, and the B1 fixes are judged on it. EMSCAD cannot replace it for the contact group or the R3 forms.
2. **Close the test gaps in the same round,** and show the EMSCAD part in the MLflow run name and tags.
3. **EMSCAD tuning baseline: done.** The user put `fake_job_postings.csv` in `apps/backend-py/data/kaggle/` on 2026-10-25, and Claude ran the tuning part one time (see "EMSCAD tuning baseline"). The held-out part still waits for Stage B.
4. **Stage B scope.** Add `no.*interview` and the `gift cards` substring to B1. Choose (a), (b), or (c) from "EMSCAD tuning baseline" before the Stage B handoff. Claude recommends (a). The weekly-pay recall gap goes to the known limits under (a).

## Decisions (2026-10-25)

The user accepted the four recommendations of the review (decisions 1 to 4), and later the same day the Stage B rules (decision 5).

1. **Rework the written cases before Stage B.** A "Stage A fixes" round (Cursor, `handoff-stage-a-fixes.md`) rewrites the 34 written cases:
    - every posting in the voice of its author;
    - the anti-scam sentence in at most 3 legitimate postings (the anti-fraud notice and 2 others);
    - neutral company names;
    - line breaks in about half of the postings;
    - lengths that overlap between the classes;
    - indicator groups assigned again.

    Each case keeps its `case_id`, its form, and its `scam` or `legit` label. Then Baseline A3b runs one time. A3 stays in the record.
2. **Close the test gaps** M1 to M4 in the same round, each with a real mutation proof.
3. **Show the EMSCAD part** in the MLflow run name and as a tag.
4. **Stage B is option (a).** It has three parts:
    - the R3 precision fixes, with `no.*interview` and the `gift cards` substring added to B1;
    - a threshold chosen on the EMSCAD tuning part for a low false-positive rate (the Stage B handoff fixes the selection rule before the tuning runs);
    - a guard so the held-out part runs one time, then the one held-out run.

    The weekly-pay gap and the low EMSCAD recall go to the known limits. A learned classifier (option c) is not part of Step 3.3. It is parked in `tasks/backlog.md`.
5. **Stage B rules (accepted later on 2026-10-25).** The user accepted the selection rule and the B1 stop rule as written in "Stage B selection rule and B1 stop rule":
    - S1: the threshold `t*`;
    - S2: the action, `drop` or `flag`, with the `scam_action` setting;
    - S3: the held-out report, with Wilson 95% intervals;
    - S4: the numbers 0.005, 0.50, and 10 do not change after a tuning run;
    - B1 is one round over a fixed pattern list, plus at most one fix round.

    On today's code the rules pick `flag`.

## Stage B selection rule and B1 stop rule (decision 5, 2026-10-25)

Claude proposed these rules, and the user accepted them as written on 2026-10-25. They are fixed before B1 and before any tuning run, so that the tuning results cannot move them.

**Why a rule with an action.** The pipeline removes a flagged posting without a trace, and the user never sees it. A false positive costs a real job. A false negative shows a scam that the user can still judge, and the job page can still run the trust analysis on request (`/jobs/{id}/trust`). So the threshold rule also decides whether the filter may remove postings at all.

**Rule S1, the threshold.**

- Use the pipeline decision after B1: the quick filter and the detector together.
- Score it on the EMSCAD tuning part at each threshold from 0.05 to 1.00, in steps of 0.05.
- The threshold `t*` is the one with the highest recall among those whose false-positive rate is at most 0.005. That is at most 1 real posting in 200, or 42 of the 8,507 legitimate tuning rows. On a tie, use the higher threshold.
- If no threshold has a false-positive rate of 0.005 or less, `t*` is 1.00.

**Rule S2, the action.**

- At `t*`, the pipeline may remove (`drop`) flagged postings only if two conditions hold on the tuning part:
    - the precision is at least 0.50, so a removed posting is at least as likely to be fraud as real;
    - at least 10 frauds are flagged, so that the precision does not rest on a few rows.
- Otherwise the pipeline keeps every posting (`flag`). It stores the detector confidence and reasons in the posting's metadata and logs them.
- Stage B adds a pipeline setting `scam_action` (`drop` or `flag`) and sets its default from this rule. The quick filter follows the same action.

**Rule S3, the report.**

- The held-out part runs one time, at `t*`, with the chosen action.
- Report the precision, the recall, and the false-positive rate, each with its counts and a Wilson 95% interval.
- The README states these numbers, the action, and the limits of EMSCAD:
    - the postings are from 2012 to 2014;
    - emails and links are masked;
    - there are no company names.

**Rule S4, no change after a tuning run.** The numbers 0.005, 0.50, and 10 do not change after a tuning run. A change needs a new user decision with its reason, recorded before the held-out run.

**B1 stop rule.**

- B1 is one round over a fixed list:
    - every pattern in `JobScamDetector.SUSPICIOUS_PATTERNS` that has `.*` or no word boundary (`pay.*to.*work`, `no.*interview`, `text.*only`, `start.*today`, `immediate.*hire`, `signal`, `kik`, `telegram`, `whatsapp`, and the others of these two kinds);
    - the `ScamFilter.REJECT_PATTERNS` substrings `bitcoin` and `gift cards`.
- B1 adds no new pattern for recall (option a).
- After the review, at most one fix round follows. What then stays wrong goes to the known limits.
- After B1, every hard negative in the committed set must be `legit`.

**What the rules pick on today's code** (tuning report of 2026-10-25, before B1):

| Quick filter | Thresholds with FPR at most 0.005 | `t*` | Precision at `t*` | Flagged frauds | Action |
|--------------|-----------------------------------|------|-------------------|----------------|--------|
| On | none (lowest FPR 0.0061 at 0.95 and 1.00) | 1.00 | 0.000 | 0 | `flag` |
| Off | 0.95, 1.00 (recall 0.000) | 1.00 | 0.000 | 0 | `flag` |

At every threshold today, the pipeline removes about 16 or more real postings for each fraud that it catches. The best case is 0.15: 89 frauds and 1,419 real postings, precision 0.059 against a base rate of 0.048. Unless B1 changes this a lot, the likely Stage B result is `flag`: the pipeline stops removing postings and only records the score.

## Review of the Stage A fixes (2026-10-25, Claude)

Commits `eaeeb8d` (F1), `2be0e1f` (F2), and `6f1b26f` (F3). Cursor's results are at the end of `handoff-stage-a-fixes.md`.

**Verdict.** Accept the reworked set for Stage B. Do not run a third rewrite round. The set now does its job as a guard for the hard-negative forms and for regressions. It is not a measure of detector recall, and the limits below keep it from being used as one.

### What I checked and found correct

- **Commits.** Three commits, each with only the files of its step, all LF. `src/scoring/` did not change. No EMSCAD run: the only EMSCAD report is mine from 2026-10-25. The A3b report (02:41 local) is after the F2 commit (02:39).
- **Voice.** I read all 34 written cases. The scams read as scam advertisements, and the legitimate postings read as employer postings. My narrator regex finds 0 of 22 scams (it was 20 of 22). The anti-scam sentence is in 2 legitimate postings: the bitcoin exchange and the anti-fraud notice (it was 12). No company name shows the label.
- **Forms and labels.** The six hard-negative forms are present: 3 with line breaks and 3 on one line. Each case keeps its ID and label. The indicator groups that the Stage A review named as missing are now listed (`scam_contact__elmwood_gmail` has payment, and `scam_urgency__rapid_onboard_blur` has contact).
- **Structure and length.** 15 of the 34 written postings have line breaks. Lengths overlap: scams have 8 to 211 words, and legitimate postings have 55 to 244.
- **Encoding.** The non-ASCII characters are em dashes, an en dash, bullets, and middle dots, all valid UTF-8.
- **F2 code.** `EvalReport.tags`, the part in the run name, and the `part` tag are correct. Minor: `**report.tags` comes after the core tags, so a report tag could replace `suite` or `git_sha`. Only EMSCAD sets tags today.
- **Mutations (mine).** I ran the four Stage A review mutations again (M1 to M4), plus M5 (per-group recall), M6 (inverted label), and M7 (report tags not merged into the MLflow tags). The run used `test_scam_suite.py`, `test_cli.py`, and `test_evaluation_harness.py` (84 tests). Each file was restored and its checksum matched. Each mutation failed its intended test:

    | Mutation | Test that failed |
    |----------|------------------|
    | M1 | `test_run_emscad_suite_uses_the_requested_part` |
    | M2 | `test_run_eval_command_passes_part_only_to_emscad` |
    | M3 | `test_split_keeps_label_counts_on_uneven_classes` |
    | M4 | `test_sweep_flags_confidence_equal_to_threshold` |
    | M5 | `test_per_group_recall` |
    | M6 | `test_load_emscad_maps_notebook_fields` |
    | M7 | `test_emscad_part_is_in_run_name_and_tags` |
- **Reproduction.** `main.py eval scam --no-mlflow` gives the same dataset SHA-256, metrics, per-case rows, and sweep as the A3b report.

### Limits of the reworked set (record; no third round)

1. **The written classes separate on hype.** All 22 scams have "!" and "$". None of the 12 written legitimate postings has either. A rule on "!" alone would classify every written case correctly. This is the next slot after the Voice rule (`docs/lessons.md`), so another limit would only move it again. Two scams have "$" with no amount ("$ weekly", "today's $ pay"). **Rule:** do not tune or judge a new detector signal (punctuation, currency, capitals, or any learned model) on this set.
2. **Committed-set recall does not measure detector recall.** A probe scored the A3 text, the A3b text, and the A3b text on one line for each changed case:
    - Of the 4 A3 detections that A3b lost, line breaks explain 1 (`scam_payment__crestvale_forward` is still caught on one line).
    - Word changes explain 3: "interview" left `scam_contact__maple_midnight_chat` ("No meeting") and `scam_urgency__instantseat_today`, and "wire" left `scam_payment__amberline_training_fee`.
    - "No interview", the guide's own urgency sign, is now in 1 of the 5 urgency scams, down from 4 of 5. Most of the old mentions were narrator sentences, but `scam_urgency__flashrole_midnight` lost "no interview" from a sentence that otherwise stayed.

    I cannot tell whether the writer avoided the patterns. The writer knew them from the A3 results. **Consequence for B1:** the committed set cannot show a B1 change that loses real detections (it has 1 true positive). B1 needs unit tests for each changed pattern: real scam wording that must still match, and hard-negative wording that must not.
3. **Padding.** 4 of the 6 postings over 200 words, and the long scams, reach their length with text after the "How to apply" section or with repeated lines. My 200-word floor caused this.
4. **Line breaks hide two R3 forms at 0.70.** `hard_negative__signal_processing` and `hard_negative__whatsapp_business_api` now score 0.50, not 0.80, because a line break stops `no.*interview`. `signal` and `whatsapp` still add 40 points each. A CI gate that pins only the decisions at one threshold would not see a regression in these patterns. **Consequence for B3:** pin the hard negatives' detector scores (or the counts at a lower check threshold), not only the decisions.

### A3b baseline (Cursor, confirmed)

Precision 0.25, recall 0.045, F1 0.077, FPR 0.125 (TP 1, FP 3, FN 21, TN 21). The false positives are `hard_negative__competitive_hearthline` (detector 0.90: `pay.*to.*work`, `no.*interview`), `hard_negative__bitcoin_exchange` (quick filter `bitcoin`), and `hard_negative__antifraud_notice` (quick filter `gift cards`, detector 0.90: `buy.*equipment`, `no.*interview`).

## Blockers / Questions

- None. The CSV is in `apps/backend-py/data/kaggle/` (2026-10-25; ignored by git through `data/`).
