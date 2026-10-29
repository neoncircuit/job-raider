# Task: Resume Generation Fix

## Goal
Make full-mode resume generation produce resumes again. Today every draft fails, because the selector, the writer, and the validator do not agree on the shape of the data (causes in `notes.md`). The fix is four small test-first changes, done by a local 7B model from micro-handoffs, and checked by Claude.

## Constraints & Context
- Found in the Step 3.6 real runs (2026-10-28). It blocks the Step 1 manual check (`tasks/active/step-1-core-flow/`).
- The implementer is a local model (`qwen2.5-coder:7b` with Aider, or `deepseek-coder:6.7b`). Each micro-handoff is one small change with its test given in full. The agent reads `AGENT.md` and one `mh-*.md` file, nothing else.
- Do not change the prompts' meaning beyond what each micro-handoff says. Do not change routing, the models, or the validator's thresholds.
- No personal data in tests: use the `sample_user_profile` and `sample_job_listing` fixtures.
- Keep dry run as the default. Do not make auto-submit reachable.

## Acceptance Criteria
- [x] MH-1 (`8f25bf8`, checked 2026-10-28). `flatten_skills` in `src/generation/resume_writer.py` turns any skills shape into one flat list of strings, and `ResumeWriter.write` uses it. The writer prompt asks for a flat list. (`mh-1-flatten-skills.md`)
- [x] MH-2 (`3847293`, checked 2026-10-29). `ResumeValidator.validate` checks the flattened skills and does not crash on a skill or a keyword that is not a string. (`mh-2-validator-skills.md`)
- [x] MH-3 (`f3f4e6c`, checked 2026-10-29). `ResumeSelector.select` keeps only projects from the profile, with the profile's spelling, and asks for no more projects than the profile has. (`mh-3-selector-projects.md`)
- [x] MH-4 (`03d60e8`, checked 2026-10-29). `ResumeWriter.write` gives each draft project the profile's name when the names match without case and without a trailing "(...)". (`mh-4-project-names.md`)
- [x] MH-5 (`7e8a9b5`, checked 2026-10-29). `ResumeSelector.select` keeps only keywords that are profile skills, with the profile's spelling, and the prompt asks for profile skills that the job asks for. (`mh-5-selector-keywords.md`)
- [x] MH-6 (`7f7561c`, checked 2026-10-29). `ResumeWriter.write` keeps only profile skills in the skills list and adds the selected keywords; when no skill is left, it uses the profile's skills. (`mh-6-writer-profile-skills.md`)
- [x] Check of MH-5 and MH-6 (Claude, in `notes.md`): the diffs, mutation proofs, the full gate, and the reproduction with the real profile. Done 2026-10-29: 1698 tests pass; 16 of 19 mutations caught (the 3 survivors are gaps in the handoff tests); both drafts pass the validator with score 100.
- [x] Check (Claude, in `notes.md`): the diffs, the full backend gate, mutation proofs for each change, and the reproduction script again against the real profile and Ollama. Done 2026-10-29: 1691 tests pass; 18 of 20 mutations caught (the 2 survivors are gaps in the handoff tests); the drafts now fail only on skills that are not in the profile.
- [ ] Done when: the reproduction gives drafts that pass the validator (or fail only on real issues, such as a skill that is not in the profile), and a full-mode dry run generates at least one resume.

## Status
`in-progress` (MH-1 to MH-6 checked on 2026-10-29; the reproduction passes; the full-mode dry run generated 2 valid DOCX resumes; the resume PDF fails, see `notes.md`)
