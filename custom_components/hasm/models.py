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
class HABackupAgent:
    agent_id: str
    name: str | None = None

    @property
    def is_local(self) -> bool:
        return self.agent_id.lower().endswith(".local")


@dataclass(frozen=True)
class HAAgentBackupSummary:
    agent_id: str
    last_full_at: str | None = None  # ISO date of last successful FULL backup on this agent
    total_size_bytes: int = 0  # sum of backup sizes stored on this agent
    backup_count: int = 0  # backups present on this agent
    has_problem: bool = False  # agent currently in failed/error state


@dataclass(frozen=True)
class HABackupOverview:
    state: str | None = None
    in_progress: bool = False
    last_completed_at: str | None = None  # last_completed_automatic_backup (global)
    next_at: str | None = None  # next_automatic_backup (global)
    agents: tuple[HABackupAgent, ...] = ()
    per_agent: tuple[HAAgentBackupSummary, ...] = ()


@dataclass(frozen=True)
class HAServerUsage:
    cpu_percent: float | None = None
    memory_percent: float | None = None
    disk_percent: float | None = None


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

    `location_name` is used for the device name. `updates` feeds the update platform."""

    health: HAHealth
    location_name: str | None = None
    updates: tuple[HAUpdate, ...] = ()
    backups: HABackupOverview | None = None
    server_usage: HAServerUsage | None = None
