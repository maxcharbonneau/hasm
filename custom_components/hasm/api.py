"""Async API client for a remote Home Assistant instance.

Port of app/ha_client/client.py (synchronous) to aiohttp. This module imports
NOTHING from homeassistant.*: it receives an injected aiohttp.ClientSession and
stays testable on its own."""

from __future__ import annotations

import asyncio
import json
import time
from urllib.parse import urlparse, urlunparse

import aiohttp

from .exceptions import (
    HasmAuthError,
    HasmConnectionError,
    HasmError,
    HasmResponseError,
)
from .const import BACKUP_BUSY_STATES
from .models import (
    HAAgentBackupSummary,
    HABackupAgent,
    HABackupOverview,
    HAConfig,
    HAHealth,
    HALogEntry,
    HAStorage,
    HAUpdate,
    HasmSnapshot,
)

_ERROR_LEVELS = ("ERROR", "CRITICAL")
_OS_SLUG = "home_assistant_operating_system"
_SUPERVISOR_SLUG = "home_assistant_supervisor"
_FEATURE_PROGRESS = 4  # UpdateEntityFeature.PROGRESS
_FEATURE_BACKUP = 8  # UpdateEntityFeature.BACKUP


# --- Pure parsers (no I/O) -----------------------------------------------------


def parse_updates(states: list[dict]) -> list[HAUpdate]:
    updates: list[HAUpdate] = []
    for s in states:
        entity_id = s.get("entity_id", "")
        if not entity_id.startswith("update."):
            continue
        attrs = s.get("attributes", {}) or {}
        if attrs.get("hasm_mirror"):
            # HASM mirror: never re-mirror our own entities (loop prevention,
            # incl. self-supervision and the A->B->A chain).
            continue
        features = int(attrs.get("supported_features") or 0)
        pct = attrs.get("update_percentage")
        try:
            pct = float(pct) if pct is not None else None
        except (TypeError, ValueError):
            pct = None
        updates.append(
            HAUpdate(
                entity_id=entity_id,
                title=attrs.get("title"),
                installed_version=attrs.get("installed_version"),
                latest_version=attrs.get("latest_version"),
                update_available=(s.get("state") == "on"),
                supports_backup=bool(features & _FEATURE_BACKUP),
                in_progress=bool(attrs.get("in_progress")),
                supports_progress=bool(features & _FEATURE_PROGRESS),
                update_percentage=pct,
            )
        )
    return updates


def _system_entity(states: list[dict], slug: str) -> dict | None:
    for s in states:
        eid = s.get("entity_id", "") or ""
        if eid.startswith("update.") and slug in eid:
            return s
    return None


def version_of(states: list[dict], slug: str) -> str | None:
    s = _system_entity(states, slug)
    if s is not None:
        return (s.get("attributes", {}) or {}).get("installed_version")
    return None


def detect_install_type(components: list[str], states: list[dict]) -> str:
    """os | supervised | container. Core and Container are indistinguishable remotely."""
    if _system_entity(states, _OS_SLUG) is not None:
        return "os"
    if "hassio" in components:
        return "supervised"
    return "container"


def count_error_entries(entries: list[HALogEntry]) -> int:
    return sum(1 for e in entries if (e.level or "").upper() in _ERROR_LEVELS)


def parse_backup_agents(agents_info: dict) -> list[HABackupAgent]:
    out: list[HABackupAgent] = []
    for a in (agents_info or {}).get("agents") or []:
        aid = a.get("agent_id")
        if aid:
            out.append(HABackupAgent(agent_id=aid, name=a.get("name")))
    return out


def _is_full(backup: dict) -> bool:
    # No explicit "type" field in HA; a "full" backup includes Home Assistant core.
    # APPROXIMATION: a *partial* backup that happens to include HA core would also
    # count as "full" here. Accepted trade-off for supervision (HA exposes no
    # explicit backup "type").
    return bool(backup.get("homeassistant_included"))


def summarize_backups(agents_info: dict, backup_info: dict) -> HABackupOverview:
    backup_info = backup_info or {}
    agents = parse_backup_agents(agents_info)
    state = backup_info.get("state") or None
    errors = backup_info.get("agent_errors") or {}
    backups = backup_info.get("backups") or []
    per_agent: list[HAAgentBackupSummary] = []
    for ag in agents:
        aid = ag.agent_id
        sizes = 0
        count = 0
        last_full: str | None = None
        for b in backups:
            stored = b.get("agents") or {}
            if aid not in stored:
                continue
            count += 1
            entry = stored.get(aid) or {}
            sizes += int(entry.get("size") or 0)
            succeeded = aid not in (b.get("failed_agent_ids") or [])
            if succeeded and _is_full(b):
                d = b.get("date")
                if d and (last_full is None or d > last_full):
                    last_full = d
        per_agent.append(
            HAAgentBackupSummary(
                agent_id=aid,
                last_full_at=last_full,
                total_size_bytes=sizes,
                backup_count=count,
                has_problem=aid in errors,
            )
        )
    return HABackupOverview(
        state=state,
        in_progress=state in BACKUP_BUSY_STATES,
        last_completed_at=backup_info.get("last_completed_automatic_backup"),
        next_at=backup_info.get("next_automatic_backup"),
        agents=tuple(agents),
        per_agent=tuple(per_agent),
    )


