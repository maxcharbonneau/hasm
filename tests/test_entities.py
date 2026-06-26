import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hasm.const import DOMAIN
from custom_components.hasm.models import HAHealth, HasmSnapshot
from custom_components.hasm.models import HAUpdate
from custom_components.hasm.models import (
    HAAgentBackupSummary,
    HABackupAgent,
    HABackupOverview,
    HAStorage,
)


@pytest.fixture
def entry():
    return MockConfigEntry(
        domain=DOMAIN,
        title="Maison",
        data={"url": "https://ha.example", "token": "TOKEN", "verify_ssl": True},
        options={"scan_interval": 120},
        unique_id="https://ha.example",
    )


async def _setup_with_snapshot(hass, entry, snap):
    entry.add_to_hass(hass)
    with patch(
        "custom_components.hasm.HasmApiClient.async_get_snapshot",
        new=AsyncMock(return_value=snap),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_connectivity_binary_sensor_on(hass, entry):
    snap = HasmSnapshot(health=HAHealth(online=True, core_version="2026.6.3"))
    await _setup_with_snapshot(hass, entry, snap)
    state = hass.states.get("binary_sensor.maison_connectivity")
    assert state is not None
    assert state.state == "on"


async def test_connectivity_binary_sensor_off_when_offline(hass, entry):
    snap = HasmSnapshot(health=HAHealth(online=False, status_message="unreachable"))
    await _setup_with_snapshot(hass, entry, snap)
    state = hass.states.get("binary_sensor.maison_connectivity")
    assert state is not None
    # Must stay available to report the offline state, NOT "unavailable".
    assert state.state == "off"


async def test_sensors_core_version_and_updates_count(hass, entry):
    snap = HasmSnapshot(
        health=HAHealth(
            online=True, core_version="2026.6.3", updates_available=2, error_count=5
        ),
        updates=(
            HAUpdate("update.core", "Core", "2026.6.0", "2026.6.3", True),
            HAUpdate("update.os", "OS", "12.0", "13.0", True),
        ),
    )
    await _setup_with_snapshot(hass, entry, snap)
    core = hass.states.get("sensor.maison_core_version")
    updates = hass.states.get("sensor.maison_updates_available")
    assert core.state == "2026.6.3"
    assert updates.state == "2"


async def test_update_entity_install_calls_client(hass, entry):
    snap = HasmSnapshot(
        health=HAHealth(online=True, core_version="2026.6.3"),
        updates=(
            HAUpdate(
                "update.home_assistant_core",
                "Core",
                "2026.6.0",
                "2026.6.3",
                update_available=True,
                supports_backup=True,
            ),
        ),
    )
    entry.add_to_hass(hass)
    install_mock = AsyncMock(return_value="accepted")
    with (
        patch(
            "custom_components.hasm.HasmApiClient.async_get_snapshot",
            new=AsyncMock(return_value=snap),
        ),
        patch(
            "custom_components.hasm.HasmApiClient.async_install_update",
            new=install_mock,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        states = [e for e in hass.states.async_entity_ids("update") if "maison" in e]
        assert states, "no update entity created"
        await hass.services.async_call(
            "update", "install", {"entity_id": states[0]}, blocking=True
        )
    install_mock.assert_awaited_once()
    assert install_mock.await_args.args[0] == "update.home_assistant_core"


async def test_update_entities_capped_at_configured_value(hass, entry, caplog):
    import logging
    from unittest.mock import patch as _patch, AsyncMock as _AsyncMock
    from custom_components.hasm.const import CONF_MAX_UPDATE_ENTITIES

    # entry with a SMALL configured cap to prove it is read from the options,
    # and not the default 250.
    entry2 = type(entry)(
        domain=entry.domain,
        title="Maison",
        data=dict(entry.data),
        options={"scan_interval": 120, CONF_MAX_UPDATE_ENTITIES: 3},
        unique_id=entry.unique_id,
    )
    many = tuple(
        HAUpdate(f"update.app_{i}", f"App {i}", "1.0", "2.0", update_available=True)
        for i in range(5)
    )
    snap = HasmSnapshot(
        health=HAHealth(online=True, core_version="2026.6.3"), updates=many
    )
    entry2.add_to_hass(hass)
    with (
        _patch(
            "custom_components.hasm.HasmApiClient.async_get_snapshot",
            new=_AsyncMock(return_value=snap),
        ),
        _patch(
            "homeassistant.components.persistent_notification.async_create"
        ) as notif,
        caplog.at_level(logging.WARNING),
    ):
        assert await hass.config_entries.async_setup(entry2.entry_id)
        await hass.async_block_till_done()
    update_ids = [e for e in hass.states.async_entity_ids("update") if "maison" in e]
    assert len(update_ids) <= 3
    assert notif.call_count == 1  # notification visible, only once
    warnings = [
        r for r in caplog.records if r.levelno == logging.WARNING and "hasm" in r.name
    ]
    assert len(warnings) >= 1


async def test_update_entities_default_cap_is_250(hass, entry):
    many = tuple(
        HAUpdate(f"update.app_{i}", f"App {i}", "1.0", "2.0", update_available=True)
        for i in range(60)
    )
    snap = HasmSnapshot(
        health=HAHealth(online=True, core_version="2026.6.3"), updates=many
    )
    await _setup_with_snapshot(hass, entry, snap)
    update_ids = [e for e in hass.states.async_entity_ids("update") if "maison" in e]
    assert len(update_ids) == 60  # below the default 250 -> all created


async def test_update_entity_added_on_later_refresh(hass, entry):
    from custom_components.hasm.api import parse_updates

    entry.add_to_hass(hass)
    snap_initial = HasmSnapshot(
        health=HAHealth(online=True, core_version="2026.6.3"), updates=()
    )
    mock = AsyncMock(return_value=snap_initial)
    with patch("custom_components.hasm.HasmApiClient.async_get_snapshot", new=mock):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert not [e for e in hass.states.async_entity_ids("update") if "maison" in e]

        # Later poll: a real update appears + a HASM mirror (must be ignored)
        later_updates = parse_updates(
            [
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
        )
        mock.return_value = HasmSnapshot(
            health=HAHealth(online=True, core_version="2026.6.3"),
            updates=tuple(later_updates),
        )
        coordinator = hass.config_entries.async_get_entry(
            entry.entry_id
        ).runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    update_ids = [e for e in hass.states.async_entity_ids("update") if "maison" in e]
    assert len(update_ids) == 1  # exactly one (the mirror filtered by parse_updates)


def test_icons_json_keys_match_translation_keys():
    """Local structural validation of icons.json (hassfest only runs in CI).

    Each entity.<platform>.<key> key in icons.json must match a translation_key
    actually declared by an entity, and vice versa. Catches a key typo before
    hassfest rejects it in CI.

    Translation keys come from three places, all collected here:
      * static description tables (SENSORS / BUTTONS),
      * `_attr_translation_key = "..."` literals on entity classes (the
        per-agent dynamic sensors, the backup-now button, binary sensors),
      * keys passed positionally into the global/storage sensor constructors
        (e.g. `HasmGlobalBackupSensor(coordinator, "backup_next", ...)`), which
        the entity sets as its translation_key in __init__.
    We read literals from source because HA exposes _attr_translation_key as a
    descriptor on Entity (reading via the class yields the property, not the
    value); the source is the truth.
    """
    import re

    from custom_components.hasm.sensor import SENSORS
    from custom_components.hasm.button import BUTTONS

    base = Path(__file__).resolve().parents[1] / "custom_components" / "hasm"
    icons = json.loads((base / "icons.json").read_text(encoding="utf-8"))

    def attr_keys(filename: str) -> set[str]:
        src = (base / filename).read_text(encoding="utf-8")
        return set(re.findall(r'_attr_translation_key\s*=\s*"([^"]+)"', src))

    sensor_src = (base / "sensor.py").read_text(encoding="utf-8")
    # Global + storage sensors take their translation_key as a string literal
    # immediately after the coordinator argument.
    ctor_keys = set(
        re.findall(
            r'Hasm(?:GlobalBackup|Storage)Sensor\(\s*coordinator,\s*"([^"]+)"',
            sensor_src,
        )
    )

    expected = {
        "binary_sensor": attr_keys("binary_sensor.py"),
        "sensor": {d.translation_key for d in SENSORS}
        | attr_keys("sensor.py")
        | ctor_keys,
        "button": {d.translation_key for d in BUTTONS} | attr_keys("button.py"),
    }
    actual = {platform: set(keys.keys()) for platform, keys in icons["entity"].items()}
    assert actual == expected, f"icons.json {actual} != entities {expected}"
    # All values are MDI icons under "default".
    for platform_keys in icons["entity"].values():
        for entry_def in platform_keys.values():
            assert entry_def["default"].startswith("mdi:")


async def test_update_entity_icon_and_no_picture(hass, entry):
    snap = HasmSnapshot(
        health=HAHealth(online=True, core_version="2026.6.3"),
        updates=(
            HAUpdate(
                "update.home_assistant_core",
                "Core",
                "1.0",
                "2.0",
                update_available=True,
            ),
        ),
    )
    await _setup_with_snapshot(hass, entry, snap)
    update_ids = [e for e in hass.states.async_entity_ids("update") if "maison" in e]
    assert update_ids
    state = hass.states.get(update_ids[0])
    assert state.attributes.get("icon") == "mdi:update"
    assert state.attributes.get("entity_picture") is None


def _overview():
    return HABackupOverview(
        state="idle", in_progress=False,
        last_completed_at="2026-06-20T03:00:00+00:00",
        agents=(HABackupAgent("hassio.local", "Local"),),
        per_agent=(HAAgentBackupSummary("hassio.local",
                   last_full_at="2026-06-20T03:00:00+00:00",
                   total_size_bytes=1048576, backup_count=4),),
    )


async def test_backup_per_destination_sensors(hass, entry):
    snap = HasmSnapshot(health=HAHealth(online=True, core_version="2026.6.1"),
                        backups=_overview())
    await _setup_with_snapshot(hass, entry, snap)
    # entity_id derives from the resolved friendly name (agent name "Local").
    size = hass.states.get("sensor.maison_backup_size_local")
    last = hass.states.get("sensor.maison_last_full_backup_local")
    # Canonical native value stays in bytes; HA converts to the suggested MB unit.
    # The state carries the full-precision converted value (1048576 B -> 1.048576 MB);
    # suggested_display_precision only rounds at the frontend display layer.
    assert size is not None
    assert size.attributes["unit_of_measurement"] == "MB"
    assert size.state == "1.048576"
    assert last is not None and "2026-06-20" in last.state


async def test_backup_problem_binary_sensor(hass, entry):
    ov = HABackupOverview(
        state="idle",
        agents=(HABackupAgent("cloud.cloud", "Cloud"),),
        per_agent=(HAAgentBackupSummary("cloud.cloud", has_problem=True),),
    )
    snap = HasmSnapshot(health=HAHealth(online=True, core_version="2026.6.1"), backups=ov)
    await _setup_with_snapshot(hass, entry, snap)
    state = hass.states.get("binary_sensor.maison_backup_problem_cloud")
    assert state is not None and state.state == "on"


async def test_global_backup_sensors(hass, entry):
    ov = HABackupOverview(state="idle", in_progress=False,
                          last_completed_at="2026-06-20T03:00:00+00:00",
                          next_at="2026-06-21T03:00:00+00:00")
    snap = HasmSnapshot(health=HAHealth(online=True, core_version="2026.6.1"), backups=ov)
    await _setup_with_snapshot(hass, entry, snap)
    assert "2026-06-20" in hass.states.get("sensor.maison_last_automatic_backup").state
    assert "2026-06-21" in hass.states.get("sensor.maison_next_automatic_backup").state
    assert hass.states.get("binary_sensor.maison_backup_in_progress").state == "off"


async def test_backup_now_button_calls_service(hass, entry):
    ov = HABackupOverview(state="idle", in_progress=False)
    snap = HasmSnapshot(health=HAHealth(online=True, core_version="2026.6.1"), backups=ov)
    entry.add_to_hass(hass)
    call_mock = AsyncMock()
    with patch("custom_components.hasm.HasmApiClient.async_get_snapshot",
               new=AsyncMock(return_value=snap)), \
         patch("custom_components.hasm.HasmApiClient.async_call_service", new=call_mock):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        btns = [e for e in hass.states.async_entity_ids("button") if "back_up_now" in e]
        assert btns
        await hass.services.async_call("button", "press", {"entity_id": btns[0]}, blocking=True)
    call_mock.assert_awaited_once_with("backup", "create_automatic")


async def test_backup_now_button_unavailable_when_running(hass, entry):
    ov = HABackupOverview(state="create_backup", in_progress=True)
    snap = HasmSnapshot(health=HAHealth(online=True, core_version="2026.6.1"), backups=ov)
    await _setup_with_snapshot(hass, entry, snap)
    btn = [e for e in hass.states.async_entity_ids("button") if "back_up_now" in e][0]
    assert hass.states.get(btn).state == "unavailable"


async def test_restart_button_calls_homeassistant_restart(hass, entry):
    snap = HasmSnapshot(health=HAHealth(online=True, core_version="2026.6.3"))
    entry.add_to_hass(hass)
    call_mock = AsyncMock()
    with (
        patch(
            "custom_components.hasm.HasmApiClient.async_get_snapshot",
            new=AsyncMock(return_value=snap),
        ),
        patch("custom_components.hasm.HasmApiClient.async_call_service", new=call_mock),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        buttons = [
            e
            for e in hass.states.async_entity_ids("button")
            if "maison" in e and "restart" in e
        ]
        assert buttons
        await hass.services.async_call(
            "button", "press", {"entity_id": buttons[0]}, blocking=True
        )
    call_mock.assert_awaited_once_with("homeassistant", "restart")


async def test_restart_button_is_a_control_not_config(hass, entry):
    # Restart/reload live in the device's "Controls" section: absence of an
    # entity_category (HA has no "control" category) places actionable entities there.
    snap = HasmSnapshot(health=HAHealth(online=True, core_version="2026.6.3"))
    await _setup_with_snapshot(hass, entry, snap)
    entity_id = next(
        e
        for e in hass.states.async_entity_ids("button")
        if "maison" in e and "restart" in e
    )
    reg_entry = er.async_get(hass).async_get(entity_id)
    assert reg_entry is not None
    assert reg_entry.entity_category is None


async def test_storage_sensors(hass, entry):
    snap = HasmSnapshot(
        health=HAHealth(online=True, core_version="2026.6.1"),
        storage=HAStorage(source="host_info", free_bytes=6*1024**3,
                          used_bytes=4*1024**3, total_bytes=10*1024**3, used_percent=40.0),
    )
    await _setup_with_snapshot(hass, entry, snap)
    assert hass.states.get("sensor.maison_disk_free").state == str(6*1024**3)
    assert hass.states.get("sensor.maison_disk_usage").state == "40.0"


async def test_storage_sensors_absent_when_no_source(hass, entry):
    snap = HasmSnapshot(health=HAHealth(online=True, core_version="2026.6.1"), storage=None)
    await _setup_with_snapshot(hass, entry, snap)
    assert hass.states.get("sensor.maison_disk_free") is None
