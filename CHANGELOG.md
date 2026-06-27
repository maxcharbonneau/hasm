# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [0.2.1] — 2026-06-27

### Fixed
- **Update-loop hardening.** When an instance supervised itself (or formed an A↔B chain),
  mirrored `update.*` entities were re-created without bound across restarts (restored
  "ghost" entities lose the `hasm_mirror` tag and were re-mirrored). `parse_updates` now also
  ignores `update.*` entities in the `unavailable` state, making mirror detection exhaustive
  (real update → mirror; live mirror → skipped via tag; ghost/restored → skipped via state).

### Added
- Config flow warns when the target instance is itself running HASM (loop risk if it is this
  instance or a cycle).

### Changed
- **Server metrics simplified.** Replaced the four byte-level disk sensors (free / used / total /
  usage) — which depended on the Supervisor `host/info` endpoint (admin-only, often returning 401)
  and were only created once at setup — with three always-available percentage sensors (CPU,
  memory, disk usage) read directly from the target's `systemmonitor` integration.

## [0.2.0] — 2026-06-26 — Backup & storage sensors

### Added
- **Per-destination backup sensors** (discovered dynamically per backup agent): last full backup
  (timestamp), space used by backups (MB), backup count, and a backup-problem binary sensor.
- **Global backup sensors:** last automatic backup, next automatic backup, backup in progress.
- **"Back up now" button** (triggers `backup.create_automatic`; unavailable while a backup runs;
  a long-running backup that read-times-out is treated as "started in the background").
- **Server storage sensors:** disk free / used / total / usage %, sourced from Supervisor
  `host/info`, falling back to `systemmonitor`, otherwise omitted.

### Changed
- `backup/info` is fetched once per polling cycle (removed the redundant legacy path).
- Restart / Reload buttons moved to the device "Controls" section.

## [0.1.4] — 2026-06-23

### Added
- Embedded brand icon under `custom_components/hasm/brand/` so the logo shows in Home Assistant
  2026.3+ (the `brands` repository no longer accepts custom-integration icons).
- MIT license, contributing guide, security policy, issue/PR templates, and project roadmap.

### Fixed
- Published a proper versioned GitHub release so HACS serves the build that includes the brand icon.

## [0.1.3] — 2026-06-22

### Added
- MDI monochrome, theme-adaptive icons for all entities.

### Changed
- Update entities use `mdi:update` and no longer attempt to load a missing brand image
  (no more "icon not available").

## [0.1.2] — 2026-06-22

### Added
- Configurable per-instance update-entity cap (default 250, bounds 10–2000) with a visible,
  one-time notification when the cap is reached.

## [0.1.1] — 2026-06-22

### Fixed
- **Critical:** mirror loop when an instance supervised itself — mirrored `update.*` entities were
  re-mirrored without bound, creating thousands of entities and crashing Home Assistant. Added
  `hasm_mirror` tagging + filtering and a per-instance entity cap.

## [0.1.0] — 2026-06-22

### Added
- Initial release. One device per remote instance via a config flow (URL + long-lived token +
  verify-SSL toggle), plus options and reconfigure flows.
- Monitoring: connectivity, Core / OS / Supervisor versions, available-updates count, error count.
- Native `update.*` entities (install + backup + progress).
- Restart and reload-configuration buttons.
- Generic `hasm.call_remote_service` service.
- English and French translations.

[0.2.1]: https://github.com/maxcharbonneau/hasm/releases/tag/v0.2.1
[0.2.0]: https://github.com/maxcharbonneau/hasm/releases/tag/v0.2.0
[0.1.4]: https://github.com/maxcharbonneau/hasm/releases/tag/v0.1.4
