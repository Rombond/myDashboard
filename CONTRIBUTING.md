# Contributing

Issues and pull requests are welcome. This project is small on purpose.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
ruff check . && python -m pytest -q
PYTHONPATH=src python -m mydashboard.demo        # try it with fake data
```

- Keep it dependency-light (Flask and PyYAML only) and database-free.
- Add a test with every behaviour change. Tests must use fake data (`example.com`, `nas.lan`), never real hostnames, users or groups.
- Never commit secrets, real domains, credentials or your own `overrides.yml` / `rules.json`.
- AI-assisted contributions are fine, but you are responsible for what you submit: read it, run it, and say so in the PR if a tool wrote most of it.
