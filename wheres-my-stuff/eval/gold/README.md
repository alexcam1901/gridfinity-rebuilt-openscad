# Gold set photos

Drop your hand-labeled item photos here (e.g. `wirenuts.jpg`, `drill.jpg`) and
add a matching line to `../gold.jsonl`. Aim for ~50–100 representative items —
the messier and more realistic the photos, the more useful the eval.

These images are intentionally **not** committed (see `.gitignore`); they're your
personal photos. The eval reads them locally. Entries whose image is missing are
skipped with a warning, so the harness still runs on a fresh checkout.
