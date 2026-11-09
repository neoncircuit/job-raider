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

## Blockers / Questions

- The install needs the user's approval.

## Review
