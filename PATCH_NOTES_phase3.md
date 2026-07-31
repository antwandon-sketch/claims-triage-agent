# Phase 3 update - golden dataset + eval harness

Built and dry-run tested (with fake responses, 0 real API cost) while you
were asleep. All 15 tests pass, including 7 new ones for the eval scoring
logic. Nothing here has made a real API call yet - that happens the first
time you run `python -m eval.run_eval` yourself.

## What's new
- `eval/golden_dataset.json` - 20 hand-labeled test emails
- `eval/run_eval.py` - the eval harness script
- `tests/test_eval_scoring.py` - unit tests for the scoring logic
- `eval_results/` - where each run's detailed output gets written

## What changed
- `classifier.py` - `classify_email()` now takes `subject` and `body`
  separately (was silently dropping the subject line before)
- `routes/ingestion.py` - updated to match the new function signature
- `db.py` - added the `eval_runs` table + `save_eval_run()` / `list_eval_runs()`
- `README.md`, `progress-log.md`, `.gitignore` - updated to match

## How to merge this in

**Terminal (one tab, nothing else running):**

```bash
cd ~/claims-triage-agent
unzip -o ~/Downloads/phase3-update.zip
source triage-env/bin/activate
pytest -v
```

You should see `15 passed`. That confirms it's all in place correctly on
your machine before touching anything real.

**Then create the new table** (safe to run - it only adds `eval_runs`,
doesn't touch your existing data):

```bash
python3 -c "import db; db.init_db()"
```

**Then run the real eval** (this makes 20 real Claude API calls - a minute
or so, a few cents of real cost):

```bash
python -m eval.run_eval
```

Read through the report it prints - especially the "Cases with at least one
wrong field" section if there is one. That's the actual measurement this
whole project exists to produce. Bring the results back to the chat and
we'll look at them together, and decide whether the prompt needs any
adjusting before calling this phase done.

**Then commit and push:**

```bash
git add .
git commit -m "Phase 3: golden dataset + eval harness, subject-line fix"
git push
```

(Or hand that same message to Claude Code in the terminal, same as last
time.)
