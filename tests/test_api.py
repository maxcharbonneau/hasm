import asyncio
import json

import pytest

from custom_components.hasm.api import (
    HasmApiClient,
    count_error_entries,
    detect_install_type,
    parse_updates,
    version_of,
)
from custom_components.hasm.exceptions import (
    HasmAuthError,
    HasmConnectionError,
    HasmResponseError,
)
from custom_components.hasm.models import (
    HAAgentBackupSummary,
    HABackupAgent,
    HABackupOverview,
    HALogEntry,
    HAStorage,
)

OS_SLUG = "home_assistant_operating_system"


def test_backup_agent_local_detection():
    assert HABackupAgent(agent_id="hassio.local", name="Local").is_local is True
    assert HABackupAgent(agent_id="hassio.my_nas", name="NAS").is_local is False
    assert HABackupAgent(agent_id="cloud.cloud", name="Cloud").is_local is False
    assert HABackupAgent(agent_id="backup.local", name="L").is_local is True


@pytest.fixture
def client(hass, aioclient_mock):
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    session = async_get_clientsession(hass)
    return HasmApiClient("https://ha.example", "TOKEN", session, verify_ssl=True)


def test_log_entry_from_dict_joins_list_message_and_source():
    entry = HALogEntry.from_dict(
        {
            "level": "ERROR",
            "message": ["boom", "details"],
            "source": ["sensor.py", 42],
            "name": "homeassistant.components.x",
            "count": 3,
        }
    )
    assert entry.level == "ERROR"
    assert entry.message == "boom details"
    assert entry.source == "sensor.py:42"
    assert entry.count == 3


def test_parse_updates_reads_features_and_percentage():
    states = [
        {
            "entity_id": "update.home_assistant_operating_system_update",
            "state": "on",
            "attributes": {
                "title": "Home Assistant OS",
                "installed_version": "12.0",
                "latest_version": "13.0",
                "supported_features": 8 | 4,  # BACKUP | PROGRESS
                "in_progress": False,
                "update_percentage": "42",
            },
        },
        {"entity_id": "sensor.cpu", "state": "5"},  # ignored
    ]
    updates = parse_updates(states)
    assert len(updates) == 1
    u = updates[0]
    assert u.update_available is True
    assert u.supports_backup is True
    assert u.supports_progress is True
    assert u.update_percentage == 42.0


def test_parse_updates_skips_hasm_mirror_entities():
    states = [
        {
            "entity_id": "update.home_assistant_core",
            "state": "on",
            "attributes": {"installed_version": "1", "latest_version": "2"},
        },
        {
            "entity_id": "update.maison_core",
            "state": "on",
            "attributes": {"hasm_mirror": True, "installed_version": "1"},
        },
    ]
    updates = parse_updates(states)
    assert len(updates) == 1
    assert updates[0].entity_id == "update.home_assistant_core"


def test_version_of_matches_by_substring_with_update_suffix():
    states = [
        {
            "entity_id": "update.home_assistant_operating_system_update",
            "attributes": {"installed_version": "13.1"},
        }
    ]
    assert version_of(states, OS_SLUG) == "13.1"


def test_detect_install_type():
    os_states = [
        {"entity_id": "update.home_assistant_operating_system_update", "attributes": {}}
    ]
    assert detect_install_type([], os_states) == "os"
    assert detect_install_type(["hassio"], []) == "supervised"
    assert detect_install_type([], []) == "container"


def test_count_error_entries_counts_error_and_critical():
    entries = [
        HALogEntry(level="ERROR", message="x"),
        HALogEntry(level="critical", message="y"),
        HALogEntry(level="WARNING", message="z"),
    ]
    assert count_error_entries(entries) == 2


_AGENTS = {
    "agents": [
        {"agent_id": "hassio.local", "name": "Local"},
        {"agent_id": "cloud.cloud", "name": "Cloud"},
    ]
}
_BACKUPS = {
    "state": "idle",
    "last_completed_automatic_backup": "2026-06-20T03:00:00+00:00",
    "next_automatic_backup": "2026-06-21T03:00:00+00:00",
    "agent_errors": {},
    "backups": [
        {  # full, on both agents, ok
            "backup_id": "a",
            "date": "2026-06-20T03:00:00+00:00",
            "homeassistant_included": True,
            "agents": {"hassio.local": {"size": 100}, "cloud.cloud": {"size": 100}},
            "failed_agent_ids": [],
        },
        {  # partial (no core) — must NOT count as full
            "backup_id": "b",
            "date": "2026-06-22T03:00:00+00:00",
            "homeassistant_included": False,
            "agents": {"hassio.local": {"size": 10}},
            "failed_agent_ids": [],
        },
        {  # full but failed on cloud — counts for local only
            "backup_id": "c",
            "date": "2026-06-19T03:00:00+00:00",
            "homeassistant_included": True,
            "agents": {"hassio.local": {"size": 50}},
            "failed_agent_ids": ["cloud.cloud"],
        },
    ],
}


