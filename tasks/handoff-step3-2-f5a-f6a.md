# Handoff: Step 3.2 Rework F5a and F6a (2026-10-23)

Read this file first. Then read `CLAUDE.md` (project rules), and these parts of `tasks/todo.md` (under **Now**, Step 3.2): the "Step 3.2 fix plan", the F5 and F6 items with their Done notes, "Review of F4 to F7", and "Decisions after F4 to F7". Also read the labeling guide `apps/backend-py/tests/fixtures/eval/grounding/README.md` and the last section of `tasks/lessons.md` ("A perfect score on a dev set says nothing about phrasings the set lacks"). `tasks/handoff-step3-2-f4-f7.md` shows the format that worked for F4 to F7. The check commands are in section 4 of `tasks/handoff-2026-10-19.md`.

The user will review your work after F6a.

## 1. Status

| Item | State |
|------|-------|
| `main` | 24 commits ahead of `origin/main` (not pushed). Do not push. |
| Last eval | After F7, on the main set: micro F1 0.793, MLflow run `f62f6ce8206f4618ac7831b58209ef26`. The table is in `tasks/todo.md` under F7. Use it as the "before" for F5a. |
| Why this rework | The main-set precision of `scope_inflation` and `fabricated_experience` is 1.000, but probes with new sentences found 15 false flags and 3 misses in these two checks. The main set has none of those phrasings. The F6 tests also reuse main-set sentences. The review lists each failure class. |
| Holdout | **Do not open** `cases.jsonl` or `profiles.json` in `apps/backend-py/tests/fixtures/eval/grounding_holdout/`. You may read its `README.md`. |
| `ungrounded_claims` | Still predicted on 64 of 65 cases. D6 changes how it is measured. Do not change it here. |
| This handoff | F5a, F6a, and one commit of small items. **Stop after that.** Do not start D5 or D6, and do not run the holdout. |

## 2. The task

```mermaid
flowchart LR
    F5a[F5a scope rework] --> F6a[F6a experience rework]
    F6a --> S1[S1 small items]
    S1 --> S[Stop: summary for the user]
```

For each fix, the same steps as F4 to F7:

1. Write unit tests first. Run them and keep the failure output.
2. Make the change. Rules must be general: no rule may refer to a `case_id`, a fixture file, or a fictional name from the dataset.
3. Mutation proof: put the old behavior back with an exact string replacement, check that the checksum changed and that a fixed-string count is right, see the tests fail, restore, and compare with the backup.
4. Run `python main.py eval grounding` on the main set. In `tasks/todo.md`, under the F5a or F6a item, add a "Done (date)" note with the tests, the mutation, and the per-label table (precision, recall, F1, and predicted count) against the previous run.
5. Black, ruff, and the mypy gate on `main.py scripts/mypy_gate.py src/ tests/`, and the full pytest suite. One commit per fix.

**New rule for the tests in this handoff.** Every test sentence and every name is new. Do not use a name or a sentence from `tests/fixtures/eval/grounding/cases.jsonl` or `profiles.json`. Do not copy a sentence from the review notes in `tasks/todo.md` either: the reviewer probes again with sentences that you have not seen, so a test copied from the notes proves nothing. For each failure class below, write your own ordinary sentence of that kind. Before each commit, check that no name in your new tests occurs in the main set.

Check a name against the main set (from `apps/backend-py`, one name at a time):

```bash
grep -c "Your Name Here" tests/fixtures/eval/grounding/cases.jsonl tests/fixtures/eval/grounding/profiles.json
```

The count must be 0 for every name.

**True positives to keep.** On the main set, `scope_inflation` finds 4 of 4 and `fabricated_experience` finds 6 of 8 after F7. A rework that removes false flags by removing a whole pattern also removes true positives. If a main-set true positive is lost, explain why in the Done note, or change the rule. Each pattern keeps at least one test that it still flags a real claim.

All line numbers below are for `apps/backend-py/src/generation/cover_letter_grounding.py` at `115fcd9`, unless the text names another file.

### F5a. Scope inflation

The code: `_SCOPE_INFLATION_PHRASES` (line 126), `_SCOPE_BARE_VERBS` (147), `_SCOPE_OBJECT_STOPS` (152), `_SCOPE_HEAD_RE` (176), `_leadership_claims` (1409), and `_resume_has_leadership_claim` (1444).

Failure classes from the review:

