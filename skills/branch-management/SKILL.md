---
name: branch-management
description: Manage feature branches in the 9router-follow-up repo using the Mini Software Factory (MSF) with a Gitflow-inspired workflow: work on branches off `develop`, merge completed work to `develop` via MSF approve, then promote to `main` after verification.
---

# branch-management

This skill documents a Gitflow-inspired workflow for the
`9router-follow-up` repository, using the Mini Software Factory (MSF)
that is already configured.

## Branch model

- **`main`** – productive branch. Contains only merged, released work.
- **`develop`** – development branch. Acts as the integration target for
  feature branches. New work is merged here first.
- **Feature branches** – short-lived branches created off `develop` for
  each change/job. MSF worktrees (`msf/<id>`) are created off the branch
  you are currently checked out on.

## MSF configuration

- `merge_mode` is `local` (set via `msf configure`). This means
  `msf approve` performs a `git merge --no-ff` into the **currently
  checked-out branch**. It does **not** require an `origin` remote or
  GitHub PR creation.
- `human_merge: true` ensures the factory records the merge in
  `merged.json` and asks for confirmation before overwriting.

> **Note:** This repo has no `origin` remote, so a true GitHub PR cannot
> be auto-created. The workflow below uses `msf approve` to merge locally
> and documents the manual promotion step to `main`.

## Typical workflow

### 1. Ensure you are on `develop`

```bash
git checkout develop          # or `git switch develop`
msf sync                     # refresh the job registry
```

### 2. Start a new job (router chooses the lane)

```bash
JID=$(msf new "Descriptive job title")
msf lane $JID standard       # standard / risky / trivial
msf next $JID                # moves to spec → build → gate → review → decision
```

### 3. Create a worktree branch off `develop`

```bash
# The worktree is created relative to the branch you are on.
# If you are on develop, msf worktree creates msf/<id> off develop.
msf worktree $JID            # creates .msf/worktrees/msf-<id> or similar
# ... make changes, commit, test ...
```

> Alternatively, you can use a detached worktree:
> ```bash
> git worktree add ../scratchpad/feature-jid <branch>
> ```

### 4. Approve / merge into `develop`

```bash
msf approve $JID             # runs `git merge --no-ff msf/<id>` into develop
# Output: "merged msf/j-001 into develop @ <sha>"
# writes .msf/jobs/j-001/merged.json
# removes the job worktree
```

### 5. Verify the merge on `develop`

```bash
msf status                    # shows job j-001 as merged
python3 -m pytest             # gate: all tests must pass
msf doctor                    # READY
```

### 6. Promote `develop` to `main` (when ready)

Only after the team verifies everything on `develop` is stable do we
promote to `main`:

```bash
git checkout main
git merge --no-ff develop   # promote develop into main
# optionally: write a tag, run final checks, etc.
git checkout develop          # get back to develop
```

> **Why a separate step?** Keeping the `main` promotion explicit ensures
> that only well-tested, reviewed code lands in the productive branch.
> It also lets you retain a history of what went into each `main`
> release (the merge commit from `develop` is recorded).

### 7. Delete the feature branch (optional)

```bash
git branch -d msf/j-001       # safe — ancestor of develop/main
# or keep it; it is harmless
```

### 8. Continue work

```bash
msf sync                      # sync the job registry
# start a new JID at step 2
```

## Command summary

| Action | Command |
|---|---|
| Switch to develop | `git checkout develop` |
| Create a new job | `msf new "title"` |
| Set lane | `msf lane <id> <standard|risky|trivial>` |
| Move to next stage | `msf next <id>` |
| Create worktree | `msf worktree <id>` |
| Merge job into develop | `msf approve <id>` |
| Check status | `msf status` |
| Run gate | `python3 -m pytest` / `msf doctor` |
| Promote develop → main | `git checkout main && git merge --no-ff develop && git checkout develop` |
| Delete merged branch | `git branch -d msf/<id>` |
| Sync job registry | `msf sync` |

## Adjusting merge_mode

If you ever need to switch strategies:

```bash
msf configure --from '{
  "name": "9router-follow-up",
  "merge": { "mode": "pr", "human_merge": true },   # would need origin/remote
  "gate": { "command": "bash .msf/checks.sh", "timeout_s": 600 },
  "max_rounds": 3
}'
```

For this repo (no remote), keeping `mode: local` and using the
`develop → main` promotion step above is the recommended approach.

## Why this workflow

- **Isolation:** Each change lives on its own branch/worktree; `main` is
  never broken by unfinished work.
- **Gate safety:** The MSF gate (`pytest`) runs on `develop` before any
  promotion to `main`.
- **Explicit releases:** The `develop → main` promotion is a deliberate
  action, making releases auditable.
- **MSF-friendly:** `msf approve` works with `merge_mode: local`; no
  `origin` or PR is required for the day‑to‑day merge step.