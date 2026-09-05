# Changelog

All notable changes to Job Raider are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
while remaining on **0.x** (MINOR = feature checkpoint, PATCH = fix-only).

The product version lives in the root `VERSION` file. Annotated git tags
`vX.Y.Z` are the release checkpoints (CI may publish Docker images on `v*`).

`0.1.0` is a **retroactive checkpoint** of the product as of commit `5732673`.
It includes substantial work completed before Cursor-assisted sessions (the
original pipeline and dashboard), not only later cover-letter and Singapore
board work. We do not invent earlier `v0.0.x` tags for that history.

## [Unreleased]

### Added

- Root `VERSION` file as product semver source of truth; FastAPI and
  `/api/version` read it; Docker images copy it to `/app/VERSION`.
- `CHANGELOG.md` and documented bump/tag release ritual.
- Cover letter **Export full analysis** (JSON) plus letter-only PDF export.
- Cover letter mission **Sources** citations when company-mission grounding passes.
- Profile **Download PDF** structured summary export.
- Evidence-weighted skills radar with relative scaling on Profile.
- Cover letter result strip shows LLM token usage (in/out when available).
- Safe cover-letter model A/B harness (`scripts/compare_cover_letter_models.py`)
  for `qwen2.5:7b` vs `qwen3.5:4b` only.

### Fixed

- Fabricated-technology checks ignore honest disclaimers and learn-intent
  phrasing (claim-direction aware).
- JobMatcher fit breakdown lists only active weight categories (no phantom
  education/projects zeros in standard mode).

## [0.1.0] - 2026-08-21

Baseline annotated tag on `5732673` (cover-letter Phase A–C ship). First formal
semver tag for the monorepo. App metadata had already advertised `0.1.0`
without a git tag.

### Pre-Cursor foundation

Work that defined Job Raider before Cursor-assisted development (captured from
the early commit history and product surface; initial tree was even labeled
informally as “Job Raider v1.0” in the first commit message):

- End-to-end job pipeline: scrape/aggregate, dedupe, filter, score, generate,
  and submit (with dry-run).
- Multi-platform aggregation (LinkedIn Playwright, JSearch, and related boards).
- Heuristic relevance scoring, scam/trust signals, and fresh-graduate scoring mode.
- Hybrid RAG (BM25, cross-encoder rerank, RRF) and ChromaDB-backed matching.
- Two-model resume selection/writing (local Ollama + optional cloud fallbacks).
- Resume analysis, LinkedIn profile analysis, and Easy Apply automation paths.
- Cover letter generation with validation (early pipeline-integrated path).
- Multi-agent career coaching API, DISC assessment, and technical interview trainer.
- Next.js dashboard (themes, Jobs, Dashboard, Settings) and FastAPI backend monorepo.
- Docker Compose stack, MLflow as a shared service, CI greening, and test infrastructure
  (pytest, Vitest, Playwright).

### Also included in this checkpoint

Shipped on `main` by the tag tip (after the foundation above), still part of
`v0.1.0`:

- Singapore job sources (MyCareersFuture, JobStreet SG, Careers@Gov delayed catalog).
- Applications tracker hardening (applied-elsewhere, interview lifecycle, listing links).
- Cover letter local-first drafting improvements, optional review/rewrite, and
  deterministic proofreading with severity-weighted grounding.
- Cover letter Phase B opt-in company-mission grounding and Phase C JD
  application-instruction detection (length asks and inclusion URLs).
- Opt-in classic cover letter style; paste-JD shared structuring; appearance
  color schemes and related UI polish.
- App-wide datetime prefs and resume Technical Skills extraction hardening.

### Notes

- Formal tags start at `v0.1.0`. Earlier informal “v1.0” wording in the first
  commit is historical only; the project stays on intentional **0.x** semver
  until a deliberate `1.0.0` stability cut.
- Root `VERSION` and changelog plumbing may land in commits after the tag tip;
  the product label for this checkpoint remains `0.1.0` until the next release.

[Unreleased]: https://github.com/neoncircuit/job-raider/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/neoncircuit/job-raider/releases/tag/v0.1.0