1. A bare verb takes any words after it as the object. A result ("led to a drop in ..."), a pronoun ("led me to ..."), and an infinitive ("managed to <verb>") become leadership claims.
2. "leading" used as an adjective ("a leading provider of ...", "an industry-leading ...") becomes a leadership claim. The hyphen in "industry-leading" is a word boundary, so `\bleading\b` matches there too.
3. The object ends only at the stop list or after six words. When the letter continues the claim ("a team of 3 engineers to rebuild ..."), the claim includes "to", and the profile ("a team of 3 engineers that rebuilt ...") does not contain it, so a supported claim is flagged.

Required behavior:

- After a bare verb, "to", "me", "us", and "them" do not start an object. There is no claim.
- "leading" is not a claim when the word before it is "a", "an", or "the", or when a hyphen joins it to the word before it.
- The object also ends at "to", "that", "which", "who", and "whose". The six-word limit stays.
- The comparison does not change: the claim with its object must be in the profile, and number words equal digits.

Tests: one sentence for each failure class (not flagged); a team claim that continues with "to <verb>" when the profile has the same team claim (not flagged); the same claim with a different team size (flagged); and the F5 positives ("led the", "managed a team of N", "headed", "owned the", "oversaw") still flagged with new objects.

### F6a. Fabricated experience

The code: `_ORG_NAME` (line 1775), `_EMPLOYER_RES` (1776), `_TITLE_WAS_RE` (1781), `_AS_TITLE_RE` (1786), `_DEGREE_LEVEL_RE` (1791; also used to read profile degrees at 1930), `_DEGREE_TAIL_RE` (1796), `_CERT_WORD_RE` (1803), `_profile_has_title` (1889), `_profile_has_certificate` (1945), `_certificate_name` (1964), and `flag_fabricated_experience_claims` (2023; the "as a X at Y" block starts at 2069). The validator calls it at `cover_letter_validator.py:274`.

Failure classes and required behavior:

1. **Names take the pronoun.** `_ORG_NAME` takes the next capitalized word, so "worked at <Org> I <verb>" reads "<Org> I". A name never contains the word "I".
2. **Events are employers.** `at <Org> I` reads a talk at a conference as an employer. Keep that pattern only when the word after "I" is a work verb from `_PAST_CLAIM_VERBS` (line 2248). "at <Event> I gave a talk" is not a claim; "at <Org> I built ..." still is.
3. **The "as a X at Y" pattern.**
    - It ignores case, so any words become a title ("as a result at <Org>"), and the company part accepts lowercase words. The title must end with a role noun from a short list (for example engineer, developer, analyst, scientist, intern, manager, architect, designer, consultant, researcher, administrator, specialist, lead, director, officer). The company must start with a capital letter.
    - Titles must be equal today, so a shorter title is flagged ("backend engineer" when the profile has "Senior Backend Engineer"). A letter title is supported when all its words are in one profile title. A letter title with a word that no profile title has is flagged ("Staff Engineer" when the profile has "Senior Backend Engineer"). Use the same rule for "my title was X".
    - The company Y is never checked. "as a <title on the profile> at <employer not on the profile>" passes. Y is an employer claim: flag it when it is not on the profile and is not the target company. Remove the branch at that point that cannot change the result.
    - The target job is not a claim: when the title is the target title and Y is the target company or is absent, there is no claim.
4. **Degree words in other senses.** `master` matches as a verb and in "the master branch". "master" and "bachelor" are degree words only when "'s", "of", "in", or "degree" follows them. Abbreviations (MBA, PhD, B.Sc., M.Sc.) and "doctorate" stay as they are. Do not change how profile degrees are read at line 1930.
5. **Degree field.** "a Bachelor's degree in X" does not read X, so a different field passes. Read the field after "'s degree in" and after "degree in" with no level, and compare it as today (`_field_in_text`).
6. **Certificate names.**
    - The name is only the capitalized words before the certificate word, and names must be equal. "I am an <Issuer> Certified <Role>" reads only "<Issuer>", which is not equal to the full profile name, so a real certificate is flagged. "I am a Certified <Role>" reads nothing, so a fake certificate passes. Read the capitalized words on both sides of the certificate word, and include the certificate word when it is capitalized.
    - A letter name is supported when all its words are in one profile certification name, or when it equals the issuer.
    - A certificate that the job asks for, or that the candidate plans to earn, is not a claim. Skip a certificate word when the sentence states a requirement ("asks for", "requires", "required", "preferred") or a plan ("plan to", "hope to", "want to", "would like to", "intend to"). `_is_skippable_non_claim` (line 2444) already skips a sentence that starts with a plan; you may use it.
