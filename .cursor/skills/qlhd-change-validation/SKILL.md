---
name: qlhd-change-validation
description: Validate every QLHD Django code or app change with repository checks, data-integrity review, UI verification, and artifact export checks. Use before and after every change.
---

# QLHD change validation

Apply this workflow to every change in `D:\QLHD`, including a new Django app, model, import, template, calculation, report, or export.

## Before implementation

1. Read `AGENTS.md`, `docs/DEVELOPMENT_WORKFLOW.md`, and `docs/PROJECT_PROGRESS.md`.
2. Record branch, status, latest commit, and baseline checks.
3. Map affected models, views, forms, URLs, templates, import/export code, and tests.
4. For data or financial changes, run the code and data-integrity reviewers.

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

Update `docs/PROJECT_PROGRESS.md` with verified results and residual risks. Do not commit or push unless explicitly requested.
