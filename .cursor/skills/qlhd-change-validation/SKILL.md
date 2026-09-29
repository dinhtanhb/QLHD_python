---
name: qlhd-change-validation
description: Validate QLHD Django code, documentation, repository cleanup, imports and exports. Use before and after changes in the QLHD repository.
---

# QLHD change validation

Apply this workflow to every change in `D:\QLHD`, including a new Django app, model, import, template, calculation, report, or export.

## Before implementation

1. Read `AGENTS.md`, `docs/DEVELOPMENT_WORKFLOW.md`, and `docs/PROJECT_PROGRESS.md`.
2. Record branch, status, latest commit, and baseline checks.
3. Map affected models, views, forms, URLs, templates, import/export code, and tests.
4. For data or financial changes, run the code and data-integrity reviewers.
5. For cleanup, compare tracked files with runtime references. Keep migrations, templates, manual data scripts and QA evidence unless their role is understood; record exact deletion counts. Never stage credentials or real data.

## After implementation

Run with the project virtual environment and set `DEBUG=True` when the local `.env` overrides it:

```powershell
$env:DEBUG = 'True'
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\venv\Scripts\python.exe manage.py test quanly.tests
git diff --check
```

Then run targeted tests and a real-flow check. For Excel, validate the ZIP package, reload it with `openpyxl`, and open it with Excel when available. For Word/PDF, render and inspect pages. For HTML, load the affected route and verify filters, actions, tables, and responsive layout.

Update `docs/PROJECT_PROGRESS.md` with verified results and residual risks. The user has granted standing authorization to commit and push after each completed change: create a review ZIP and a full source/template ZIP under `backups/`, stage only intended files, commit with a clear message, and push the active branch. Never include `.env`, databases, real input data, virtual environments, logs, or temporary files in commits or backups. If commit or push fails, report the exact state and blocker instead of claiming completion.

Build backups from a reviewed source/document/template allowlist, not by zipping the working directory. Exclude `.codex_tmp/`, `_qa/` generated outputs, LibreOffice profiles, `~$*`, and local credentials. If a requested improvement changes business behavior, propose it to the user before implementation.