def test_parse_backup_agents():
    from custom_components.hasm.api import parse_backup_agents

    agents = parse_backup_agents(_AGENTS)
    assert [a.agent_id for a in agents] == ["hassio.local", "cloud.cloud"]
    assert agents[0].name == "Local"


def test_summarize_backups_per_agent():
    from custom_components.hasm.api import summarize_backups

    ov = summarize_backups(_AGENTS, _BACKUPS)
    assert ov.state == "idle" and ov.in_progress is False
    assert ov.last_completed_at == "2026-06-20T03:00:00+00:00"
    by = {s.agent_id: s for s in ov.per_agent}
    # local: last FULL = backup "a" (2026-06-20); "b" is partial, ignored
    assert by["hassio.local"].last_full_at == "2026-06-20T03:00:00+00:00"
    assert by["hassio.local"].total_size_bytes == 160  # 100 + 10 + 50
    assert by["hassio.local"].backup_count == 3
    # cloud: only "a" succeeded (c failed on cloud) → last full = a
    assert by["cloud.cloud"].last_full_at == "2026-06-20T03:00:00+00:00"
    assert by["cloud.cloud"].total_size_bytes == 100
    assert by["cloud.cloud"].backup_count == 1


def test_summarize_backups_in_progress_and_problem():
    from custom_components.hasm.api import summarize_backups

    data = {**_BACKUPS, "state": "create_backup", "agent_errors": {"cloud.cloud": "auth"}}
    ov = summarize_backups(_AGENTS, data)
    assert ov.in_progress is True
    by = {s.agent_id: s for s in ov.per_agent}
    assert by["cloud.cloud"].has_problem is True
    assert by["hassio.local"].has_problem is False


def test_parse_host_storage_gb_to_bytes():
    from custom_components.hasm.api import parse_host_storage

    # Supervisor host/info: disk sizes are GB floats
    host = {"data": {"disk_total": 100.0, "disk_used": 40.0, "disk_free": 60.0}}
    st = parse_host_storage(host)
    assert st.source == "host_info"
    assert st.total_bytes == int(100.0 * 1024**3)
    assert st.free_bytes == int(60.0 * 1024**3)
    assert round(st.used_percent, 1) == 40.0


def test_parse_systemmonitor_storage_from_states():
    from custom_components.hasm.api import parse_systemmonitor_storage

    states = [
        {
            "entity_id": "sensor.system_monitor_disk_free",
            "state": "53.7",
            "attributes": {"device_class": "data_size", "unit_of_measurement": "GiB"},
        },
        {
            "entity_id": "sensor.system_monitor_disk_usage",
            "state": "46.0",
            "attributes": {"unit_of_measurement": "%"},
        },
    ]
    st = parse_systemmonitor_storage(states)
    assert st is not None and st.source == "systemmonitor"
    assert st.free_bytes == int(53.7 * 1024**3)  # GiB -> bytes
    assert round(st.used_percent, 1) == 46.0


def test_parse_systemmonitor_storage_absent():
    from custom_components.hasm.api import parse_systemmonitor_storage

    assert (
        parse_systemmonitor_storage([{"entity_id": "sensor.cpu", "state": "5"}]) is None
    )


async def test_get_host_info_ok(client, aioclient_mock):
    aioclient_mock.get(
        "https://ha.example/api/hassio/host/info",
        json={"result": "ok", "data": {"disk_total": 32.0, "disk_free": 8.0}},
    )
    data = await client.async_get_host_info()
    assert data["data"]["disk_total"] == 32.0


async def test_snapshot_includes_backups_and_storage(client, aioclient_mock, monkeypatch):
    aioclient_mock.get(
        "https://ha.example/api/config",
        json={"version": "2026.6.1", "location_name": "X", "components": ["hassio"]},
    )
    aioclient_mock.get("https://ha.example/api/states", json=[])
    aioclient_mock.get(
        "https://ha.example/api/hassio/host/info",
        json={
            "result": "ok",
            "data": {"disk_total": 10.0, "disk_used": 4.0, "disk_free": 6.0},
        },
    )

    async def fake_log(self):
        return []

    async def fake_agents(self):
        return {"agents": [{"agent_id": "hassio.local", "name": "Local"}]}

    async def fake_binfo(self):
        return {"state": "idle", "backups": [], "agent_errors": {}}

    monkeypatch.setattr(HasmApiClient, "async_get_system_log", fake_log)
    monkeypatch.setattr(HasmApiClient, "async_get_backup_agents_raw", fake_agents)
    monkeypatch.setattr(HasmApiClient, "async_get_backup_info_raw", fake_binfo)

    snap = await client.async_get_snapshot()
    assert snap.health.online is True
    assert snap.backups is not None and snap.backups.state == "idle"
    assert snap.storage is not None and snap.storage.source == "host_info"
    assert snap.storage.total_bytes == int(10.0 * 1024**3)


