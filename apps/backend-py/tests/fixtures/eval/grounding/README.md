# Grounding Evaluation Labeling Guide

This guide defines the labels for the grounding evaluation set. The labels
state what each check must find. They do not describe the current validator.
The baseline report measures the difference between these labels and the
validator output.

```mermaid
flowchart LR
    P[Read profile and job] --> L[Read letter]
    L --> E[Label each check separately]
    E --> N[Write note and labels]
    N --> V[Validate case format]
    V --> B[Run baseline after all labels are fixed]
```

## Labeling Rules

### Rule 1: Label Each Check Separately

Decide every label with its own definition. One sentence can have more than
one label.

Example: The sentence "I run Kubernetes clusters" has
`fabricated_technology` and `ungrounded_claims` when the profile does not
contain Kubernetes. It names an unsupported technology as the candidate's
own, and it states an unsupported fact about the candidate.

### Rule 2: Write Labels Before the Validator Runs

Write `expected_issues` before you run the validator. Do not change a label
because of validator output.

If a definition is unclear or wrong:

1. Change the definition in this guide.
2. Add the reason to [Changes](#changes).
3. Relabel every affected case in the same way.
4. Run the validator only after the relabeling is complete.

## Label Definitions

### `fabricated_technology`

Use this label when the letter claims a technology as the candidate's own,
but the technology is not in the profile skills or in the technologies of an
experience or project. Claims include "used," "built with," and "experienced
in." A technology that appears only in the job description is unsupported.
Short names such as AWS, GCP, Go, and C# count.

Named tools, libraries, languages, and services are technologies. Examples
are FAISS, LangChain, PyTorch, and Kubernetes. Retrieval, reranking, RAG,
fine-tuning, reinforcement learning, distillation, and similar methods are
techniques. Do not use `fabricated_technology` for a technique. Use
`technique_mismatch` when a technique is assigned to the wrong profile
project, and use `ungrounded_claims` when the profile does not support the
technique claim.

Do not use this label when the mention is a disclaimer or a learning goal,
such as "rather than Java" or "keen to learn Go." Do not use it when the word
has a normal English meaning, such as "express my interest," "spring
semester," "a swift reply," or "spark curiosity."

### `inflated_duration`

Use this label when a duration claim, such as "over 5 years," "3-5 years," or
"five years of," is longer than the profile's merged experience. Also use it
when the claim is longer than the `years_of_experience` value of a skill that
the same sentence names.

Do not use this label when the duration is within both limits.

### `inconsistent_metric`

Use this label when one sentence states "from A% to B%" and a gain Z% that
matches neither:

- `B - A`, nor
- `(B - A) / A × 100`.

Allow a difference of 2 percentage points.

Do not use this label when the values agree or when there are no from/to
endpoints. An unsupported number without endpoints is `ungrounded_claims`,
not `inconsistent_metric`.

### `fabricated_experience`

Use this label when the letter presents a project, employer, job title,
degree, or certification as the candidate's own, but the profile does not
contain it.

Do not use this label when the profile contains the item. This definition is
wider than the current code, which checks only selected project names.

### `analogical_claim`

Use this label when the letter maps a resume fact onto a duty that only the
job description names. The mapping uses an analogy such as "my X work is like
Y," "similar to," or "translates directly to," and Y is not in the profile.

Do not use this label when Y is in the profile.

### `scope_inflation`

Use this label when the letter uses leadership or ownership wording beyond
what the profile documents for that work. Examples include "led," "managed a
team," "owned," "architected," and "spearheaded."

Do not use this label when the profile has the same kind of wording for that
work.

### `technique_mismatch`

Use this label when the letter assigns a named technique to a profile project
that does not document that technique. Named techniques include retrieval,
reranking, fine-tuning, RAG, reinforcement learning, and distillation.

A technique claim that the profile does not support is also
`ungrounded_claims`. It is not `fabricated_technology`.

Do not use this label when the project documents that technique.

### `ungrounded_claims`

Use this label when a sentence states a fact about the candidate that no
profile field supports. Facts include actions, achievements, numbers,
responsibilities, and uses of skills. This label includes unsupported numbers
such as "cut costs by 90%" and "3x faster," and fake employers.

Do not use this label for:

- a greeting;
- a closing or call to action;
- a sign-off line, such as "Sincerely, Mara Chen," which is part of the
  closing;
- a statement of interest or motivation, such as "I am excited about your
  mission";
- a statement of values, working style, or opinion that states no checkable
  fact, such as "I value clear documentation" or "I enjoy pairing with
  designers"; or
- a company fact from the job description.

A self-assessment that implies a fact is `ungrounded_claims` when the profile
does not support it. Examples are "I am an expert in distributed systems" and
"I have shipped many production ML systems."

## Case Format

`cases.jsonl` contains one JSON object per line. Each object uses the
`GroundingCase` format:

- `case_id`: Unique `<group>__<short_name>` identifier.
- `profile_id`: Key from `profiles.json`.
- `job`: Inline fictional job data accepted by `JobListing`.
- `selection`: Optional selection data used by the validator.
- `letter`: A fictional 150-to-350-word cover letter. The candidate writes it
  in the first person about the candidate's own work. It has a greeting, two
  to four paragraphs, and a closing. No sentence describes the profile or the
  dataset.
- `expected_issues`: Labels assigned with this guide.
- `note`: The injected condition and why each applicable label is present or
  absent.

## Labeling Process

1. Read the complete synthetic profile.
2. Read the fictional job and optional selection.
3. Read the letter without running the validator.
4. Evaluate every label in this guide, one at a time.
5. Write all applicable labels in `expected_issues`.
6. Explain the main injection and overlapping labels in `note`.
7. Check the JSONL format and dataset counts.
8. Freeze the labels.
9. Run the baseline.

## Voice

Each letter is written by the candidate, in the first person, about the
candidate's own work. No sentence describes the profile or the dataset. For
example, do not write "Atlas Search documents retrieval." Write "I used
retrieval on Atlas Search" when that fact is true.

## Changes

- **2026-10-22, techniques are not technologies (D3).** Retrieval, reranking,
  RAG, fine-tuning, reinforcement learning, and distillation stay techniques.
  A technique on the wrong project is `technique_mismatch` and
  `ungrounded_claims`. It is not `fabricated_technology`. Reason: the first
  constructed set labeled those methods as fabricated technologies, but this
  guide already listed them as techniques.
- **2026-10-22, values and sign-offs (D4).** A values, working-style, or
  opinion sentence with no checkable fact is not `ungrounded_claims`. A
  sign-off line is part of the closing. A self-assessment that implies an
  unsupported fact is `ungrounded_claims`. Reason: the first set used value
  sentences that no rule covered.
- **2026-10-22, voice.** Letters stay in the first person and do not describe
  the dataset. Reason: one sentence about what two projects "document" was
  copied into many letters, and a candidate would not write it.
- **2026-10-22, length.** A letter has 150 to 350 words and two to four
  paragraphs. Reason: the diversity rule for this set replaces the earlier
  120-to-300-word note.
- **2026-10-22, SQL and SQL databases.** A letter that says SQL is supported
  when the resume lists a SQL database (PostgreSQL, MySQL, SQLite, MariaDB,
  SQL Server, or Oracle), because those skills are SQL. A letter that names
  one of those databases still needs that database on the resume. Labels did
  not change. They already treated SQL this way. Reason: the validator treated
  SQL as a separate skill from the database that implies it.
