---
name: 9router-refresh
description: Regenerate, serve, or schedule the 9router model inventory dashboard (dist/models.html). Use when asked to refresh/update the model list or leaderboard, open the dashboard with a working refresh button, change how often it refreshes, or diagnose a stale dashboard.
---

# 9router-refresh

Drives the dashboard built by this repo. Read `docs/REFRESH.md` for the full guide.

## Commands

```bash
# one-shot refresh (re-reads 9router, OpenRouter cached 24h)
python3 -m nine_router_followup dashboard --refresh

# local server with a working Refresh button
python3 -m nine_router_followup serve        # http://127.0.0.1:4780/

# scheduler entry point (also what cron/launchd call)
ops/refresh.sh
```

Use `.venv/bin/python` instead of `python3` when the repo venv exists (it has pytest for the
gate; the dashboard itself is stdlib-only).

## Scheduled refresh

Prepared but never installed automatically:

- macOS: `ops/launchd/com.9routerfollowup.refresh.plist.template` (`StartInterval`, seconds;
  `21600` = 6 h) → `launchctl bootstrap gui/$(id -u) …`
- cron: copy a line from `ops/cron.example`

Only install or change a schedule when the user explicitly asks, and say which cadence you
used. Remove with `launchctl bootout gui/$(id -u)/com.9routerfollowup.refresh`.

## Guardrails

- Never read or print `~/.9router/jwt-secret`, `apiKeys` or connection `data` blobs; the code
  never selects them and `dist/models.html` must not contain them.
- Do not add external URLs/CDNs to the page: it must stay one self-contained file.
- A refresh must never fail the scheduler noisily: `ops/refresh.sh` uses `--skip-if-busy` and
  exits 0 on a concurrent run.
- If asked to change the cadence, edit the template/cron line and tell the user the exact
  `launchctl`/`crontab` command; do not install silently.

## Verify

```bash
python3 -m pytest                     # repo gate
tail -n 20 dist/refresh.log           # last scheduled run
open dist/models.html                 # static snapshot
```
