# Notes: python-version-setup

Found 2026-11-14: setup.sh stopped on the laptop (Python 3.10). Review section to be added when the task is done.

## Checks on the scratch clone (2026-11-14)

- Script tests: 29 passed (14 in `test_find_python.py`: system Python choice, `.python-version` as the source, broken Pythons skipped, in-repository install when none fits, failed install, wrong uv checksum refused and its download folder removed, uv kept inside `.tools`, help text; plus launcher, dev deps, mprocs, setup llmfit).
- Full backend: black and ruff clean, mypy gate 177 known and 0 new, pytest 2,368 passed.
- Container `ubuntu:22.04`, deadsnakes path: Python 3.10 alone gives the help text; with `python3.12` installed, the helper picks `/usr/bin/python3.12` and `python3` stays 3.10.
- Container `ubuntu:22.04`, option A path (only Python 3.10, curl, no sudo): `setup.sh` `check_python` downloaded uv 0.13.5 (SHA-256 checked), installed Python 3.11.17 into `.tools/python` in 1.5 s, and `create_venv` built `.venv` from it (pip works). No file was written under `$HOME`. A second run found the installed Python without a download. `.tools/` size: 130 MB (uv, the Python, and the uv cache).
