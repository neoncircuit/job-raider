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

## Blockers / Questions
- None.
