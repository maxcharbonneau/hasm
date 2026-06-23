"""Shared fixtures for the HASM tests."""

from __future__ import annotations

import aiohttp
import pytest
import pytest_socket

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(fixturedef):
    """Allow socket.socketpair() for event loop creation.

    On Windows, Home Assistant's event loop factory uses socket.socketpair()
    (AF_INET fallback in the absence of AF_UNIX), blocked by default by
    pytest-socket. The loop is built during setup of the `event_loop` fixture
    (after the pytest_runtest_setup hooks), hence this wrapper around
    pytest_fixture_setup: we re-enable the socket just before. Real network
    calls remain covered by aioclient_mock (no outgoing traffic)."""
    if fixturedef.argname == "event_loop":
        pytest_socket.enable_socket()
    yield


def pytest_configure(config):
    """Avoid aiodns (AsyncResolver) during session creation on Windows.

    Home Assistant's async_get_clientsession() builds its connector with
    aiohttp.AsyncResolver (aiodns), which requires a SelectorEventLoop on Windows;
    but the test plugin forces a ProactorEventLoop, which makes the mere
    instantiation of the resolver fail (winloop import). Since outgoing traffic is
    intercepted by aioclient_mock, no DNS is resolved in tests: so, from pytest
    configuration onward and globally, we substitute the default ThreadedResolver
    for AsyncResolver. Production code stays unchanged (aiodns works normally on
    Linux/HAOS).

    Replacing DefaultResolver is not enough: homeassistant/helpers/aiohttp_client.py
    *explicitly* instantiates AsyncResolver() (resolver=AsyncResolver() in
    _async_get_connector). So we alias AsyncResolver -> ThreadedResolver both on
    the aiohttp modules (aiohttp, aiohttp.resolver, aiohttp.connector) and on the
    name already imported into homeassistant.helpers.aiohttp_client
    (`from aiohttp.resolver import AsyncResolver`, bound at the time the HA module
    is imported), so that every AsyncResolver() becomes a ThreadedResolver."""
    import aiohttp.connector as _connector
    import aiohttp.resolver as _resolver
    from homeassistant.helpers import aiohttp_client as _ha_aiohttp_client

    _threaded = aiohttp.ThreadedResolver

    # Default resolver (already present) + explicit alias of AsyncResolver.
    _resolver.DefaultResolver = _threaded
    _connector.DefaultResolver = _threaded
    aiohttp.AsyncResolver = _threaded
    _resolver.AsyncResolver = _threaded
    _connector.AsyncResolver = _threaded
    # Name already imported in the HA module that calls AsyncResolver() directly.
    _ha_aiohttp_client.AsyncResolver = _threaded


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of custom_components/hasm in the tests."""
    yield
