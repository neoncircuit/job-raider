# Notes: python-version-setup

Found 2026-11-14: setup.sh stopped on the laptop (Python 3.10). Review section to be added when the task is done.

## Checks on the scratch clone (2026-11-14)

- Script tests: 29 passed (14 in `test_find_python.py`: system Python choice, `.python-version` as the source, broken Pythons skipped, in-repository install when none fits, failed install, wrong uv checksum refused and its download folder removed, uv kept inside `.tools`, help text; plus launcher, dev deps, mprocs, setup llmfit).
- Full backend: black and ruff clean, mypy gate 177 known and 0 new, pytest 2,368 passed.
- Container `ubuntu:22.04`, deadsnakes path: Python 3.10 alone gives the help text; with `python3.12` installed, the helper picks `/usr/bin/python3.12` and `python3` stays 3.10.
- Container `ubuntu:22.04`, option A path (only Python 3.10, curl, no sudo): `setup.sh` `check_python` downloaded uv 0.13.5 (SHA-256 checked), installed Python 3.11.17 into `.tools/python` in 1.5 s, and `create_venv` built `.venv` from it (pip works). No file was written under `$HOME`. A second run found the installed Python without a download. `.tools/` size: 130 MB (uv, the Python, and the uv cache).

## Applied and pushed (2026-11-14)

- Applied after "Yes, apply it"; `main` matches the checked clone (empty diff). Pushed after approval. CI: success (12 jobs passed, 1 skipped).
- Still open: `setup.sh` passes on the laptop.

## Review (2026-11-14)

- Laptop (Ubuntu 22.04, Python 3.10): after `git pull`, `./setup.sh` ran to the end; the user then started `make dev` and both the backend and the frontend came up.
- Result: a fresh machine with an old default Python now sets up with no manual Python install and no sudo.
- Follow-up noted: the end of `setup.sh` still prints an old "Phase 36 to 44" feature list from June 2026; it can go.