7. **Wiring test.** No test covers the validator call. Turning it off left every unit test green. Add a test in `tests/test_cover_letter_validator.py` that runs `CoverLetterValidator(llm_router=None, strict_mode=False).validate` on a letter with a fabricated employer and no selected project, and checks that `FABRICATED_EXPERIENCE` is in the issues, and that a letter with only profile employers does not get it. The mutation proof for this test turns the call off.
8. **Tests that reuse the main set.** Rewrite the F6 tests and the F7 analogy tests that use main-set names or sentences (for example "Orbit Lantern", "Glassmill College", "Design History", "Northbridge Ledger Auditor", "Director of Engineering", "similar to the penetration-testing", "Northwind"). Keep the behavior that each test checks, with new names and sentences, and say in the summary which tests you rewrote. Also fix `test_target_company_and_ordinary_at_are_not_employers`: "I want to join <target>" matches no pattern ("joined" only), so it does not test the target-company rule. Use a sentence that a pattern does read with the target company.

Tests: for each class, a sentence that must not be flagged and, where the class is a miss, a sentence that must be flagged. Positives for each kind still flagged: an employer, a title, a degree (level and field), and a certificate that the profile does not have.

### S1. Small items (one commit)

- The first line of the second docstring paragraph of `flag_inflated_duration_claims` (line 1171) has 8 spaces of indent. Use 4.
- `_project_name_spans` (line 1464) finds a project name inside a longer word, because it uses `str.find`. Match whole words, and add a test with a project name inside a longer word.

## 3. Traps

- **The holdout set.** Opening its cases makes it useless.
- **Labels and letters do not change.** Do not edit `tests/fixtures/eval/grounding/cases.jsonl` or `profiles.json`. If you think a label is wrong, write it in the summary.
- **Narrow, not empty.** Each rule must remove a failure class and keep the real claims of that kind. Prefer a rule about the words next to the match over a rule that drops a pattern.
- **Word lists.** Keep the role-noun list and the requirement and plan phrases short and general, with a comment. Do not add a word because one main-set letter has it.
- **Existing tests.** Rewriting the tests in item 8 is a change that this handoff asks for. If any other existing test conflicts with a change, stop and ask the user.
- **No real data.** Never open `.env`, `.env.local`, or `apps/backend-py/data/settings/user_settings.json`.
- **Startup time.** `main.py` takes about 100 s to start on `/mnt/d`; the full backend suite takes 3 to 8 minutes. Run long commands in the background.
- **Line endings and scratch files.** Check `git ls-files --eol` before you commit, and do not commit the 14 files that Cursor rewrites with CRLF. Put scratch files and commit messages outside the repository; use `git commit -F <file>`.

## 4. Rules (unchanged)

- Follow `CLAUDE.md`: docstrings with description, arguments, and returns; type hints; ASD-STE100 for documentation; no emojis; a Mermaid diagram in documentation.
- Before each commit, run `git status --short` and stage only the files of that fix.
- Never run `scripts/mypy_gate.py --update` to accept a new error.
- Keep dry run as the default. Do not make auto-submit reachable.
- Do not push. Push only from WSL, and only after the user approves.

## 5. Summary to leave for the user

At the end, add "Cursor results (date)" to this file with:

- The commits (hash and subject), one for F5a, one for F6a, and one for S1.
- For each fix: what changed, the tests and their failure output before the fix, the mutation result, and the eval table against the previous run, with any label that got worse and why.
- The tests you rewrote under item 8, and the name check result for your new tests.
- Any main-set true positive that was lost, and why.
- Any label you think is wrong (do not change it).
- Every check you ran and its result. Say clearly what you did not run.

## Cursor results (2026-10-23)

Work stopped after S1. D5, D6, and the holdout were not started. Nothing was pushed.

### Commits

- `27bd81f6b5026b67642d3d060b036a525584e12e` fix(grounding): skip non-noun objects and adjective 'leading' in scope checks.
- `ec82fb277533375172cb81217f839e12b8464da3` fix(grounding): tighten employer, title, degree, and certificate checks.
- `aaf0fdfd4e04c6bfe4a1876700d711a255f794ed` fix(grounding): match project-name spans on word boundaries.

