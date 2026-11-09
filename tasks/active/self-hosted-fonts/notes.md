# Notes: Self-Hosted Fonts

## Why (2026-11-09)

The user chose it next ("Self-host the fonts"). The Step 5 and Step 6 reviews list the font download as a repeated CI flake: run 42469431381 failed in the E2E job because the dev server did not start after `next/font/google` failed to download the fonts.

## Measure (2026-11-09, Claude)

- `src/app/layout.tsx`: `IBM_Plex_Sans` (weights 300, 400, 500, 600, 700) and `IBM_Plex_Mono` (400, 500, 600, 700), subset `latin`, variables `--font-ibm-plex-sans` and `--font-ibm-plex-mono`. No other file imports `next/font`.
- `globals.css` maps `--font-sans`, `--font-mono`, `--font-heading`, `--font-display`, and `--font-body` to those two variables, with system fallbacks.
- npm: `@fontsource/ibm-plex-sans` 5.3.0 and `@fontsource/ibm-plex-mono` 5.3.0, OFL-1.1, from `github.com/fontsource/font-files`, about 2.5 MB and 1.5 MB unpacked. Each has a `files/` folder with one woff2 file per subset, weight, and style.
- Next.js is 16.2.4. Its docs (`01-app/01-getting-started/13-fonts.md`, `03-api-reference/02-components/font.md`) show `localFont({ src: [{ path, weight, style }], variable })`, with paths relative to the calling file.

## Plan

| # | Content | How |
|---|---------|-----|
| MH-1 | Install the two packages (exact 5.3.0); `layout.tsx` uses `next/font/local` with the 9 Latin woff2 files; a unit test fails when a source file imports `next/font/google` | Runner handoff; red step, unit tests, a build with outside HTTPS refused, E2E, demo E2E, and before/after screenshots on a clone |

## Decisions (user, 2026-11-09)

- Plan approved, with the install of the two packages ("Yes, approve it").

## MH-1 written and checked (2026-11-09, Claude)

Applied on the repo (2026-11-10, Claude, on the user's word "Yes, apply it"): commit `841943b`, a cherry-pick of `ba13c57`. The only difference from the clone commit is the file mode of the new test (100644; the clone copy was 100755 because it was copied from the Windows drive). The real `apps/frontend-ts/node_modules` does not have the two packages yet, so the local dev server and build need `npm install` there; CI runs `npm ci` from the lockfile.

One commit was ready on the WSL clone `~/s4_work`, on top of `c43dfa5`: `ba13c57` `fix(frontend)`. It is a direct commit, not a runner handoff, because `package-lock.json` changes. To apply it, the real repository fetches the clone and cherry-picks it. The clone's `node_modules` is a real folder, not a link to the repository, so the install did not touch the real working tree.

- `package.json`: `@fontsource/ibm-plex-sans` and `@fontsource/ibm-plex-mono`, exact 5.3.0; `package-lock.json` has the two entries.
- `src/app/layout.tsx`: `next/font/local` with the 9 Latin woff2 files (paths written in full, because `next/font` needs literal values), the same CSS variables, and system fallbacks.
- `src/app/globals.css`: the `:root` values of `--font-ibm-plex-sans` and `--font-ibm-plex-mono` are removed (see below).
- `tests/lib/no-google-fonts.test.ts` (new, 3 tests): no source file imports `next/font/google`; the layout uses the Fontsource files; `globals.css` does not set the two font variables.

A defect found on the way: the first version built and passed every test, but the pixel compare showed that the page used a system font. `globals.css` set `--font-ibm-plex-sans: "IBM Plex Sans", ...` on `:root`, and that value won over the class from `next/font`. With Google fonts the name "IBM Plex Sans" existed; with `next/font/local` the family is named `ibmPlexSans`. The `:root` values are removed, and the third test guards it.

Checks on the clone:

- Red: before the change, the guard tests fail (an import of `next/font/google`; no `next/font/local`; then, for the third test, the `:root` values).
- 378 unit tests pass; prettier, eslint with no warnings, and tsc pass.
- A build with outside HTTPS refused (`HTTPS_PROXY=http://127.0.0.1:9`): the old build fails ("issue establishing a connection while requesting https://fonts.googleapis.com/..."); the new build passes. The demo build with the base path also passes with outside HTTPS refused.
- The browser loads `ibmPlexSans` 400, 500, 600 and `ibmPlexMono` 400, 600, 700 on the Settings page; the body uses `ibmPlexSans` and `h1` uses `ibmPlexMono`.
- Screenshots before and after (desktop, Dashboard and Settings) look the same: the same faces, weights, and layout. About 2.9% of the pixels differ, from small glyph-metric differences between the files that Google serves and the Fontsource 5.3.0 files (one line on Settings wraps one word differently).
- E2E with the API mock: 44 pass, 1 skipped (the phone test on desktop), 1 failed: the Jobs page search test. That test is flaky before this change too: 4 repeats gave 2 failures of 24 with the Google fonts and 4 of 24 with the local fonts. It is a separate open item.
- Demo E2E: 18 pass.

## Blockers / Questions

- None.

## Review
