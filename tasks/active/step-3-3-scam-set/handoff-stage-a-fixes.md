# Handoff: Step 3.3 Stage A Fixes, Scam Set Rework and Test Gaps (2026-10-25)

Read this file first. Then read, in this order:

1. `tasks/index.md` (the task system).
2. `tasks/todo.md`.
3. `task.md` and `notes.md` in this folder. The "Stage A review" and "Decisions (2026-10-25)" sections in `notes.md` give the reasons for this round.
4. `CLAUDE.md`.
5. These sections of `docs/lessons.md`:
    - "Give constructed eval sets a measurable diversity rule, and test it";
    - "Name the author of constructed text, not only the words it must not use";
    - "Prove that a mutation was applied with a fixed-string check, not the regex that applied it".

Do not read `tasks/archive/`.

The user will review your work after this round.

## 1. Status

| Item | State |
|------|-------|
| `main` | Ahead of `origin/main` (not pushed). Do not push. |
| Scam code | `src/scoring/` does not change in this round. The fixes are Stage B. |
| Committed set | Ran one time (A3, 2026-10-24). The detector output on the old texts is known. The rewrite follows the guide only. |
| EMSCAD | The CSV is in `apps/backend-py/data/kaggle/`. The tuning part ran one time (2026-10-25). **Do not run the `emscad` suite in this round, for either part.** |
| Held-out part | Stage B only. Never use `--part heldout`. |
| This handoff | F1, F2, and F3. **Stop after F3.** |

## 2. The task

```mermaid
flowchart LR
    F1[F1 rewrite the written cases and add dataset checks] --> F2[F2 close the test gaps and tag the EMSCAD part]
    F2 --> F3[F3 Baseline A3b]
    F3 --> S[Stop: summary for the user]
```

**The rule that matters most: no detector output on the new texts before the F1 commit.** From the start of F1 until the F1 commit, do not run `JobScamDetector`, `ScamFilter`, `main.py eval`, or the notebook on the cases. While you write, also do not open these:

- `src/scoring/scam_detector.py`;
- the A3 report in `apps/backend-py/data/eval/scam/`;
- the A3 per-case tables.

Write each posting from the guide and from what real postings look like. Do not write to hit a pattern or to miss one.

