# Handoff: Step 3.3 Stage A, Scam Set, Suites, and Baselines (2026-10-24)

Read this file first. Then read, in this order: `tasks/index.md` (the task system), `tasks/todo.md`, `task.md` and `notes.md` in this folder, `CLAUDE.md` (project rules), and these sections of `docs/lessons.md`: "Give constructed eval sets a measurable diversity rule, and test it", "A perfect score on a dev set says nothing about phrasings the set lacks", and "Set a stop rule for rule rounds on a long-tail check". Use the grounding suite as the model for code and tests: `apps/backend-py/src/evaluation/suites/grounding.py`, `apps/backend-py/tests/unit/test_grounding_dataset.py`, and the guide `apps/backend-py/tests/fixtures/eval/grounding/README.md`. Do not read `tasks/archive/`.

The user will review your work after Stage A.

## 1. Status

| Item | State |
|------|-------|
| `main` | 3 commits ahead of `origin/main` (not pushed). Do not push. |
| Scam code | `src/scoring/` does not change in Stage A. The fixes are Stage B, after the review. |
| EMSCAD | `apps/backend-py/data/kaggle/` has no `fake_job_postings.csv` yet. The user downloads it (decision 3 of 2026-10-22). If it is not there at A3, skip the EMSCAD baseline and say so. |
| Held-out part | The EMSCAD held-out part is the unbiased measure. **Do not run it in Stage A**, not even to look. It runs one time in Stage B, after the threshold is chosen. |
| This handoff | A1, A2, and A3. **Stop after A3.** |

## 2. The task

```mermaid
flowchart LR
    A1[A1 guide, cases, dataset tests] --> A2[A2 scam and emscad suites]
    A2 --> A3[A3 baselines]
    A3 --> S[Stop: summary for the user]
```

**The rule that matters most: no detector output before the labels are frozen.** From the start of A1 until the A1 commit, do not run `JobScamDetector`, `ScamFilter`, `main.py eval`, or the notebook on the cases. Decide every label from the guide only. The structure and diversity tests do not run the detector, so you can run them at any time.