Each commit contains only the files of that item. This results section is left unstaged. `tasks/handoff-2026-10-19.md` and `tasks/handoff-step2.md` stayed untracked.

Dataset SHA-256 stayed `13e5ec3d685a45d93da14e72ac1ea5f58239b94af98f7fb909dda58278b1c2f0`. No main-set true positive was lost. No label metric got worse. No label was changed.

### F5a. Scope inflation

`_leadership_claims` skips `leading` when `a`, `an`, `the`, or a hyphen comes before it. After a bare leadership verb (`led`, `leading`, `managed`, `headed`, `oversaw`), `to`, `me`, `us`, and `them` do not start an object (`_SCOPE_NON_OBJECT_STARTS`). `_SCOPE_OBJECT_STOPS` now includes `to`, `that`, and `whose` along with `which` and `who`, so the object ends before an infinitive or a relative clause.

Tests, written before the change: 3 failed, 1 passed. Failures: `The cache index led to a shorter morning run.` was flagged (`Scope inflation: 'led to a shorter morning run'`); `We read papers from a leading lab in speech synthesis.` was flagged (`Scope inflation: 'leading lab'`); `I led a team of four engineers to rewrite the invoice parser.` was flagged against `Led a team of 4 engineers that rewrote the invoice parser.` (`Scope inflation: 'led a team of four engineers to'`). `test_scope_inflation_positives_stay_flagged_with_new_objects` already passed.

Mutation: the adjective skip, the non-object start check, and the new stops (`to`, `that`, `whose`) were replaced with the old loop body (1 occurrence). Checksum changed from `c63c2894dd6747d37193f312dccb134f20e06cd07a82ac6e4174f30c9fa11a5e` to `262455e937d83f0d88c82df438d905ee22b7185369afe756af890e2bf2d895e3`. `grep -F` count of the mutated line was 1. All 3 failure-class tests failed again. The file was restored and matched the backup byte for byte.

Eval: Git SHA `6bf4fd31c5480e1997703171daac15e0e73afd1d`, dirty true. MLflow run `09871db45a9145b391761e829168c3f6`. Report `20261023T032922271752Z.json`. No label metric changed against F7.

| Label | P before (F7) | P after | R before | R after | F1 before | F1 after | Predicted before | Predicted after |
|-------|---------------|---------|----------|---------|-----------|----------|------------------|-----------------|
| `fabricated_technology` | 0.889 | 0.889 | 1.000 | 1.000 | 0.941 | 0.941 | 9 | 9 |
| `inflated_duration` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 5 | 5 |
| `inconsistent_metric` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 3 | 3 |
| `fabricated_experience` | 1.000 | 1.000 | 0.750 | 0.750 | 0.857 | 0.857 | 6 | 6 |
| `analogical_claim` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 3 | 3 |
| `scope_inflation` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 4 | 4 |
| `technique_mismatch` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 3 | 3 |
| `ungrounded_claims` | 0.516 | 0.516 | 1.000 | 1.000 | 0.680 | 0.680 | 64 | 64 |
| micro | 0.670 | 0.670 | 0.970 | 0.970 | 0.793 | 0.793 | — | — |

### F6a. Fabricated experience

`_ORG_TOKEN` uses `(?!I\b)[A-Z][\w&.'-]*`, so a name never takes the pronoun `I`. `_AT_ORG_I_RE` matches `[Aa]t <Org> I <verb>` only when `<verb>` is in `_PAST_CLAIM_VERBS`, so an event talk (`At PyForum I gave a talk`) is skipped while `At Vesper Foundry I built` is checked. `_AS_TITLE_RE` matches `[Aa]s an? <title> at <Org>` with a capitalized company, requires the title to end with a role noun from `_TITLE_ROLE_NOUNS`, checks `<Org>` as an employer claim when it is not the target company, and removes the dead branch. `_profile_has_title` allows a letter title when all its words appear in one profile title. `bachelor` and `master` match in the letter only when `'s`, `of`, `in`, or `degree` follows them (`_DEGREE_WORD_CONTEXT_RE`); `_DEGREE_TAIL_RE` reads the field after `'s degree in`, and `_BARE_DEGREE_IN_RE` reads `degree in <field>` with no level. `_certificate_name` reads capitalized words on both sides of the certificate word and includes capitalized `Certified` when words follow it; `_profile_has_certificate` allows a name when all its words appear in one profile certification name or when it equals the issuer; requirement and plan sentences are skipped via `_CERT_REQUIREMENT_OR_PLAN_RE` and `_is_skippable_non_claim`. `test_fabricated_employer_raises_fabricated_experience_without_selected_project` in `tests/test_cover_letter_validator.py` tests the validator wiring.