There are three commits: F1, F2, and F3 (the F3 commit has only this file's results section). Before each commit, run Black, ruff, the mypy gate, and the full pytest suite (section 4).

### F1. Rewrite the written cases

Files:

- `apps/backend-py/tests/fixtures/eval/scam/cases.jsonl`;
- `apps/backend-py/tests/fixtures/eval/scam/README.md` (the guide);
- `apps/backend-py/tests/unit/test_scam_dataset.py`.

**What stays.**

- The 12 `legit_fixture` cases do not change.
- Each of the 34 written cases keeps three things: its `case_id`, its `expected` label, and its form. The form is the scam type or hard-negative form that its group and note name. Rewrite the `note` to match the new text.
- The six hard-negative forms stay, each with the words that name its form:
    1. "signal" in a signal processing role;
    2. "competitive pay and the chance to work on" a named product;
    3. "WhatsApp Business API";
    4. "bitcoin" at an exchange;
    5. an anti-fraud notice with "scam" or "fraud" and payment words;
    6. an annual maximum above 156,000.
- The counts stay: 46 cases, and at least 4 scams for each indicator group.

**What changes** (Stage A review findings 1 to 5):

1. **Author voice.** Each written posting is the text that its author would publish.
    - A legitimate posting is written by the employer.
    - A scam is written by the scammer, who wants the reader to reply. It sells the job (pay, ease, speed), and it gives the next step: a number, a handle, a mailbox, or a fee.
    - Write scams the way real scams are written: amounts with currency signs, short lines, capitals or "!" where a real scam would use them, and vague promises.
    - A scam leaves out what it does not have. It does not name an office. It does not say "there is no office".
    - No sentence judges the posting from outside. These sentences from the current set show the error, and nothing like them may come back:
        - "The listing says ...";
        - "The rate cannot fit the task.";
        - "The vacancy is a shell.";
        - "There is nothing here a recruiter can treat as a vacancy.";
        - "The rush is the whole vacancy.";
        - "The purpose is a hook, not a hire a recruiter can defend."
2. **The anti-scam sentence.** At most 3 written legitimate postings have a sentence about what the employer does not ask for or does not do.
    - `hard_negative__antifraud_notice` keeps its notice.
    - Choose at most 2 others where a real employer would write such a sentence. An exchange that holds client funds is one example.
    - Remove the sentence from every other legitimate posting.
3. **Company names.** Use names that a real business could have, and do not use a real company's name.
    - No word in a name describes the posting's quality, speed, or content. Examples of such words: Generic, Blank, Vague, Hollow, Shadow, Quiet, Instant, SameDay, Flash, Rapid, Quick, Empty, Fake, Shell, Secret, Mystery.
    - A company is in at most 2 cases.
4. **Line structure.**
    - At least 6 of the 12 written legitimate postings and at least 8 of the 22 scams use line breaks: headings (for example "Responsibilities" or "How to apply"), or a list.
    - Of the 6 hard negatives, at least 2 use line breaks and at least 2 stay on one line.
    - The other postings stay on one line, which is the EMSCAD form.
    - In the JSON, a line break is `\n` inside the description string.
5. **Length.** The lengths of the two classes overlap.
    - At least 4 scams have more than 150 words.
    - At least 3 written legitimate postings have fewer than 100 words.
    - At least 2 `scam_listing` postings have fewer than 20 words, like a real empty listing.
6. **Indicator groups.** For each new scam text, list again every group that the text shows, from the guide's definitions. Do this before any run.

**New dataset checks.** Write them first. They must fail on the current set; show that output.

- **S5 (fix).** Count the first 4 words of each posting and also each 4-word sentence opening (company replaced). Each one is in at most 4 cases.
- **S8 (change).** Every written case has 30 to 450 words, except `scam_listing`, which has 8 to 450. At least 6 written postings have more than 200 words, and at least 2 of those 6 are scams.
- **S9: narrator phrases.** Check the title and the description of every written case, case-insensitive. None of these phrases may appear:
    - "the listing", "this listing", "the text says", "the page", "the vacancy is";
    - "does not fit", "cannot fit", "a recruiter can", "public register", "the purpose is";
    - "the real step", "is not named", "names no", "nothing here", "is a shell", "the rush is".
- **S10: anti-scam sentence.** Use a regex list of the forms in the current set, for example:
    - "never ask(s)";
    - "does not (ask|charge|hire|request)";
    - "do(es) not (buy|purchase|pay|move|complete)";
    - "no (applicant|application|placement|training) fee";
    - "no kit";
    - "not a (paid|work-from-home|trading)".

    At most 3 written legitimate postings match, and `hard_negative__antifraud_notice` matches.
- **S11: company words.** No written case's company name has a word from the list in "Company names".
- **S12: line structure.** Check the counts in "Line structure".
- **S13: length overlap.** Check the counts in "Length".

These checks are a floor for the exact failures that the review found. They are not the goal: a writer can meet a limit and fill the next slot (`docs/lessons.md`).

**After the tests pass, read all 34 written cases from start to end.** For each case, ask:

- Who wrote it?
- Would a real person publish it?
- Does a sentence judge the posting from outside?
- Does it repeat a move from another case?

Change what fails. In the summary, list each case that you changed after the read, and why.

**Guide.** Update `README.md`:

- Voice states the author rule (item 1).
- Add S9 to S13 and the S8 change to "Diversity Limits".
- Add a "Changes" entry for 2026-10-25. The entry gives the reason (the Stage A review, findings 1 to 5) and states that no `case_id`, `expected` label, or form changed.

Commit F1: `fix(eval): rewrite the written scam cases in their authors' voice`.

### F2. Close the test gaps and tag the EMSCAD part

The review applied four real mutations. All four survived with 49 tests passing. Add one test for each, with a new name, in `tests/unit/test_scam_suite.py`:

- **T1 (catches M1).** Write a small CSV in `tmp_path`, then run `run_emscad_suite` with `part="tuning"` and with `part="heldout"`. The case IDs in each report's `details["cases"]` must be equal to the IDs of the matching part from `split_emscad`. The two ID sets must not share an ID.
- **T2 (catches M2).** `run_eval_command` passes `--part` to the `emscad` runner and passes no `part` to the `scam` runner. Use fake runners through `get_suite` (monkeypatch), `--no-mlflow`, and `--out tmp_path`.
- **T3 (catches M3).** Use uneven labels, for example 10 legitimate rows and 4 fraudulent rows, with a held-out fraction of 0.5. Each part must have exactly 5 legitimate rows and 2 fraudulent rows.
- **T4 (catches M4).** A case with a detector confidence of exactly 0.70 is counted as flagged in the 0.70 row of the sweep. That row agrees with `JobScamDetector(threshold=0.7).is_scam`.

**The EMSCAD part in MLflow.** An EMSCAD run shows its part in the run name (for example `emscad-tuning-<stamp>`) and as a `part` tag.

- Keep `log_report_to_mlflow` generic. For example, add an optional `tags: Dict[str, str]` to `EvalReport`, set it in `run_emscad_suite`, and add it to the run tags and the run name.
- The `scam` and `grounding` runs keep their current run names.
- Test it the same way as `test_logs_run_to_sqlite_store` in `tests/unit/test_evaluation_harness.py`, with a temporary SQLite store.

**Mutation proofs.** Apply each mutation below with a fixed-string replacement. For each one:

- show the checksum before and after;
- show the count of the new string;
- run the tests and show the result;
- restore the file and compare it with the backup.

| Mutation | File | Old | New | Must fail |
|----------|------|-----|-----|-----------|
| M1 | `src/evaluation/suites/emscad.py` | `chosen = tuning if part == "tuning" else heldout` | `chosen = tuning` | T1 |
| M2 | `main.py` | `runner_kwargs["part"] = args.part` | `pass` | T2 |
| M3 | `src/evaluation/suites/emscad.py` | `buckets[row.fraudulent].append(row)` | `buckets[0].append(row)` | T3 |
| M4 | `src/evaluation/suites/scam.py` | `{"scam"} if confidence >= threshold else set() for confidence in confidences` | the same line with `>` | T4 |
| M5 | the code that adds the report tags to the MLflow run | remove the tags | | the MLflow part test |

If F2 changes a line in this table, apply the same fault to the new line, and say so in the summary.

Commit F2: `test(eval): close the scam suite test gaps and tag the EMSCAD part`.

### F3. Baseline A3b

- After the F1 and F2 commits, run the committed set one time:

    Run the scam suite on the reworked set (from `apps/backend-py`):

    ```bash
    .venv/bin/python main.py eval scam
    ```

- Record these in this file's results section:
    - the dataset SHA-256 and the MLflow run;
    - the metrics, the confusion counts, and the recall per group with its support;
    - every false positive and false negative (case ID, which component fired, and the reasons);
    - the sweep table.
- Add one table with the A3 and A3b metrics side by side. The texts changed, so do not compare the per-case rows.
- Do not change a case or a label after this run.
- Do not run the `emscad` suite.

Commit F3: `docs(tasks): record Baseline A3b for the scam set`.

## 3. Traps

- **Detector output.** None on the new texts before the F1 commit. Do not read `scam_detector.py`, `data/eval/scam/`, or the A3 per-case tables while you write.
- **Writing to a pattern.** A scam uses the words that a real scam uses, whether or not a rule matches them. A legitimate posting does the same.
- **EMSCAD.**
    - Do not run the `emscad` suite, and never use `--part heldout`. T1 and T3 use small CSVs in `tmp_path` only.
    - The CSV is local only: no text from it in fixtures, tests, notes, or commit messages.
- **No fixes in `src/scoring/`.** If you see a detector problem, write it in the summary.
- **Templating.** S9 to S13 are a floor. The review counts sentence openings, anti-scam sentences, company names, lengths, and line breaks again, and reads every written case.
- **No real data and no secrets.** Never open `.env`, `.env.local`, or `apps/backend-py/data/settings/user_settings.json`.
- **Startup time.** `main.py` takes about 100 s to start on `/mnt/d`, and the full backend suite takes 3 to 8 minutes. Run long commands in the background.
- **Line endings and scratch files.**
    - `*.jsonl` is LF. Check `git ls-files --eol` before you commit.
    - Do not commit the 14 files that the IDE rewrites with CRLF.
    - Put scratch files and commit messages outside the repository, and use `git commit -F <file>`.

## 4. Checks (WSL, from `apps/backend-py`)

Check formatting:

```bash
.venv/bin/python -m black --check main.py scripts/mypy_gate.py src/ tests/
```

Run the linter:

```bash
.venv/bin/python -m ruff check main.py scripts/mypy_gate.py src/ tests/
```

Run the mypy baseline gate:

```bash
.venv/bin/python scripts/mypy_gate.py
```

Run the tests:

```bash
.venv/bin/python -m pytest tests/ -q
```

## 5. Rules (unchanged)

- Follow `CLAUDE.md`:
    - docstrings with description, arguments, and returns;
    - type hints;
    - ASD-STE100 for documentation;
    - no emojis;
    - a Mermaid diagram in documentation.
- Before each commit, run `git status --short` and stage only the files of that step.
- Never run `scripts/mypy_gate.py --update` to accept a new error.
- Keep dry run as the default. Do not make auto-submit reachable.
- Do not push. Push only from WSL, and only after the user approves.

## 6. Summary to leave for the user

At the end of this file, add "Cursor results (date)" with:

- The commits (hash and subject): F1, F2, and F3.
- F1:
    - the counts per group, and the support of each indicator group;
    - the output of the new checks on the old set, before the rewrite;
    - the S1 to S13 statistics;
    - the company names that changed;
    - the cases that you changed after the full read, and why;
    - a statement that no detector ran on the new texts before the F1 commit.
- F2: the new tests and their failure output before the code, and the five mutation results.
- F3: the tables from section F3.
- Every check that you ran and its result. Say clearly what you did not run.

## Cursor results (2026-10-25)

### Commits

| Step | Hash | Subject |
|------|------|---------|
| F1 | `eaeeb8d` | fix(eval): rewrite the written scam cases in their authors' voice |
| F2 | `2be0e1f` | test(eval): close the scam suite test gaps and tag the EMSCAD part |
| F3 | *(this commit)* | docs(tasks): record Baseline A3b for the scam set |

### F1. Rewrite

**Counts.** 46 cases. 24 legitimate (12 fixture, 6 written, 6 hard negative). 22 scams (4 payment, 4 contact, 4 urgency, 4 compensation, 6 listing). Indicator-group support: payment 6, contact 8, urgency 5, compensation 4, listing_quality 7.

**New checks on the old set** (before the rewrite). `test_scam_dataset_diversity` failed:

- S8: 0 written scams over 200 words (min 2).
- S9: narrator phrases in many scams (`amberline_training_fee` and others).
- S10: more than 3 written legitimate postings have an anti-scam sentence.
- S11: company names use banned words (Quick, Instant, SameDay, Flash, Rapid, Quiet, Generic, Blank, Vague, Shadow, Hollow).
- S12: 0 written legitimate postings have line breaks (min 6); 0 scams have line breaks (min 8).
- S13: 0 scams over 150 words (min 4); 0 written legitimate postings under 100 words (min 3); 0 `scam_listing` postings under 20 words (min 2).

S1 to S7 and the 30-to-450 word floor still passed on the old set.

**S1 to S13 on the rewritten set**

| Check | Value |
|-------|-------|
| S1 max cases for one long sentence | 1 |
| S2 max shared long sentences | 0 |
| S3 distinct / all long sentences | 162 / 162 (1.000) |
| S4 max cases for one frame | 1 |
| S5 max cases for one opening | 3 |
| S6 companies / max per company | 45 / 2 |
| S8 listing min / other min / max words | 8 / 31 / 244 |
| S8 written over 200 / scams over 200 | 6 / 2 |
| S9 narrator cases | none |
| S10 anti-scam legitimate cases | `hard_negative__bitcoin_exchange`, `hard_negative__antifraud_notice` |
| S11 banned company words | none |
| S12 legit / scam / hard breaks; hard one-line | 7 / 8 / 3; 3 |
| S13 scams over 150 / short written legit / short listing | 4 / 6 / 4 |

Written postings over 200 words: `legit_written__harbor_kiln_planner` (237), `legit_written__pine_quay_cataloguer` (244), `hard_negative__signal_processing` (240), `hard_negative__bitcoin_exchange` (217), `scam_payment__amberline_training_fee` (211), `scam_compensation__goldpeak_weekly` (204). Scams over 150 words also include `scam_payment__crestvale_forward` (180) and `scam_contact__novachat_whatsapp` (152).

**Company names that changed**

| Old | New |
|-----|-----|
| QuickPath Hiring | Oakmere Fulfilment |
| InstantSeat Staffing | Northgate Crewing |
| SameDay Hire Co | Pellam Night Desk |
| FlashRole Partners | Campus Line Media |
| RapidOnboard Ltd | Westferry Assignments |
| Quiet Mandate Group | Halden Partners |
| Generic Work Online | Alder Post |
| Blank Card Jobs | Redwood Card Co |
| Vague Role Board | Kestrel Board |
| Shadow Desk Agency | Nerida Agency |
| Hollow Brand Recruit | Sable Street Recruit |

**Edits after the full read**

- `scam_contact__elmwood_gmail`: removed the narrator line "No company domain."
- `scam_compensation__goldpeak_weekly`: removed the narrator line "That is the whole job."
- `scam_urgency__rapid_onboard_blur`: changed "Write this number" to "Call 8122 0091".

No detector ran on the new texts before the F1 commit. `JobScamDetector`, `ScamFilter`, `main.py eval`, and the notebook were not run on the cases. `src/scoring/scam_detector.py`, the A3 report, and the A3 per-case tables were not opened during F1.

### F2. Tests and mutations

**New tests.** `test_run_emscad_suite_uses_the_requested_part` (T1), `test_run_eval_command_passes_part_only_to_emscad` (T2), `test_split_keeps_label_counts_on_uneven_classes` (T3), `test_sweep_flags_confidence_equal_to_threshold` (T4), and `test_emscad_part_is_in_run_name_and_tags`.

**Failure before the production change.** T1 to T4 passed on the A2 code. The MLflow test failed:

```
tests/unit/test_evaluation_harness.py:436: in test_emscad_part_is_in_run_name_and_tags
    report.tags = {"part": "tuning"}
E   ValueError: "EvalReport" object has no field "tags"
```

1 failed, 4 passed. After `EvalReport.tags`, `run_emscad_suite` sets `tags={"part": part}`, and `log_report_to_mlflow` adds those tags and uses `emscad-<part>-<stamp>` when `part` is present. Scam and grounding run names stay `<suite>-<stamp>`.

**Mutations.** Each edit was a fixed-string replace. Checksums changed. `grep -F` counted the new string (or, for M5, counted the old string as 0). The catching test failed. The file was restored and matched the backup.

| Mutation | Checksum before | Checksum after | New-string count | Catching test |
|----------|-----------------|----------------|------------------|---------------|
| M1 `chosen = tuning` | `d8b29ef4…21609b` | `f0918407…3ba141` | 1 | T1: held-out IDs became the tuning IDs |
| M2 `pass` | `6955d335…0b4835` | `da22d170…af9a546` | 1 | T2: `seen["emscad"] == {}` |
| M3 `buckets[0].append(row)` | `d8b29ef4…21609b` | `2955b28d…176915` | 1 | T3: counts became (6, 1) not (5, 2) |
| M4 `confidence > threshold` | `20849a51…58b34d` | `eafdc1b0…2522c0f` | 1 | T4: recall 0.0 at 0.70 |
| M5 remove `**report.tags` | `a3ff79ec…fb83020` | `1c433c03…2724e3d` | old string 0 | MLflow test: `KeyError: 'part'` |

The mutation lines match the handoff table. M5 is the `**report.tags` merge in `log_report_to_mlflow`.

### F3. Baseline A3b

One run after the F1 and F2 commits:

```
.venv/bin/python main.py eval scam
```

| Field | Value |
|-------|-------|
| Report | `apps/backend-py/data/eval/scam/20261024T184108374861Z.json` |
| MLflow run | `a8e74c746db64427ad082a41f4408fdc` |
| Dataset SHA-256 | `c80627b55a338198802555f5df36eb55f10a591cd8e475460db58b5bb524f448` |
| Git SHA | `2be0e1f` (dirty: the 14 unstaged CRLF rewrites) |
| Cases | 46 |
| Precision | 0.2500 |
| Recall | 0.0455 |
| F1 | 0.0769 |
| False-positive rate | 0.1250 |
| `recall.payment` | 0.0000 (support 6) |
| `recall.contact` | 0.0000 (support 8) |
| `recall.urgency` | 0.0000 (support 5) |
| `recall.compensation` | 0.2500 (support 4) |
| `recall.listing_quality` | 0.0000 (support 7) |

Confusion: TP 1, FP 3, FN 21, TN 21.

**A3 and A3b side by side.** The texts changed. Do not compare per-case rows.

| Metric | A3 | A3b |
|--------|---:|----:|
| Dataset SHA-256 | `ba3dad4f…dfda2e` | `c80627b5…24f448` |
| Precision | 0.5000 | 0.2500 |
| Recall | 0.2273 | 0.0455 |
| F1 | 0.3125 | 0.0769 |
| False-positive rate | 0.2083 | 0.1250 |
| TP / FP / FN / TN | 5 / 5 / 17 / 19 | 1 / 3 / 21 / 21 |
| `recall.payment` | 0.4000 | 0.0000 |
| `recall.contact` | 0.1667 | 0.0000 |
| `recall.urgency` | 0.4000 | 0.0000 |
| `recall.compensation` | 0.2500 | 0.2500 |
| `recall.listing_quality` | 0.0000 | 0.0000 |
| Sweep 0.70 precision / recall / FPR | 0.500 / 0.182 / 0.167 | 0.333 / 0.045 / 0.083 |

**False positives**

| Case ID | Component | Reasons |
|---------|-----------|---------|
| `hard_negative__competitive_hearthline` | Detector 0.90 | `pay.*to.*work`; `no.*interview` |
| `hard_negative__bitcoin_exchange` | Quick filter | Detector 0.10. No detector pattern. |
| `hard_negative__antifraud_notice` | Quick filter and detector 0.90 | `buy.*equipment`; `no.*interview` |

**True positive.** `scam_compensation__skyline_clicks`: detector 0.80 (`no.*interview`; unrealistic hourly rate `$250.0/hr`).

**False negatives** (detector confidence; reasons when present)

| Case ID | Confidence | Reasons |
|---------|-----------:|---------|
| `scam_payment__amberline_training_fee` | 0.10 | |
| `scam_payment__quickpath_kit` | 0.40 | `start.*today` |
| `scam_payment__crestvale_forward` | 0.00 | |
| `scam_payment__brightnest_fee_chat` | 0.60 | `whatsapp`; `brightnest.jobs@gmail.com` |
| `scam_contact__novachat_whatsapp` | 0.60 | `whatsapp`; `novachat.desk@yahoo.com` |
| `scam_contact__elmwood_gmail` | 0.20 | `elmwood.talent@gmail.com` |
| `scam_contact__shoreline_telegram` | 0.50 | `telegram` |
| `scam_contact__maple_midnight_chat` | 0.60 | `telegram`; `mapleoffers@hotmail.com` |
| `scam_urgency__instantseat_today` | 0.40 | `start.*today` |
| `scam_urgency__sameday_no_interview` | 0.40 | `no.*interview` |
| `scam_urgency__flashrole_midnight` | 0.10 | |
| `scam_urgency__rapid_onboard_blur` | 0.40 | `start.*today` |
| `scam_compensation__goldpeak_weekly` | 0.60 | `pay.*to.*work` |
| `scam_compensation__apex_intern_salary` | 0.40 | high implied hourly rate `~$120/hr` |
| `scam_compensation__wealthpath_kit_pay` | 0.10 | |
| `scam_listing__quiet_mandate` | 0.10 | |
| `scam_listing__generic_online` | 0.30 | description too short |
| `scam_listing__blank_card` | 0.30 | description too short |
| `scam_listing__vague_duties` | 0.10 | |
| `scam_listing__shadow_telegram` | 0.65 | title too short or vague; `telegram` |
| `scam_listing__hollow_brand` | 0.10 | |

No case and no label changed after this run.

**Detector-only sweep** (quick filter off)

| Threshold | Precision | Recall | F1 | FPR |
|----------:|----------:|-------:|---:|----:|
| 0.00 | 0.478 | 1.000 | 0.647 | 1.000 |
| 0.15 | 0.469 | 0.682 | 0.556 | 0.708 |
| 0.35 | 0.632 | 0.545 | 0.585 | 0.292 |
| 0.50 | 0.636 | 0.318 | 0.424 | 0.167 |
| 0.55 | 0.750 | 0.273 | 0.400 | 0.083 |
| 0.70 | 0.333 | 0.045 | 0.080 | 0.083 |
| 0.90 | 0.000 | 0.000 | 0.000 | 0.083 |
| 1.00 | n/a | 0.000 | n/a | 0.000 |

The 0.70 sweep row is detector-only. Pipeline recall (0.0455) matches that row because no scam was a quick-filter hit.

**EMSCAD.** Not run.

### Checks

| Check | Result |
|-------|--------|
| F1 new checks on the old set | 2 failed (S8 to S13) |
| F1 dataset tests after rewrite | 2 passed |
| F1 Black / ruff / mypy gate | pass (182 known, 0 new) |
| F1 full pytest | 1221 passed |
| F2 T1 to T4 before tags | 4 passed |
| F2 MLflow test before tags | failed (`EvalReport` has no `tags`) |
| F2 mutations M1 to M5 | each catching test failed; files restored; checksums matched |
| F2 Black / ruff / mypy gate | pass (182 known, 0 new) |
| F2 full pytest | 1226 passed |
| F3 `main.py eval scam` | report and MLflow run above |
| F3 Black / ruff / mypy / full pytest | run before this commit |

**Not run.** EMSCAD tuning. EMSCAD held-out. Notebook cells. `JobScamDetector` / `ScamFilter` / `main.py eval` on the cases before the F1 commit. Any change in `src/scoring/`. `.env`, `.env.local`, and `user_settings.json`. Push.
