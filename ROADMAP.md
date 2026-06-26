# HASM Roadmap

This document outlines the **future** direction for Home Assistant Site Manager (HASM).
It is **directional, not a commitment** — priorities and timing may change.

- For what has already shipped, see the [CHANGELOG](CHANGELOG.md).
- For concrete, trackable work, see the [issues](https://github.com/maxcharbonneau/hasm/issues).

## Philosophy

HASM stays small on purpose. Home Assistant already provides the UI (dashboards), authentication
(HA users), alerting (notifications) and automation — HASM only brings remote instances in as
**devices and entities**. New features should respect this: expose useful data and actions, and let
Home Assistant do the rest.

## Next — 0.2.1 · Update-loop hardening

- Make mirror detection exhaustive: ignore `unavailable` / restored `update.*` entities so an
  instance supervising itself (or a chain) can no longer duplicate entities, even across restarts.
- Warn at setup when the target instance is itself running HASM (loop risk).
- Automatic cleanup of orphaned mirror entities _(here, or in 0.2.2)_.

## Planned

- **0.2.2 · Maintenance & small additions**
  - Auto-purge orphaned mirror entities (if not shipped in 0.2.1).
  - Create storage sensors when `systemmonitor` loads after HASM (late-load listener).
  - Link-latency sensor (already measured on every poll).
  - Count of unavailable entities on the remote instance.
  - "Refresh now" button.
- **0.3.0 · Turn-key alerting**
  - Automation **blueprints** (instance offline, updates pending, backup overdue, error spike).
  - Example Lovelace dashboard / package to view a fleet at a glance.

## Later / ideas

- **Fleet rollup** — an aggregate "Fleet" device (instances online, total updates pending, total
  errors across all instances).
- **Remote system metrics** (CPU / memory) — limited: the Supervisor API is not reachable remotely,
  so this would rely on mapping `sensor.*` entities the remote already exposes.
- Submit to the **HACS default** store (searchable without adding a custom repository).
- Additional UI translations (community-contributed).

## Non-goals

- A separate web UI, login system, or backend — Home Assistant provides these.
- Re-implementing Home Assistant's automation / alerting engine.
- Managing backups — HASM is a read-only relay: it surfaces backup state and relays the native
  trigger, but does not own backup orchestration.
- Multi-tenant or SaaS features.

## Contributing

Ideas and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Please open an issue
to discuss larger items before implementing.
