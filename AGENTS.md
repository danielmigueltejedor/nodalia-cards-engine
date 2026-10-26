# Agent instructions — nodalia-cards-engine

## Repository-specific deterministic quality contract (2026-10-26)

**Project:** Python Home Assistant backend engine for Nodalia Cards notifications, device controls and transports.

**Engineering requirements:** Protect websocket commands, state versioning, climate engine, notification fallback and HA event behavior.

**Verification commands:** python -m unittest discover -s tests -p 'test_*.py' -v; python -m unittest discover -s tests/python -p 'test_*.py' -v; python -m compileall -q custom_components.

Execute applicable checks before claiming completion and report the output honestly. Tests must cover behavior, edge cases and failures. Never delete, skip or weaken tests, quality thresholds or CI for a green result. Review changes to policies, `AGENTS.md`, `QUALITY_GATES.md` and workflows. Make `quality` required in protected branches. Report missing dependencies and failing legacy tests, never hide them. These instructions extend (do not replace) existing rules.
