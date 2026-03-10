"""Apple TV Twitch integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady

_LOGGER = logging.getLogger(__name__)

DOMAIN = "apple_tv_twitch"
PLATFORMS = [Platform.MEDIA_PLAYER]

# Confirmed via diagnostic.py on tvOS 26.3 (Apple TV 4K gen 3).
# NOTE: Deep links (twitch://stream/<channel>) are NOT supported by Twitch's
# tvOS app. The service opens the Twitch app to its home screen only.
TWITCH_BUNDLE_ID = "tv.twitch"

RECONNECT_DELAY = 30  # seconds between reconnect attempts


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Apple TV Twitch from a config entry."""
    manager = AppleTVTwitchManager(hass, entry)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager

    try:
        await manager.async_connect()
    except Exception as err:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise ConfigEntryNotReady(f"Could not connect to Apple TV: {err}") from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def handle_play_channel(call: ServiceCall) -> None:
        # channel_name is stored on the entity as an attribute but cannot be
        # used for navigation — Twitch tvOS rejects all URL deep link schemes.
        channel = call.data.get("channel_name", "").strip() or None
        await manager.async_launch_twitch(channel)

    hass.services.async_register(
        DOMAIN,
        "play_channel",
        handle_play_channel,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        manager: AppleTVTwitchManager = hass.data[DOMAIN].pop(entry.entry_id)
        await manager.async_disconnect()

    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, "play_channel")

    return unload_ok


class _PushDelegate:
    """Forward pyatv push updates to registered entity listeners."""

    def __init__(self, listeners: list[Callable]) -> None:
        self._listeners = listeners

    def playstatus_update(self, updater, playing) -> None:
        for cb in self._listeners:
            cb("playstatus_update", playing)

    def playstatus_error(self, updater, exception: Exception) -> None:
        _LOGGER.debug("Push status error: %s", exception)
        for cb in self._listeners:
            cb("playstatus_error", exception)

    def connection_lost(self, exception: Exception) -> None:
        _LOGGER.warning("Apple TV connection lost: %s", exception)
        for cb in self._listeners:
            cb("connection_lost", exception)

    def connection_closed(self) -> None:
        _LOGGER.debug("Apple TV connection closed")
        for cb in self._listeners:
            cb("connection_closed", None)


class AppleTVTwitchManager:
    """Manages the pyatv connection for the integration."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.atv = None
        self._listeners: list[Callable] = []
        self._connect_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_listener(self, callback: Callable) -> None:
        """Register an entity callback for push/connection events."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def unregister_listener(self, callback: Callable) -> None:
        try:
            self._listeners.remove(callback)
        except ValueError:
            pass

    async def async_connect(self) -> None:
        """Perform initial connection (raises on failure)."""
        await self._do_connect()
        self._connect_task = self.hass.async_create_background_task(
            self._connect_loop(), "apple_tv_twitch_reconnect"
        )

    async def async_disconnect(self) -> None:
        """Disconnect and cancel background tasks."""
        if self._connect_task:
            self._connect_task.cancel()
            try:
                await self._connect_task
            except asyncio.CancelledError:
                pass
        self._close_atv()

    async def async_open_twitch(self) -> None:
        """Launch the Twitch app on the Apple TV."""
        if self.atv is None:
            _LOGGER.error("Cannot open Twitch — not connected to Apple TV")
            return
        _LOGGER.debug("Launching Twitch app (%s)", TWITCH_BUNDLE_ID)
        await self.atv.apps.launch_app(TWITCH_BUNDLE_ID)

    async def async_launch_twitch(self, channel: str | None = None) -> None:
        """Launch Twitch and notify listeners so the entity updates optimistic state."""
        await self.async_open_twitch()
        for cb in self._listeners:
            cb("launched", channel)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _connect_loop(self) -> None:
        """Background loop that reconnects after disconnection."""
        while True:
            await asyncio.sleep(RECONNECT_DELAY)
            if self.atv is None:
                _LOGGER.debug("Attempting to reconnect to Apple TV…")
                try:
                    await self._do_connect()
                except Exception as err:
                    _LOGGER.debug("Reconnect failed: %s", err)

    async def _do_connect(self) -> None:
        """Scan and connect to the Apple TV, applying stored credentials."""
        try:
            import pyatv
            from pyatv.const import Protocol
        except ImportError as err:
            raise RuntimeError("pyatv is not installed") from err

        address = self.entry.data["address"]
        results = await pyatv.scan(
            hosts=[address], timeout=5, loop=asyncio.get_event_loop()
        )
        if not results:
            raise RuntimeError(f"No Apple TV found at {address}")

        conf = results[0]

        credentials: dict = self.entry.data.get("credentials", {})
        for proto_key, cred_str in credentials.items():
            if not cred_str:
                continue
            try:
                proto = Protocol(int(proto_key))
                svc = conf.get_service(proto)
                if svc:
                    conf.set_credentials(proto, cred_str)
            except (ValueError, KeyError):
                _LOGGER.debug("Skipping unknown protocol key %s", proto_key)

        loop = asyncio.get_event_loop()
        atv = await pyatv.connect(conf, loop)

        delegate = _PushDelegate(self._listeners)
        atv.listener = delegate
        atv.push_updater.listener = delegate
        atv.push_updater.start(initial_delay=0)

        self._close_atv()
        self.atv = atv
        _LOGGER.info("Connected to Apple TV at %s", address)

        for cb in self._listeners:
            cb("connected", None)

    def _close_atv(self) -> None:
        if self.atv is not None:
            try:
                self.atv.close()
            except Exception:
                pass
            self.atv = None