_GB = 1024**3
_UNIT_TO_BYTES = {
    "b": 1,
    "bytes": 1,
    "kb": 1000,
    "kib": 1024,
    "mb": 1000**2,
    "mib": 1024**2,
    "gb": 1000**3,
    "gib": 1024**3,
    "tb": 1000**4,
    "tib": 1024**4,
}


def parse_host_storage(host_info: dict) -> HAStorage | None:
    data = (host_info or {}).get("data", host_info) or {}
    total, used, free = (
        data.get("disk_total"),
        data.get("disk_used"),
        data.get("disk_free"),
    )
    if total is None and free is None:
        return None
    # Supervisor reports GB floats.
    tb = int(total * _GB) if total is not None else None
    ub = int(used * _GB) if used is not None else None
    fb = int(free * _GB) if free is not None else None
    pct = round(used / total * 100, 1) if (total and used is not None) else None
    return HAStorage(
        source="host_info", free_bytes=fb, used_bytes=ub, total_bytes=tb, used_percent=pct
    )


def _to_bytes(state: str, unit: str | None) -> int | None:
    try:
        val = float(state)
    except (TypeError, ValueError):
        return None
    return int(val * _UNIT_TO_BYTES.get((unit or "").lower(), 1))


def parse_systemmonitor_storage(states: list[dict]) -> HAStorage | None:
    free = pct = used = total = None
    for s in states or []:
        eid = (s.get("entity_id") or "").lower()
        if "disk" not in eid and "system_monitor" not in eid:
            continue
        attrs = s.get("attributes") or {}
        unit = attrs.get("unit_of_measurement")
        if "free" in eid and free is None:
            free = _to_bytes(s.get("state"), unit)
        elif ("usage" in eid or "use_percent" in eid or unit == "%") and pct is None:
            try:
                pct = float(s.get("state"))
            except (TypeError, ValueError):
                pct = None
        elif "used" in eid and used is None:
            used = _to_bytes(s.get("state"), unit)
    if free is None and pct is None and used is None:
        return None
    return HAStorage(
        source="systemmonitor",
        free_bytes=free,
        used_bytes=used,
        total_bytes=total,
        used_percent=pct,
    )


# --- Client (REST + WebSocket) -------------------------------------------------