Tests, written before the change: 5 failed in `tests/unit/test_cover_letter_grounding.py` (`Tamarack Vault I` was flagged; `At Vesper Foundry I built the audio router.` was missed; `As a backend consultant at Tamarack Vault` was flagged against `Senior Backend Consultant`; `I completed a Bachelor's degree in Biophysics.` was missed; `I am a Certified Solstice Inspector.` was missed). After making `[Aa]t` and `[Aa]s` match at sentence start and fixing the `SelectionOutput` fields in the validator test, all 12 selected tests passed.

Mutations:
1. In `cover_letter_validator.py`, `if flag_fabricated_experience_claims(content, profile, job):` was replaced with `if False and flag_fabricated_experience_claims(content, profile, job):` (1 occurrence). Checksum changed from `f8eb02f8d757d745180d2f795df762581c84393dd6089d8c40a899c933733097` to `e40807f329774959da72bc7818ef31ef4867e53f85728ddc2f41684ac9aa59c4`. `grep -F` count was 1. `test_fabricated_employer_raises_fabricated_experience_without_selected_project` failed. The file was restored and matched the backup byte for byte.
2. In `cover_letter_grounding.py`, `_ORG_TOKEN = r"(?!I\b)[A-Z][\w&.'-]*"` was replaced with `_ORG_TOKEN = r"[A-Z][\w&.'-]*"  # allow I in org` (1 occurrence). Checksum changed from `f907c4900f70a3a30e455576f110a24d4ca584227ccc57db99ea62ad4cfdb9ab` to `58268eb91d8f1a3072af960a6a365037d4413ba39c0377b20121d9af2da40a86`. `grep -F` count was 1. `test_fabricated_employer_is_flagged_and_a_real_one_is_not` failed on `Tamarack Vault I`. The file was restored and matched the backup byte for byte.

Eval: Git SHA `27bd81f6b5026b67642d3d060b036a525584e12e`, dirty true. MLflow run `545cd75cfb204fb28c1f25e5531bd750`. Report `20261023T035536113628Z.json`. No label metric changed against F5a.

| Label | P before (F5a) | P after | R before | R after | F1 before | F1 after | Predicted before | Predicted after |
|-------|----------------|---------|----------|---------|-----------|----------|------------------|-----------------|
| `fabricated_technology` | 0.889 | 0.889 | 1.000 | 1.000 | 0.941 | 0.941 | 9 | 9 |
| `inflated_duration` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 5 | 5 |
| `inconsistent_metric` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 3 | 3 |
| `fabricated_experience` | 1.000 | 1.000 | 0.750 | 0.750 | 0.857 | 0.857 | 6 | 6 |
| `analogical_claim` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 3 | 3 |
| `scope_inflation` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 4 | 4 |
| `technique_mismatch` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 3 | 3 |
| `ungrounded_claims` | 0.516 | 0.516 | 1.000 | 1.000 | 0.680 | 0.680 | 64 | 64 |
| micro | 0.670 | 0.670 | 0.970 | 0.970 | 0.793 | 0.793 | — | — |

### S1. Small items

The first line of the second docstring paragraph of `flag_inflated_duration_claims` now has 4 spaces of indent instead of 8. `_project_name_spans` matches each project name with `(?<![A-Za-z0-9])...(?![A-Za-z0-9])` instead of `str.find`, so a project name inside a longer word is not a span.

Tests, written before the change: `test_project_name_inside_a_longer_word_is_not_a_project_span` failed (`[(11, 17, 'Quarry'), (47, 60, 'Anvil Foundry')] != [(47, 60, 'Anvil Foundry')]` on `"Inside the quarryman logs I ran fine-tuning on Anvil Foundry."`). After the change, the test passed.

