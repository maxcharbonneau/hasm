# HASM Roadmap

This document outlines the direction for **Home Assistant Site Manager (HASM)**.
It is **directional, not a commitment** — priorities and timing may change, and
contributions are welcome. For concrete, trackable work, see the
[issues](https://github.com/maxcharbonneau/hasm/issues).

## Philosophy

HASM stays small on purpose. Home Assistant already provides the UI (dashboards),
authentication (HA users), alerting (notifications) and automation — HASM only brings
remote instances in as **devices and entities**. New features should respect this:
expose useful data and actions, and let Home Assistant do the rest.

## Status — v0.1.4 (shipped)

- One device per remote instance (config flow: URL + long-lived token + SSL toggle;
  options and reconfigure flows)
- Monitoring: connectivity, Core / OS / Supervisor versions, available-updates count, error count
- Native `update.*` entities (install + backup + progress)
- Buttons: restart, reload configuration
- Generic `hasm.call_remote_service` service
- Configurable per-instance entity cap with a visible notification
- Local brand icon (HA 2026.3+)

## Phase 2 — next

### Richer monitoring (mostly data we already collect)
- [ ] **Last backup** timestamp sensor + **backup overdue** binary sensor (from `backup/info`)
- [ ] **Link latency** sensor (already measured on every poll)
- [ ] Optional: count of unavailable entities on the remote instance

### Easier alerting & dashboards
- [ ] **Automation blueprints**: instance offline, updates pending, backup overdue, error spike
- [ ] Example Lovelace dashboard / package to view a fleet at a glance

### More actions
- [ ] Buttons: **create backup now**, **refresh now**

## Later / ideas

- [ ] Remote system metrics (CPU / memory / disk). Note: the Supervisor API is not reachable
  remotely, so this would rely on mapping `sensor.*` entities the remote already exposes.
- [ ] Submit to the **HACS default** store (searchable without adding a custom repository)
- [ ] Additional UI translations (community-contributed)

## Non-goals

- A separate web UI, login system, or backend — Home Assistant provides these.
- Re-implementing Home Assistant's automation / alerting engine.
- Multi-tenant or SaaS features.

## Contributing

Ideas and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Please open an
issue to discuss larger items before implementing.
