# Copilot Issue Automation + GitHub Pages Demo

This starter repo does four things:

1. Lets you create GitHub issues that auto-assign `@copilot`
2. Gives Copilot repository-specific instructions
3. Prepares a lightweight environment for Copilot cloud agent
4. Deploys a static dashboard to GitHub Pages with freshly generated synthetic data on each deploy

## What this demo models

Domain: **customer support operations for a B2B SaaS company**

Embedded hypotheses in the generated data:

1. **Higher backlog today increases SLA breach risk tomorrow**
2. **Email tickets have slower first response and lower CSAT than chat**
3. **Weekend under-staffing creates a Monday ticket spike**
4. **APAC has the strongest Monday backlog effect because staffing is leaner**

The dashboard reads `site/data/dashboard.json` and renders:
- KPI cards
- trend charts
- channel and region comparisons
- hypothesis callouts
- alert panels
- **CSAT Six Sigma I-MR control charts** — Individuals chart with UCL/LCL (3σ limits), Moving Range chart, process capability (Cpk, sigma level), and Western Electric rule violations (Rules 1, 2, 3)

## Simplest setup steps

1. Create a GitHub repo and copy these files in.
2. Enable **GitHub Copilot cloud agent** for the repo.
3. In **Settings → Pages**, choose **GitHub Actions** as the source.
4. Push to your default branch.
5. Open **Actions** and run **Deploy GitHub Pages dashboard** once if needed.
6. Create a new issue using the **Copilot Bug Fix** template.

If your plan and repo permissions allow it, the issue template auto-assigns `@copilot`, and Copilot can open a branch and PR for review.

## Local run

```bash
python scripts/generate_data.py --seed 42 --days 180 --output site/data/dashboard.json
python -m http.server 8000
```

Then open `http://localhost:8000/site/`.

## Notes

- The dashboard is intentionally static and dependency-free.
- The dataset is synthetic but structured to feel realistic.
- Each GitHub Pages deploy uses a fresh seed, so the site changes slightly from deploy to deploy.
