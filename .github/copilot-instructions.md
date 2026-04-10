You are working in a small static-site repository.

Priorities:
1. Prefer the smallest correct change.
2. Keep the site dependency-free: plain HTML, CSS, JavaScript, and Python only.
3. Do not introduce build frameworks or package managers unless the issue explicitly requires them.
4. Preserve the JSON schema produced by `scripts/generate_data.py` unless the issue explicitly changes the contract.
5. If you change the schema, update `site/index.html`, `tests/test_dashboard_data.py`, and `README.md` in the same pull request.
6. Make charts readable with semantic labels, units, and defensive handling for missing values.
7. Keep names boring and clear. Avoid clever abstractions.
8. Add or update tests for behavioral changes.

Validation commands:
- `python scripts/generate_data.py --seed 42 --days 180 --output site/data/dashboard.json`
- `python -m unittest discover -s tests -p 'test_*.py'`

When fixing issues:
- Restate the failure in code or tests where possible.
- Prefer targeted fixes over broad refactors.
- Do not break GitHub Pages deployment.
