"""
Measure the full cover letter flow (the Cover Letter page path) on 3
grounding pairs: Deep validation and Review & rewrite on, no selection
given. Prints counts only; the app's full log goes to a file (argv[1]).

Run from apps/backend-py:
    .venv/bin/python ../../tasks/active/lean-setup/tools/measure_letter_flow.py <log-file>
"""

import logging
import sys
import time

sys.path.insert(0, ".")
log_file = sys.argv[1]
logging.basicConfig(
    level=logging.INFO,
    filename=log_file,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
from src.evaluation.suites.structured import default_router, unload_ollama_model  # noqa: E402
from src.evaluation.suites.writer import load_pairs  # noqa: E402
from src.generation.cover_letter_service import generate_cover_letter_sync  # noqa: E402
from src.generation.generic_phrasing import find_generic_phrases  # noqa: E402

pairs = load_pairs()[:3]
total = 0.0
try:
    for pair in pairs:
        started = time.perf_counter()
        response = generate_cover_letter_sync(
            pair.job, pair.profile, deep=True, review=True
        )
        seconds = time.perf_counter() - started
        total += seconds
        content = (response.cover_letter or {}).get("content", "")
        validation = response.validation
        details = getattr(validation, "details", {}) or {}
        review = details.get("review") or {}
        phrases = [h.phrase for h in find_generic_phrases(content).hits]
        issues = sorted(
            getattr(i, "value", str(i)) for i in (getattr(validation, "issues", []) or [])
        )
        print(
            f"{time.strftime('%H:%M:%S')} {pair.case_id}: {seconds:.0f}s | words={len(content.split())} "
            f"stock={phrases} score={getattr(validation, 'score', None)} "
            f"rewrites={review.get('rewrite_count')} issues={issues}",
            flush=True,
        )
    print(f"total {total:.0f}s, mean {total / len(pairs):.0f}s per letter", flush=True)
finally:
    router = default_router()
    for model in ("qwen2.5:7b", "qwen2.5:3b"):
        unload_ollama_model(router, model)