Mutation: the regex span loop in `_project_name_spans` was replaced with `index = lowered.find(name.lower())  # substring find` (1 occurrence). Checksum changed from `778c059f7854e96abcfd917df0527ceb2e1c13e7edcc8b6e0d83eaa69a5ab179` to `4636a5c3e08e3d21929ff133242bd9b73f07526f2e3674dc78d91efc9f5357e3`. `grep -F` count was 1. `test_project_name_inside_a_longer_word_is_not_a_project_span` failed again. The file was restored and matched the backup byte for byte.

Eval: Git SHA `ec82fb277533375172cb81217f839e12b8464da3`, dirty true. MLflow run `df038b8f80624f91b33742de8dd576ef`. Report `20261023T041001420647Z.json`. No label metric changed against F6a.

| Label | P before (F6a) | P after | R before | R after | F1 before | F1 after | Predicted before | Predicted after |
|-------|----------------|---------|----------|---------|-----------|----------|------------------|-----------------|
| `fabricated_technology` | 0.889 | 0.889 | 1.000 | 1.000 | 0.941 | 0.941 | 9 | 9 |
| `inflated_duration` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 5 | 5 |
| `inconsistent_metric` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 3 | 3 |
| `fabricated_experience` | 1.000 | 1.000 | 0.750 | 0.750 | 0.857 | 0.857 | 6 | 6 |
| `analogical_claim` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 3 | 3 |
| `scope_inflation` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 4 | 4 |
| `technique_mismatch` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 3 | 3 |
| `ungrounded_claims` | 0.516 | 0.516 | 1.000 | 1.000 | 0.680 | 0.680 | 64 | 64 |
| micro | 0.670 | 0.670 | 0.970 | 0.970 | 0.793 | 0.793 | — | — |

### Rewritten tests and name check (item 8)

Rewritten helpers and tests in `tests/unit/test_cover_letter_grounding.py`:
- `_desk_job` and `_desk_profile`
- `test_fabricated_employer_is_flagged_and_a_real_one_is_not`
- `test_target_company_and_ordinary_at_are_not_employers` (now uses `"At Kestrel Audio I built a prototype during the workshop."`, which `_AT_ORG_I_RE` matches and skips via the target-company rule)
- `test_fabricated_title_is_flagged_and_the_job_title_is_not`
- `test_fabricated_degree_is_flagged_and_an_abbreviation_matches`
- `test_fabricated_certificate_is_flagged_and_a_real_one_is_not`
- `_two_desk_profile`, `test_distillation_on_a_project_without_it_is_flagged`, `test_each_technique_is_checked_against_the_nearest_project`, `test_a_technique_beside_the_other_project_is_flagged`
- `_forms_profile`, `_testing_job`, `test_hyphenated_analogy_target_matches_a_spaced_jd_duty`, `test_hyphenated_analogy_is_allowed_when_the_resume_has_the_words`, `test_significant_words_keeps_a_hyphenated_compound`

`grep -c "<name>" tests/fixtures/eval/grounding/cases.jsonl tests/fixtures/eval/grounding/profiles.json` returned `0` in both files for every name used in the rewritten and new tests: `Elena`, `Tamarack Vault`, `Kestrel Audio`, `Bramblewood Institute`, `Vesper Foundry`, `Larkspur Polytech`, `Solstice Vault Inspector`, `Solstice Inspector`, `Redwood Certified Network Specialist`, `Redwood Network Specialist`, `PyForum`, `Quarry Beacon`, `Anvil Foundry`, and `Quarry`.

### Labels left as they are

No label was changed. The two `fabricated_experience` misses (`fabricated_experience__harbor_mint` and `prompt_injection__led_orbit_aws`) and the `ungrounded_claims` measurement (predicted on 64 of 65 cases, for D6) are unchanged from F6 and F7.

### Checks

| Item | Black | Ruff | mypy gate | pytest |
|------|-------|------|-----------|--------|
| F5a | exit 0, 271 files unchanged | clean | 182 known, 0 new | 1183 passed, 1 Starlette warning, 176 s |
| F6a | exit 0, 271 files unchanged | clean | 182 known, 0 new | 1184 passed, 1 warning, 155 s |
| S1 | exit 0, 271 files unchanged | clean | 182 known, 0 new | 1185 passed, 1 warning, 152 s |

Black reformatted `cover_letter_grounding.py` once during F6a before the gate. `scripts/mypy_gate.py --update` was not run.

Not run: frontend checks, D5, D6, the holdout, the CI gate, and push. The holdout cases and profiles were not opened.