Three commits: A1, A2, and A3 (the A3 commit has only this file's results section). Black, ruff, the mypy gate on `main.py scripts/mypy_gate.py src/ tests/`, and the full pytest suite before each commit.

### A1. Labeling guide, cases, and dataset tests

Files: `apps/backend-py/tests/fixtures/eval/scam/README.md` (the guide, with a Mermaid diagram of the labeling steps), `cases.jsonl` in the same folder, and `apps/backend-py/tests/unit/test_scam_dataset.py`.

**Definition for the guide.** A posting is `scam` when its purpose is to take money, personal data, or unpaid work from the applicant, or when it misrepresents the employer. Label by the purpose of the whole posting, not by single words. The guide describes the signs of each indicator group:

- `payment`: the applicant pays a fee, buys equipment or a kit, or receives money to forward;
- `contact`: the hiring moves to a messaging app or a personal email address only;
- `urgency`: a hire with no interview, or a start today with no checks;
- `compensation`: pay that does not fit the work, the hours, or the role;
- `listing_quality`: no real employer, no real duties, or a very short or generic text.

**Case format.** Add `ScamCase` (Pydantic, `extra="forbid"`) in `src/evaluation/suites/scam.py` (A2 uses it too):

- `case_id`: `<group>__<short_name>`. Groups: `legit_fixture`, `legit_written`, `hard_negative`, `scam_payment`, `scam_contact`, `scam_urgency`, `scam_compensation`, `scam_listing`.
- `job`: a dict that `JobListing` accepts (title, company, description, and, when useful, `salary_range`, `recruiter_email`, `source_url`).
- `expected`: `scam` or `legit`.
- `indicator_groups`: for a scam, the groups that the posting shows (one or more); empty for a legitimate posting.
- `source`: `fixture:<path>#<index or id>` or `written`.
- `note`: why the label is right, in one or two sentences.

**Counts.** At least 40 cases:

- At least 20 legitimate: every usable public posting from the source fixtures (`tests/fixtures/careersatgov/`, `jobstreet/`, `mycareersfuture/`, `jd_paste/`; about 12, some are search-page teasers, and that is real input), then written legitimate postings, and at least 6 hard negatives.
- At least 20 scams, with at least 4 cases for each indicator group. A scam can show more than one group.

**Hard negatives.** Legitimate postings, each realistic and each legitimate for a reason a recruiter accepts. Write your own words for each form:

1. a signal processing role;
2. a posting that offers competitive pay and the chance to work on a named product;
3. an integration role for the WhatsApp Business API;
4. an engineering role at a bitcoin exchange;
5. a legitimate posting with an anti-fraud notice that names payment words (for example, that the company never asks candidates to pay a fee or buy equipment);
6. a senior role with an annual maximum above 156,000.

**Rules for written postings.**

- Write each posting for its own company and role. Do not copy text from EMSCAD or another dataset into the committed set (license; decision 3).
- Voice: no sentence names the dataset, a label, or the test. "label", "test case", "indicator", "dataset", and "this posting is" never appear. "scam" and "fraud" may appear only in the anti-fraud notice of a hard negative, and its note says so.
- Use real-looking but fictional company names. A company is in at most 2 cases.

**Dataset tests** (`test_scam_dataset.py`), written before the cases, so they fail first:

- Structure: every case loads as `ScamCase`, and its `job` loads as `JobListing`; IDs are unique; the group prefix is valid; `expected` agrees with the group (`scam_*` is `scam`; `legit_*` and `hard_negative` are `legit`); `indicator_groups` is not empty for a scam and is empty for a legitimate posting; the counts above hold; each `fixture:` source exists and its description is the fixture text.
- Diversity for written cases (long sentence: 8 or more words, digits as `#`):
    - S1: a long sentence is in at most 2 cases;
    - S2: two cases share at most 1 long sentence;
    - S3: distinct long sentences divided by all long sentences is at least 0.90;
    - S4: with the company and the title replaced by slots, a sentence frame is in at most 3 cases;
    - S5: a 4-word sentence opening (company replaced) is in at most 4 cases;
    - S6: at least 25 distinct companies;
    - S7: the Voice rule above;
    - S8: word counts from 30 to 450, with at least 6 written postings over 200 words.
- These limits are a floor, not the goal. A writer can meet a limit by filling a slot (`docs/lessons.md`). After the tests pass, read 10 cases from start to end and check that each one reads like a real posting.

### A2. The `scam` and `emscad` suites

- **`src/evaluation/suites/scam.py`:** `run_scam_suite(dataset_dir) -> EvalReport`. The decision for each case is the pipeline decision: `ScamFilter.is_potential_scam(job)` or `JobScamDetector(threshold=0.7).detect(job).is_scam`. Metrics: `precision`, `recall`, and `f1` for the class `scam`; `false_positive_rate` (legitimate postings flagged, divided by legitimate postings); `recall.<group>` for each indicator group. Details: the confusion counts; one row per case with the expected and predicted label, whether the quick filter fired, the detector confidence, and the detector reasons; and a threshold sweep of the detector alone (0.00 to 1.00 in steps of 0.05: precision, recall, F1, and false-positive rate). The sweep is for review; Stage A does not change the threshold.
- **`src/evaluation/suites/emscad.py`:** move the row mapping of notebook cell 8 into `load_emscad(csv_path)`. Add `split_emscad(rows, seed=20261024, held_out_fraction=0.5)`: deterministic, stratified by the `fraudulent` column. `run_emscad_suite(dataset_dir, part="tuning")` reports the same metrics on that part. The metadata has the SHA-256 of the CSV, the part, the seed, and the row counts. A missing CSV raises `FileNotFoundError` with the path and a pointer to decision 3. The notebook does not change in Stage A.
- **Registry and CLI:** add `scam` (default folder `tests/fixtures/eval/scam`) and `emscad` (default folder `data/kaggle`) to `SUITE_NAMES` and `get_suite` (`src/evaluation/suites/__init__.py`). Add `--part {tuning,heldout}` (default `tuning`) to `python main.py eval`; only `emscad` uses it. MLflow logging works as for `grounding`.
- **Tests** on small datasets that the test writes to `tmp_path`, with new names: a quick-filter hit is a scam even when the detector confidence is low; metric values on a known small set; per-group recall; the false-positive rate; the sweep; the EMSCAD mapping of a small CSV; the split (the same seed gives the same parts, the parts do not share a row, and both labels are in both parts); the missing-CSV message; the registry and `--part`.
- **Mutation proofs:** (1) the decision without the quick filter, and a test must fail; (2) the split without the seed, and the determinism test must fail. Check the checksum and a fixed-string count, and restore and compare with the backup.

### A3. Baselines

- After the A1 commit, run the committed set one time:

    Run the scam suite on the committed set (from `apps/backend-py`):

    ```bash
    .venv/bin/python main.py eval scam
    ```

- If the CSV is in `apps/backend-py/data/kaggle/`, run the tuning part one time:

    Run the EMSCAD tuning part (from `apps/backend-py`):

    ```bash
    .venv/bin/python main.py eval emscad --part tuning
    ```

- Record both in this file's results section: the dataset SHA-256, the MLflow run, the metrics, the confusion counts, recall per group, the false positives (case ID, which component fired, and the reasons), and the sweep table. Do not change a label or a case after this run.

## 3. Traps

- **No detector output while you write or label** (section 2).
- **The held-out part** runs one time, in Stage B. A look at it now uses it up.
- **EMSCAD is local only.** Do not commit the CSV, a sample of it, or text from it. Outputs go to `apps/backend-py/data/`.
- **No real data and no secrets.** Never open `.env`, `.env.local`, or `apps/backend-py/data/settings/user_settings.json`. Do not run the first cells of the notebook: they load `.env` and call the Kaggle API.
- **No fixes in Stage A.** Do not change `src/scoring/`, even when a false positive is obvious. Write it in the summary.
- **Templating.** See A1. The review counts openings and reads cases.
- **Startup time.** `main.py` takes about 100 s to start on `/mnt/d`; the full backend suite takes 3 to 8 minutes. Run long commands in the background.
- **Line endings and scratch files.** `*.jsonl` is LF (`.gitattributes`). Check `git ls-files --eol` before you commit, and do not commit the 14 files that Cursor rewrites with CRLF. Put scratch files and commit messages outside the repository; use `git commit -F <file>`.

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

- Follow `CLAUDE.md`: docstrings with description, arguments, and returns; type hints; ASD-STE100 for documentation; no emojis; a Mermaid diagram in documentation.
- Before each commit, run `git status --short` and stage only the files of that step.
- Never run `scripts/mypy_gate.py --update` to accept a new error.
- Keep dry run as the default. Do not make auto-submit reachable.
- Do not push. Push only from WSL, and only after the user approves.

## 6. Summary to leave for the user

At the end of this file, add "Cursor results (date)" with:

- The commits (hash and subject): A1, A2, and A3.
- A1: the counts per group, the dataset test failure output before the cases existed, the S1 to S8 stats, the list of hard negatives (case ID and form), and a statement that no detector ran before the A1 commit.
- A2: the tests and their failure output before the code, and the two mutation results.
- A3: the baseline tables (section A3), or a statement that the CSV was not there.
- False positives or misses that look like R3 items (for Stage B; do not fix them).
- Every check you ran and its result. Say clearly what you did not run.

## Cursor results (2026-10-24)

Stop after this section. Stage B is not started. Nothing is pushed.

### Commits

| Step | Hash | Subject |
|------|------|---------|
| A1 | `26988ab` | feat(eval): add the labeled scam set and dataset tests |
| A2 | `8615c3f` | feat(eval): add the scam and EMSCAD evaluation suites |
| A3 | *(this commit)* | docs(tasks): record Stage A baselines for the scam set |

### A1. Guide, cases, and dataset tests

No detector ran before the A1 commit. Labels come from the guide only. `JobScamDetector`, `ScamFilter`, `main.py eval`, and the notebook were not run on the cases until A3.

**Counts.** 46 cases. 24 legit, 22 scam.

| Group | Count |
|-------|------:|
| `legit_fixture` | 12 |
| `legit_written` | 6 |
| `hard_negative` | 6 |
| `scam_payment` | 4 |
| `scam_contact` | 4 |
| `scam_urgency` | 4 |
| `scam_compensation` | 4 |
| `scam_listing` | 6 |

Scam indicator support (a case can list more than one group): payment 5, contact 6, urgency 5, compensation 4, listing_quality 7.

**Dataset tests before the cases existed.** Both tests failed with:

```
FileNotFoundError: [Errno 2] No such file or directory:
  .../tests/fixtures/eval/scam/cases.jsonl
```

**S1 to S8 stats** (written cases; 34 written, 12 fixtures):

| Limit | Value | Floor |
|-------|-------|-------|
| S1 max cases for one long sentence | 1 | 2 |
| S2 max shared long sentences | 0 | 1 |
| S3 distinct / all long sentences | 208 / 208 (1.000) | 0.90 |
| S4 max cases for one slot frame | 1 | 3 |
| S5 max cases for one 4-word opening | 1 | 4 |
| S6 distinct companies | 45 | 25 |
| S6 max cases per company | 2 | 2 |
| S7 Voice | pass | — |
| S8 written word min / max | 55 / 248 | 30–450 |
| S8 written postings over 200 words | 6 | 6 |

After the tests passed, 10 cases were read from start to end (`legit_fixture__jobstreet_software`, `legit_written__harbor_kiln_planner`, the six hard negatives, `scam_payment__amberline_training_fee`, `scam_contact__novachat_whatsapp`, `scam_listing__quiet_mandate`). Each one reads as a posting, not as a filled slot.

**Hard negatives**

| Case ID | Form |
|---------|------|
| `hard_negative__signal_processing` | 1. Signal processing role (Tidewell Instruments) |
| `hard_negative__competitive_hearthline` | 2. Competitive pay and the chance to work on Hearthline |
| `hard_negative__whatsapp_business_api` | 3. WhatsApp Business API integration (Riverton Commerce) |
| `hard_negative__bitcoin_exchange` | 4. Matching-engine role at a bitcoin exchange |
| `hard_negative__antifraud_notice` | 5. Anti-fraud notice that uses "scam" and "fraud" |
| `hard_negative__summit_ridge_revenue` | 6. Senior role, annual maximum 185000 |

### A2. Suites, CLI, tests, mutations

**Tests before the code.** `tests/unit/test_scam_suite.py` failed at collection:

```
ModuleNotFoundError: No module named 'src.evaluation.suites.emscad'
```

After the implementation, the 10 suite tests passed.

**Mutation 1.** `predicted = filter_hit or report.is_scam` count 1. After the line became `predicted = report.is_scam`, the count was 0 and `test_quick_filter_hit_is_scam_when_detector_is_low` failed (`assert 'legit' == 'scam'`). Restored. SHA-256 of `scam.py` matched the backup: `20849a516fcf24820e03fed3f6f6af64e1ca9aa5daeb434340b08bed6a58b34d`.

**Mutation 2.** `random.Random(seed)` count 1. After the line became `random.Random()`, the count was 0 and `test_split_is_seeded_stratified_and_disjoint` failed (the two splits differed). Restored. SHA-256 of `emscad.py` matched the backup: `5796c81ef35dbd50dedc4101f85d057c29a9f45ee42a198da5e959227bf50d14`.

### A3. Baselines

**Committed scam set** (one run after A1, command after A2).

```
.venv/bin/python main.py eval scam
```

| Field | Value |
|-------|-------|
| Report | `apps/backend-py/data/eval/scam/20261024T083147042694Z.json` |
| MLflow run | `6be4c68d79414182a08f05ff09b184c7` |
| Dataset SHA-256 | `ba3dad4f68c85cf42d23fc17dddc4c50b148393429e5ff88d6513413c9dfda2e` |
| Git SHA | `8615c3f` (dirty: the 14 unstaged CRLF rewrites) |
| Cases | 46 |
| Precision | 0.5000 |
| Recall | 0.2273 |
| F1 | 0.3125 |
| False-positive rate | 0.2083 |
| `recall.payment` | 0.4000 |
| `recall.contact` | 0.1667 |
| `recall.urgency` | 0.4000 |
| `recall.compensation` | 0.2500 |
| `recall.listing_quality` | 0.0000 |

Confusion: TP 5, FP 5, FN 17, TN 19.

**False positives** (all five are hard negatives)

| Case ID | Component | Reasons |
|---------|-----------|---------|
| `hard_negative__signal_processing` | Detector 0.80 | `signal`; `no.*interview` |
| `hard_negative__competitive_hearthline` | Detector 0.90 | `pay.*to.*work`; `no.*interview` |
| `hard_negative__whatsapp_business_api` | Detector 0.80 | `whatsapp`; `no.*interview` |
| `hard_negative__bitcoin_exchange` | Quick filter | `bitcoin` substring. Detector 0.10 |
| `hard_negative__antifraud_notice` | Quick filter and detector 0.90 | Filter: `gift cards`. Detector: `buy.*equipment`; `no.*interview` |

`hard_negative__summit_ridge_revenue` stayed legit (detector 0.40, high implied hourly rate). Labels were not changed after this run.

**Detector-only sweep** (quick filter off)

| Threshold | Precision | Recall | F1 | FPR |
|----------:|----------:|-------:|---:|----:|
| 0.00 | 0.478 | 1.000 | 0.647 | 1.000 |
| 0.15 | 0.452 | 0.636 | 0.528 | 0.708 |
| 0.35 | 0.667 | 0.636 | 0.651 | 0.292 |
| 0.50 | 0.733 | 0.500 | 0.595 | 0.167 |
| 0.70 | 0.500 | 0.182 | 0.267 | 0.167 |
| 0.90 | 0.500 | 0.091 | 0.154 | 0.083 |
| 1.00 | n/a | 0.000 | n/a | 0.000 |

The 0.70 sweep row is detector-only, so recall is lower than the pipeline recall (0.227), which includes the two quick-filter hits.

**EMSCAD.** `apps/backend-py/data/kaggle/fake_job_postings.csv` was not present. The EMSCAD tuning baseline was skipped. The held-out part was not run.

### R3 items for Stage B (not fixed)

The five false positives above are the R3 forms: bare `signal` / `whatsapp` / `telegram`, `pay.*to.*work` across a legitimate product sentence, `no.*interview` across a later "interview" word, `buy.*equipment` in a warning, and the `ScamFilter` substrings `bitcoin` and `gift cards`. Do not change `src/scoring/` in this stage.

### Checks

| Check | Result |
|-------|--------|
| A1 dataset tests before cases | 2 failed (`FileNotFoundError`) |
| A1 dataset tests after cases | 2 passed |
| A1 Black / ruff / mypy gate | pass (182 known, 0 new) |
| A1 full pytest | 1211 passed |
| A2 suite tests before code | collection error (`emscad` missing) |
| A2 suite tests after code | 10 passed |
| A2 mutations | both required tests failed; files restored; checksums matched |
| A2 Black / ruff / mypy gate | pass (182 known, 0 new) |
| A2 full pytest | 1221 passed |
| A3 `main.py eval scam` | report and MLflow run above |
| A3 Black / ruff / mypy / full pytest | run before this commit |

**Not run.** EMSCAD tuning (CSV missing). EMSCAD held-out (Stage B only). Notebook cells. `JobScamDetector` / `ScamFilter` / `main.py eval` on the cases before the A1 commit. Any change in `src/scoring/`. `.env`, `.env.local`, and `user_settings.json`. Push.
