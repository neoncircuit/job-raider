# Scratchpad & Notes

## Plan (2026-11-03, Claude)

### What exists today

- Heuristic matcher, `src/scoring/matcher.py`:
  - `_score_keywords` (line 212) and `_score_skills_from_description` (line 290) match with plain substrings (`keyword in text`), so "ai" matches "email" and the skill "Java" matches every "JavaScript" job. The grounding profile `grad` has both Java and JavaScript, so this trap is real.
  - `_score_skills_from_description`: no match gives half the weight (20 of 40); one match out of many profile skills gives `max(score, weight // 4)` = 10 of 40. More matches can give a lower score.
- RAG ranker, `src/rag/ranker.py`:
  - Dense results use `job_id` as the document ID (line 408); BM25 results use chunk IDs `<job_id>_chunk_<n>` (line 160). `reciprocal_rank_fusion` fuses by document ID, so a job never gets a fused score from both lists.
  - Jobs that the hybrid step returns get a min-max-normalized RRF score; the other jobs get a dense cosine similarity (lines 292 to 302). The two are on different scales.
  - Found while planning: `_build_profile_query_text` reads `profile.professional_summary` and `profile.target_job`, but `UserProfile` has `summary` and `targets`. The `hasattr` checks fail without an error, so the BM25 query is the skill names only.
  - Found while planning: `index_profile` adds the profile's own chunks to the same BM25 index that the job search uses, so a BM25 query can return profile chunks.
- Data: the source fixtures (`careersatgov`, `jobstreet`, `mycareersfuture`) hold 3 listings each. The grounding set has 65 constructed jobs (about 41 words each, no structured skills) for 3 small profiles (3 or 4 skills). The dedupe set is constructed (31 pairs).

### Proposed set

