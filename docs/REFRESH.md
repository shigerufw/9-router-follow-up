# Refreshing the dashboard

`dist/models.html` is a **snapshot**. Every command below re-reads
`~/.9router/model-catalog.json` and `~/.9router/db/data.sqlite` and rewrites the file, so the
numbers are always current as of the run — the only thing that is cached is the OpenRouter
model table (24 h).

## 1. Manual

```bash
python3 -m nine_router_followup dashboard              # uses the cache if < 24h old
python3 -m nine_router_followup dashboard --refresh    # force an OpenRouter fetch
python3 -m nine_router_followup dashboard --offline    # never touch the network
open dist/models.html
```

If you do not use the repo venv, prefix the interpreter:
`.venv/bin/python -m nine_router_followup dashboard`.

## 2. From the page: `serve`

```bash
python3 -m nine_router_followup serve          # http://127.0.0.1:4780/
```

`serve` binds loopback only, regenerates once at startup, then serves the page. The
**Refresh** button POSTs `/refresh`, which runs the same in-process generator and reloads the
page. Opened as a `file://` page the button is disabled and names the command to run instead.

| endpoint | behaviour |
|---|---|
| `GET /` | the page (generated on demand if missing) |
| `GET /health` | `{"ok": true, "generated": "..."}` |
| `POST /refresh` | regenerate; `200` with summary, `409` if another refresh holds the lock |

Stop it with `Ctrl+C`. Nothing is left running in the background.

## 3. Scheduled (prepared, not installed)

`ops/refresh.sh` is the single entry point for schedulers. It resolves the repo root, prefers
`.venv/bin/python`, logs to `dist/refresh.log` (trimmed to 500 lines), uses `--skip-if-busy`
and propagates the exit code.

```bash
ops/refresh.sh                        # run it once to verify
REFRESH_ARGS="--offline" ops/refresh.sh
```

### macOS — launchd

Cadence lives in `ops/launchd/com.9routerfollowup.refresh.plist.template`
(`StartInterval`, seconds; `21600` = 6 h).

```bash
sed "s|__REPO__|$PWD|g" ops/launchd/com.9routerfollowup.refresh.plist.template \
  > ~/Library/LaunchAgents/com.9routerfollowup.refresh.plist

launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.9routerfollowup.refresh.plist
launchctl print gui/$(id -u)/com.9routerfollowup.refresh | head -20
```

Change the cadence later:

```bash
launchctl bootout gui/$(id -u)/com.9routerfollowup.refresh
# edit StartInterval, then bootstrap again
```

Remove it:

```bash
launchctl bootout gui/$(id -u)/com.9routerfollowup.refresh
rm ~/Library/LaunchAgents/com.9routerfollowup.refresh.plist
```

### Linux/macOS — cron

Copy a line from `ops/cron.example` (`crontab -e`), replacing the path:

```cron
0 */6 * * *   /absolute/path/to/9-router-follow-up/ops/refresh.sh
```

## 4. Verify and troubleshoot

```bash
tail -n 20 dist/refresh.log       # what the last run did
ls -l dist/models.html            # mtime = last successful refresh
```

| symptom | cause / fix |
|---|---|
| `skipped: another refresh holds …` | a previous run is still going; the lock is released by the OS if a run dies |
| `warnings: OpenRouter fetch failed … using cached models` | offline or rate-limited; the page still renders from cache |
| page shows `Static snapshot…` | opened via `file://`; use `serve` to get a working button |
| `429`/`503` in the log | OpenRouter throttling; retry later or use `--offline` |
| launchd job never runs | wrong `__REPO__` path; run `launchctl print` and look at `last exit code` |

Nothing here writes to `~/.9router`: the DB is opened `mode=ro` and credentials are never read.
