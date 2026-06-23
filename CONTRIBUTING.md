# Contributing to HASM

Thanks for your interest in improving **Home Assistant Site Manager (HASM)**!

## Reporting issues

Please use the issue templates (bug report / feature request). For bugs, include:

- your **Home Assistant** version and **HASM** version,
- relevant logs (Settings → System → Logs, filtered on `custom_components.hasm` — **remove any tokens**),
- clear steps to reproduce.

## Development setup

Requires Python 3.12+.

```bash
python -m venv .venv
# Windows:        .venv\Scripts\activate
# Linux / macOS:  source .venv/bin/activate
pip install -r requirements_test.txt
```

## Running the tests

```bash
pytest tests/ -q
```

All tests must pass before a pull request can be merged. The CI (`Validate` workflow) also
runs **hassfest** and the **HACS** validation on every pull request.

## Code style

- Python is linted and formatted with [ruff](https://docs.astral.sh/ruff/):
  `ruff check` and `ruff format`.
- Code, comments, docstrings, log messages and exception messages are written in **English**.
- User-facing UI labels are translated via `strings.json`, `icons.json` and `translations/`.
  Add or update translations there rather than hardcoding strings.

## Pull requests

- Branch off `master`, keep each change focused, and open a pull request.
- Describe **what** changes and **why**.
- Make sure the test suite and the CI are green.
- Use clear commit messages (e.g. `fix: …`, `feat: …`, `docs: …`, `chore: …`).

## Architecture (quick map)

- `custom_components/hasm/api.py` — async client to a remote Home Assistant (REST + WebSocket);
  contains **no** `homeassistant` imports, so it is testable on its own.
- `custom_components/hasm/coordinator.py` — `DataUpdateCoordinator` polling one remote instance.
- `custom_components/hasm/config_flow.py` — add / options / reconfigure flows.
- `custom_components/hasm/entity.py` + platform files (`binary_sensor.py`, `sensor.py`,
  `update.py`, `button.py`) — the entities exposed per instance.
- `tests/` — the test suite.