class HasmApiClient:
    """Async client for ONE remote HA instance (REST + WebSocket, Bearer token).

    `session` is injected (in production: async_get_clientsession(hass, verify_ssl)).
    No dependency on homeassistant.*."""

    def __init__(
        self,
        base_url: str,
        token: str,
        session: aiohttp.ClientSession,
        *,
        verify_ssl: bool = True,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._session = session
        self._ssl = verify_ssl  # aiohttp: ssl=False disables verification
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._headers = {"Authorization": f"Bearer {token}"}

    # --- Low-level REST ---
    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        read_timeout: float | None = None,
    ):
        url = self._base_url + path
        timeout = (
            aiohttp.ClientTimeout(total=read_timeout) if read_timeout else self._timeout
        )
        try:
            async with self._session.request(
                method,
                url,
                headers=self._headers,
                ssl=self._ssl,
                timeout=timeout,
                allow_redirects=False,  # internal redirect guard
                json=json_body,
            ) as resp:
                if resp.status in (401, 403):
                    raise HasmAuthError("Token rejected by the Home Assistant instance")
                if resp.status >= 400:
                    raise HasmResponseError(f"HTTP response {resp.status} on {path}")
                text = await resp.text()
                return resp.status, text
        except asyncio.TimeoutError as e:
            raise HasmConnectionError(f"Timeout while contacting {path}") from e
        except aiohttp.ClientError as e:
            raise HasmConnectionError(f"Instance unreachable: {e}") from e

    async def _get_json(self, path: str):
        _, text = await self._request("GET", path)
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise HasmResponseError(f"Unreadable JSON response on {path}") from e

    # --- Public REST API ---
    async def async_test_connection(self) -> bool:
        await self._request("GET", "/api/")
        return True

    async def async_get_config(self) -> HAConfig:
        data = await self._get_json("/api/config") or {}
        return HAConfig(
            core_version=data.get("version"),
            location_name=data.get("location_name"),
            components=list(data.get("components", [])),
        )

    async def async_get_states(self) -> list[dict]:
        return await self._get_json("/api/states") or []

    async def async_call_service(
        self, domain: str, service: str, service_data: dict | None = None
    ) -> None:
        """POST /api/services/{domain}/{service}. Used by buttons + generic service."""
        await self._request(
            "POST", f"/api/services/{domain}/{service}", json_body=service_data or {}
        )

    async def async_install_update(
        self, entity_id: str, *, version: str | None = None, backup: bool = False
    ) -> str:
        """Returns 'accepted' (2xx) or 'initiated_background' (read-timeout: HA installs
        in the background via asyncio.shield, typical for OS/Core updates + backup).
        Raises otherwise."""
        body: dict = {"entity_id": entity_id}
        if version:
            body["version"] = version
        if backup:
            body["backup"] = True
        url = self._base_url + "/api/services/update/install"
        try:
            async with self._session.post(
                url,
                headers=self._headers,
                ssl=self._ssl,
                json=body,
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(sock_connect=10.0, total=15.0),
            ) as resp:
                if resp.status in (401, 403):
                    raise HasmAuthError("Token rejected by the Home Assistant instance")
                if resp.status >= 400:
                    raise HasmResponseError(
                        f"Home Assistant refused the installation (HTTP {resp.status})"
                    )
                await resp.read()
                return "accepted"
        except asyncio.TimeoutError:
            # The command may have been sent; the install continues on the HA side.
            # NOT a failure.
            return "initiated_background"
        except aiohttp.ClientError as e:
            raise HasmConnectionError(f"Instance unreachable: {e}") from e

    # --- WebSocket (system_log/list, backup/info) ---
    def _ws_url(self) -> str:
        p = urlparse(self._base_url)
        scheme = "wss" if p.scheme == "https" else "ws"
        return urlunparse((scheme, p.netloc, "/api/websocket", "", "", ""))

    async def _ws_request(self, command_type: str, *, command_id: int = 1):
        """Opens the WS, handshake auth_required->auth->auth_ok, sends {id,type},
        returns its `result`. Error mapping identical to the original."""
        # aiohttp 3.11: ws_connect(timeout=...) expects a ClientWSTimeout (not a
        # float as in versions <3.9). ws_receive bounds the read of each frame
        # (handshake and result), which covers the original's need.
        ws_timeout = aiohttp.ClientWSTimeout(ws_receive=self._timeout.total)
        try:
            async with self._session.ws_connect(
                self._ws_url(), ssl=self._ssl, timeout=ws_timeout
            ) as ws:
                hello = json.loads(await ws.receive_str())
                if hello.get("type") != "auth_required":
                    raise HasmResponseError(
                        f"Unexpected WS handshake: {hello.get('type')}"
                    )
                await ws.send_str(
                    json.dumps({"type": "auth", "access_token": self._token})
                )
                auth = json.loads(await ws.receive_str())
                if auth.get("type") == "auth_invalid":
                    raise HasmAuthError(
                        "Token rejected by the Home Assistant WebSocket"
                    )
                if auth.get("type") != "auth_ok":
                    raise HasmResponseError(f"Unexpected WS auth: {auth.get('type')}")
                await ws.send_str(json.dumps({"id": command_id, "type": command_type}))
                # Backstop: if the expected result frame never arrives, the
                # ws_receive timeout (ClientWSTimeout) bounds each read and exits.
                while True:
                    msg = json.loads(await ws.receive_str())
                    if msg.get("id") == command_id and msg.get("type") == "result":
                        break
                if not msg.get("success", False):
                    raise HasmResponseError(
                        f"{command_type} failed on the Home Assistant side"
                    )
                return msg.get("result")
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, TypeError) as e:
            raise HasmConnectionError(f"WebSocket failure: {e}") from e

    async def async_get_system_log(self) -> list[HALogEntry]:
        result = await self._ws_request("system_log/list")
        return [HALogEntry.from_dict(e) for e in (result or [])]

    # --- Supervision aggregate ---
    async def async_get_snapshot(self) -> "HasmSnapshot":
        """Supervision aggregate. `online` depends ONLY on /api/config (lightweight).
        states, system log and backup are best-effort: their failure degrades the metrics
        but does NOT take the instance offline. Warnings recorded in status_message."""
        start = time.monotonic()
        try:
            config = await self.async_get_config()
        except HasmError as e:
            return HasmSnapshot(health=HAHealth(online=False, status_message=str(e)))

        warnings: list[str] = []

        states: list[dict] = []
        try:
            states = await self.async_get_states()
        except HasmError as e:
            warnings.append(f"states unavailable ({e})")

        error_count = 0
        try:
            error_count = count_error_entries(await self.async_get_system_log())
        except HasmError as e:
            warnings.append(f"system log unavailable ({e})")

        updates = parse_updates(states)
        latency_ms = int((time.monotonic() - start) * 1000)
        health = HAHealth(
            online=True,
            install_type=detect_install_type(config.components, states),
            core_version=config.core_version,
            os_version=version_of(states, _OS_SLUG),
            supervisor_version=version_of(states, _SUPERVISOR_SLUG),
            updates_available=sum(1 for u in updates if u.update_available),
            error_count=error_count,
            latency_ms=latency_ms,
            status_message="; ".join(warnings) or None,
        )
        return HasmSnapshot(
            health=health,
            location_name=config.location_name,
            updates=tuple(updates),
        )