async def test_test_connection_ok(client, aioclient_mock):
    aioclient_mock.get("https://ha.example/api/", json={"message": "API running."})
    assert await client.async_test_connection() is True


async def test_get_raises_auth_on_401(client, aioclient_mock):
    aioclient_mock.get("https://ha.example/api/config", status=401)
    with pytest.raises(HasmAuthError):
        await client.async_get_config()


async def test_get_config_parses_version(client, aioclient_mock):
    aioclient_mock.get(
        "https://ha.example/api/config",
        json={
            "version": "2026.6.3",
            "location_name": "Maison",
            "components": ["hassio"],
        },
    )
    cfg = await client.async_get_config()
    assert cfg.core_version == "2026.6.3"
    assert cfg.location_name == "Maison"
    assert "hassio" in cfg.components


async def test_snapshot_online_with_degraded_states(
    client, aioclient_mock, monkeypatch
):
    aioclient_mock.get(
        "https://ha.example/api/config",
        json={
            "version": "2026.6.3",
            "location_name": "Maison",
            "components": ["hassio"],
        },
    )
    aioclient_mock.get(
        "https://ha.example/api/states", status=500
    )  # states KO -> degraded
    aioclient_mock.get(
        "https://ha.example/api/hassio/host/info", status=500
    )  # host/info KO -> no storage

    async def fake_log(self):
        raise HasmConnectionError("ws down")

    async def fake_agents(self):
        raise HasmConnectionError("ws down")

    async def fake_binfo(self):
        raise HasmConnectionError("ws down")

    monkeypatch.setattr(HasmApiClient, "async_get_system_log", fake_log)
    monkeypatch.setattr(HasmApiClient, "async_get_backup_agents_raw", fake_agents)
    monkeypatch.setattr(HasmApiClient, "async_get_backup_info_raw", fake_binfo)

    snap = await client.async_get_snapshot()
    assert snap.health.online is True
    assert snap.health.core_version == "2026.6.3"
    assert snap.location_name == "Maison"
    assert snap.health.status_message is not None
    assert snap.backups is None
    assert snap.storage is None


async def test_snapshot_offline_when_config_fails(client, aioclient_mock):
    aioclient_mock.get("https://ha.example/api/config", status=500)
    snap = await client.async_get_snapshot()
    assert snap.health.online is False
    assert snap.health.status_message


async def test_get_config_malformed_json_raises_response_error(client, aioclient_mock):
    # Unreadable JSON body on a 200: must be mapped into the HasmError hierarchy
    # (HasmResponseError) and NOT let a json.JSONDecodeError (ValueError) bubble up.
    aioclient_mock.get("https://ha.example/api/config", text="not json{")
    with pytest.raises(HasmResponseError):
        await client.async_get_config()


async def test_install_update_read_timeout_returns_background(client, aioclient_mock):
    # HAOS lesson #3: a read-timeout on the POST install is NOT a failure;
    # HA continues the installation in the background (asyncio.shield).
    aioclient_mock.post(
        "https://ha.example/api/services/update/install",
        exc=asyncio.TimeoutError(),
    )
    result = await client.async_install_update(
        "update.home_assistant_operating_system_update"
    )
    assert result == "initiated_background"


async def test_trigger_backup_read_timeout_returns_background(client, aioclient_mock):
    # A long backup blocks past our read timeout; the backup still runs server-side,
    # exactly like a long update install. The read-timeout is success, not an error.
    aioclient_mock.post(
        "https://ha.example/api/services/backup/create_automatic",
        exc=asyncio.TimeoutError(),
    )
    assert await client.async_trigger_backup() == "initiated_background"


class _FakeWS:
    """Minimal WebSocket: returns the `frames` in order via receive_str."""

    def __init__(self, frames: list[str]) -> None:
        self._frames = list(frames)
        self.sent: list[str] = []

    async def __aenter__(self) -> "_FakeWS":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def send_str(self, data: str) -> None:
        self.sent.append(data)

    async def receive_str(self) -> str:
        return self._frames.pop(0)


async def test_ws_auth_invalid_raises_auth_error(client, monkeypatch):
    fake = _FakeWS(
        [
            json.dumps({"type": "auth_required"}),
            json.dumps({"type": "auth_invalid"}),
        ]
    )

    def fake_ws_connect(*args, **kwargs):
        return fake

    monkeypatch.setattr(client._session, "ws_connect", fake_ws_connect)
    with pytest.raises(HasmAuthError):
        await client.async_get_system_log()