- 2 synthetic profiles in the shape of real users: a fresh graduate (backend and machine learning projects, close to the user's own search) and a mid-level backend engineer. Richer than the grounding profiles: summary, 8 to 12 skills, projects, targets.
- About 35 constructed jobs for each profile (about 70 jobs), written in the shape of real postings (120 to 250 words): some with structured skills, some description only (pasted). A mix of clear fits, partial fits, seniority mismatches (the backlog finding that senior roles rank high for a fresh graduate), and traps for R4: "Java" against JavaScript-only jobs, "AI" against "email" and "maintain", "SQL" against PostgreSQL, "React" against "reactive", "Go" against "good".
- Each profile is ranked against all jobs of the set (both profiles' jobs), so each profile has about 70 candidates and the other profile's jobs give natural "not relevant" and "maybe" cases.
- Labels 0, 1, 2 for each of about 140 pairs, with a one-line reason. Labeling guide in `tests/fixtures/eval/ranking/README.md` (rules first, labels before any ranker runs).

### Metrics

- NDCG@10 with gains 2 and 1; recall@10 of the jobs labeled 2; for each profile and the mean over the profiles.
- Methods: heuristic (`JobMatcher.rank_jobs`), BM25 only, dense only, hybrid (the `RAGRanker` path). BM25 and dense use the ranker's own profile query and job chunks.

### Micro-handoffs (outline)

1. The set and its guide (Claude writes the profiles and jobs; labels drafted by Claude, checked by the user), with a format test.
2. The suite with heuristic and BM25 (CI), and its tests.
3. Dense and hybrid in the suite (local; temporary vector store), and its tests.
4. Baseline run (local; embedding model only).
5. R4 fix, with tests; measure.
6. R5 fix (fusion, score scale, query fields, profile chunks), with tests; measure.
7. CI thresholds, docs, decision log.

Runner handoffs for the data and the suite; spec handoffs for the fixes where they fit an agent.

### Choices for the check-in

1. Job pool: a new constructed set (2 richer profiles, about 70 realistic jobs with traps), or the 65 thin grounding jobs plus about 10 traps (quicker to make, weaker test).
2. Labels: Claude drafts all of about 140 labels with reasons and the user checks them all, or the user checks a sample of about 40.

## Decisions (user, 2026-11-03)

1. Job pool: the new constructed set (2 synthetic profiles, about 70 constructed jobs with seniority mismatches and the R4 traps).
2. Labels: Claude drafts every label with a one-line reason before any ranker runs; the user checks all of them. This changes decision 1 of 2026-10-22 (the user labels the pairs) in the same way as the real-letter decision of 2026-10-30.

## Draft set written (2026-11-03, Claude)

`draft/` holds the labeling guide (`README.md`), the two synthetic profiles (`profiles.py`, with `MODES`: `fresh_ml` uses `fresh_grad_mode`), 70 constructed jobs with a draft label for each profile (`jobs_ml.py`: rk-001 to rk-035; `jobs_backend.py`: rk-036 to rk-070), and `build_set.py`, which validates every profile and job against the app models and writes `draft/out/` (`profiles.json`, `modes.json`, `jobs.jsonl`, `labels.jsonl`) and `label-review.md`.

- Profiles: `fresh_ml` (0.5 years from one internship; targets machine learning engineer, data scientist, AI; entry level; 12 skills; 3 projects) and `mid_backend` (4.4 years from two jobs; targets backend engineer, platform engineer, Java; mid level; 11 skills).
- Jobs: 57 with required skills and 13 without (the matcher's description path, as for a pasted job description). Fewer description-only jobs than planned; the description-path jobs are rk-003, rk-007, rk-018, rk-019, rk-021, rk-022, rk-023, rk-027, rk-031, rk-035, rk-051, rk-052, and rk-062, so the skill traps "Git" in digital (rk-021) and "Go" in good, going, Google, and goal (rk-023, rk-051, rk-052) reach that path. The keyword traps ("AI" and "Java" in the profile targets) reach every job, because keywords are matched in the title and description. Traps for R4: "AI" against email, maintain, detail, retail, and training (rk-019 to rk-023); "Git" against digital (rk-021); "Java" against JavaScript (rk-044, rk-045); "Go" against good, going, Google, goal, Django, and MongoDB (rk-023, rk-043, rk-051, rk-052, rk-056).
- Draft labels: `fresh_ml` 8 apply, 19 maybe, 43 not relevant; `mid_backend` 11, 17, 42.
- The guide changed once while drafting, before any ranker ran: the label rules now give every pair one label (a target role or a role next to it, at most one level step off, is at least `1`; `2` needs a target role, the right level, and most required skills), and "role next to a target role" names software roles in the profile's main language for a machine learning profile.
- No ranker has run on the set. The user checks every label in `label-review.md`.

## Label check (user, 2026-11-03)

The user chose yes-or-no questions over the review sheet (the set is synthetic, so the questions ask whether a job fits a made-up profile). Claude asked about the label rules and the borderline cases, so each answer covers a group of labels.

| Round | Question | Answer |
|-------|----------|--------|
| 1 | Fresh graduate: mid-level ML and data jobs (rk-005, 011, 012, 017, 025, 033) are 1 | Yes |
| 1 | Fresh graduate: the AI internship (rk-013) is 1 | Yes |
| 1 | Fresh graduate: nearby data roles (rk-008, 009, 010, 015, 034, 035, 048) are 1 | Yes |
| 1 | Fresh graduate: Python or any-language software jobs (rk-026, 043, 062) are 1; Java-only or Go-only backend jobs are 0 | Yes |
| 2 | Backend engineer: senior one step up (rk-028, 040, 063) is 1; lead, staff, principal (rk-041, 054, 064) are 0 | Yes |
| 2 | Backend engineer: junior and graduate one step down (rk-009, 010, 026, 042, 062) are 1; internships (rk-013, 053) are 0 | Yes |
| 2 | Backend engineer: roles next to backend (rk-045 to 049, 057, 059) are 1 | Yes |
| 2 | Backend engineer: backend in another stack (rk-043, 061) is 1 | Yes |
| 3 | Backend engineer: QA automation (rk-058) and DBA (rk-065) are 0 | Yes |
| 3 | Backend engineer: the AI engineer job with FastAPI services (rk-003) is 0 | No: make it 1 |
| 3 | Backend engineer: Kotlin backend (rk-055) is 2 | Yes |
| 3 | Backend engineer: search backend (rk-060) and ML platform (rk-024) are 2 | Yes |
| 4 | rk-030 is 1; rk-019 and rk-031 are 0; the clear fits are 2; the clear non-fits are 0 | Not answered: the user said "I'll just let you decide what is considered sensible"; Claude kept the drafts, which follow the rules that rounds 1 to 3 confirmed |

Result: rk-003 for `mid_backend` changed from 0 to 1, with a new line in the guide's terms and its Changes section. Final counts: `fresh_ml` 8 apply, 19 maybe, 43 not relevant; `mid_backend` 11, 18, 41. The labels are final; no ranker has run on the set.

## MH-1 written and checked (2026-11-03, Claude)

`mh-1-ranking-set.md` (runner): `profiles.json`, `modes.json`, `jobs.jsonl`, and `labels.jsonl` in `tests/fixtures/eval/ranking/` (from `draft/build_set.py`), and `tests/unit/test_ranking_set.py` (5 tests: the models, the matcher modes, unique job IDs, one label of 0 to 2 with a reason for each pair, the label mix for each profile, and the guide's label rules).

- The guide (`tests/fixtures/eval/ranking/README.md`) is in Claude's docs commit, not in the handoff: it has a Mermaid fence, and the runner's fence pattern (`FENCE_RE` in `scripts/run_handoff.py`) reads only three-backtick blocks, so a four-backtick block that holds the guide would be skipped.
- Scratch clone (guide in place): red 4 failed and 1 passed (the guide test); black leaves the test unchanged; ruff clean; 5 passed; the mypy gate has 0 new errors.
- Data mutants 8 of 8 caught (duplicate job, label 3, missing label, profile without a name, wrong matcher mode, no apply labels for a profile, empty reason, guide without the label-first rule).
- The guide is committed (`c0865af`). Runner test on a fresh clone at that commit: the red step failed, the 4 checks passed, commit `32d24ce` on the clone, and the five files are the same bytes as the checked copies.
- MH-1 applied on the repo (2026-11-03, Claude ran the runner on the user's word "Yes, apply it"): commit `de901a4`. The red step failed, and the 4 checks passed. The apply script compared the files with the runner-test clone in WSL `/tmp`, which was gone, so it printed "DIFFERENT" for each file; a second comparison with the sources (the checked test copy and `draft/out/`) shows the five committed files are the same bytes.

The ranking set is in the repository and final. Next: MH-2, the `ranking` eval suite with the heuristic matcher and BM25.

## MH-2 written and checked (2026-11-03, Claude)

`mh-2-ranking-suite.md` (runner): `src/evaluation/suites/ranking.py` (`load_ranking_set`, `sort_scores`, `heuristic_ranking`, `profile_query`, `bm25_ranking`, `ndcg_at_k`, `recall_at_k`, `run_ranking_suite`), `tests/unit/test_ranking_suite.py` (14 tests), the registry, one `eval` help example, and the pinned suite names in `test_scam_suite.py`.

- `heuristic` uses the profile's `fresh_grad_mode`; `bm25` indexes the job chunks of the RAG chunker (`config/rag_config.yaml`), queries with `RAGRanker._build_profile_query_text` (so the query bug is measured), and takes each job's best chunk score. The current code has no BM25-only ranking; this method measures the BM25 half of the hybrid ranker.
- NDCG@10 with the label as the gain; recall@10 of the jobs labeled 2. Ties broken by job ID.
- Scratch clone (exit codes printed): red is a collection error (exit 2); black reformatted the two new files; ruff clean; 96 tests pass (the new file, the set, scam, CLI, dedupe, and writer command tests); the mypy gate has 0 new errors.
- Mutants 12 of 12 caught (NDCG discount off by one, ideal order not sorted, recall counts label 1, ties not broken by job ID, heuristic ignores the mode, BM25 keeps the last chunk, BM25 builds its own query, mean is the first profile, missing labels accepted, suite not in the registry, NDCG and recall ignore the cut-off).
- First numbers on the scratch clone (not the baseline run; the labels were final before it ran):

| Method | NDCG@10 `fresh_ml` | NDCG@10 `mid_backend` | NDCG@10 mean | Recall@10 mean |
|--------|--------------------|-----------------------|--------------|----------------|
| heuristic | 0.720 | 0.857 | 0.788 | 0.506 |
| bm25 | 0.864 | 0.900 | 0.882 | 0.693 |

The heuristic matcher puts 3 of the 8 `apply` jobs of the fresh graduate in its top 10 (recall 0.375).

- Runner test on a fresh clone: the red step failed (exit 2), the 4 checks passed, commit `670c18a` on the clone, and the five files are the same bytes as the checked copies.
- MH-2 applied on the repo (2026-11-03, Claude ran the runner on the user's word "Yes, apply it"): commit `e450d91`. The red step failed, and the 4 checks passed. The two new files are the same bytes as the checked copies, and the three edited files are the same as in the runner test.

Next: MH-3, the dense and hybrid methods (local; the embedding model `nomic-embed-text`). The official baseline runs after MH-3, so all four methods share one code state; MH-3 does not change the heuristic and BM25 methods.

## Blockers / Questions
- None.
