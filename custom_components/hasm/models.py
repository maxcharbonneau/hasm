"""HA data dataclasses (pure, immutable). Port of app/ha_client/models.py."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class HAConfig:
    core_version: str | None
    location_name: str | None
    components: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HAUpdate:
    entity_id: str
    title: str | None
    installed_version: str | None
    latest_version: str | None
    update_available: bool
    supports_backup: bool = False
    in_progress: bool = False
    supports_progress: bool = False
    update_percentage: float | None = None


@dataclass(frozen=True)
class HABackupState:
    in_progress: bool
    last_backup_at: str | None = None
    last_backup_state: str | None = None  # "completed" | "failed" | None


@dataclass(frozen=True)
class HALogEntry:
    level: str | None
    message: str
    name: str | None = None
    source: str | None = None
    timestamp: float | None = None
    count: int = 1
    exception: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> "HALogEntry":
        msg = d.get("message")
        if isinstance(msg, list):
            msg = " ".join(str(m) for m in msg)
        src = d.get("source")
        if isinstance(src, (list, tuple)):
            src = ":".join(str(p) for p in src)
        return cls(
            level=d.get("level"),
            message=msg or "",
            name=d.get("name"),
            source=src,
            timestamp=d.get("timestamp"),
            count=int(d.get("count", 1) or 1),
            exception=d.get("exception") or None,
        )


@dataclass(frozen=True)
class HAHealth:
    online: bool
    install_type: str = "unknown"  # os | supervised | container | unknown
    core_version: str | None = None
    os_version: str | None = None
    supervisor_version: str | None = None
    updates_available: int = 0
    error_count: int = 0
    latency_ms: int | None = None
    status_message: str | None = None


@dataclass(frozen=True)
class HasmSnapshot:
    """Full snapshot returned by the client on each polling cycle.

    `location_name` is used for the device name. `updates` feeds the update platform.
    `backup_state` is best-effort (None if not readable)."""

    health: HAHealth
    location_name: str | None = None
    updates: tuple[HAUpdate, ...] = ()
    backup_state: HABackupState | None = None
