# 9router follow-up

Internal tooling to follow up on how [9router](https://openrouter.ai) is configured:
verify that models and provider connections work, keep a model leaderboard, and evaluate
which models make sense in a combo.

Everything here is **read-only** against the local 9router install (`~/.9router`). It never
reads `apiKeys`, connection `data` blobs or `jwt-secret`, and it never writes to 9router.

## Model inventory dashboard

```bash
python3 -m nine_router_followup dashboard          # -> dist/models.html
open dist/models.html
```

Options:

| flag | meaning |
|---|---|
| `--out PATH` | output file (default `dist/models.html`) |
| `--home DIR` | 9router home (default `~/.9router`) |
| `--cache PATH` | OpenRouter cache (default `~/.cache/9router-followup/openrouter-models.json`) |
| `--offline` | never hit the network; use the cache (may be stale) |
| `--refresh` | force a fetch even when the cache is fresh (TTL 24h) |
| `--generated ISO` | fixed timestamp, for reproducible output |
| `--skip-if-busy` | exit 0 if another refresh is running (used by schedulers) |

### Keeping it up to date

`dist/models.html` is a snapshot; every run re-reads 9router and rewrites it.

```bash
python3 -m nine_router_followup dashboard --refresh   # one-shot
python3 -m nine_router_followup serve                 # http://127.0.0.1:4780/ + Refresh button
```

Scheduling is **prepared but not installed**: `ops/refresh.sh` is the cron/launchd entry
point, templates live in `ops/launchd/` and `ops/cron.example`, and `docs/REFRESH.md` has the
install/change/uninstall steps. Agents can drive all of it with
`skills/9router-refresh/SKILL.md`.

### What it shows

- **Summary**: models known, in use, requests, tokens in/out, cost, provider connections,
  combos, and how many models have an OpenRouter counterpart.
- **Models**: every model 9router can route to — used, hand-added (custom models), or offered
  by a connected provider — with usage (requests, tokens, cost, errors, last used), context
  window, max output, OpenRouter prices per 1M tokens, vision/modality and enabled state.
- **Providers & connections**: connection name, auth type, priority and active state.
- **Combos**: each member with `available` / `missing` and whether it is in use.
- **Not matched in OpenRouter**: listed explicitly instead of being guessed.

### Data sources

| source | used for |
|---|---|
| `~/.9router/model-catalog.json` | catalogue models, context window, max output, vision |
| `~/.9router/db/data.sqlite` | connections, usage, combos, custom/disabled models (opened `mode=ro`) |
| `https://openrouter.ai/api/v1/models` | names, pricing, context, modalities (cached 24h) |

9router and OpenRouter name models differently, so matching is a conservative ladder:
exact id → `provider/model` → variant (`:free`, `-free`, `-preview`) → same tail
(`meta/` vs `meta-llama/`) → size-tag fuzzy (`-30b-a3b` vs `-lightning`). A match is only
accepted when it is unique; the `OR match` column shows which rule fired.

## Development

```bash
python3 -m pytest      # the MSF gate runs this
```

The gate uses the local `.venv` (created with `uv venv .venv && uv pip install pytest`).
