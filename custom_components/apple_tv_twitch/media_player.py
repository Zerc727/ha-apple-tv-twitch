"""Apple TV Twitch media player entity."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, TWITCH_BUNDLE_ID, AppleTVTwitchManager

_LOGGER = logging.getLogger(__name__)

# NOTE: tvOS 26.3 dropped the MRP protocol, so metadata.app is not available.
# Active app detection is not possible on modern Apple TVs via pyatv.
# State reflects connection status only: ON = connected, OFF = not connected.

SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Apple TV Twitch media player."""
    manager: AppleTVTwitchManager = hass.data[DOMAIN][entry.entry_id]
    entity = AppleTVTwitchMediaPlayer(manager, entry)
    manager.register_listener(entity.on_push_event)
    async_add_entities([entity])


class AppleTVTwitchMediaPlayer(MediaPlayerEntity):
    """Media player entity for Twitch on Apple TV.

    Capabilities confirmed via diagnostic on tvOS 26.3:
    - Launch Twitch app: YES (bundle ID: tv.twitch)
    - Deep link to channel: NO (Twitch tvOS app rejects URL schemes)
    - Active app detection: NO (MRP protocol removed in tvOS 16+)
    - Playing metadata: NO (Twitch exposes nothing via MRP/Companion)

    State: IDLE when connected to Apple TV, OFF when disconnected.
    Use the play_channel service or media_play to open the Twitch app.
    """

    _attr_has_entity_name = True
    _attr_name = "Twitch"
    _attr_supported_features = SUPPORTED_FEATURES

    def __init__(self, manager: AppleTVTwitchManager, entry: ConfigEntry) -> None:
        self._manager = manager
        self._entry = entry
        self._connected = manager.atv is not None

        device_name = entry.data.get("name", "Apple TV")
        self._attr_unique_id = f"{entry.entry_id}_twitch"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="Apple",
            model="Apple TV",
        )

    # ------------------------------------------------------------------
    # Push event handler (called by AppleTVTwitchManager)
    # ------------------------------------------------------------------

    @callback
    def on_push_event(self, event_type: str, data: Any) -> None:
        """Handle push/connection events from the manager."""
        if event_type in ("connection_lost", "connection_closed"):
            self._connected = False
        elif event_type == "connected":
            self._connected = True
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # State properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> MediaPlayerState:
        """Return IDLE when connected (app detection not possible), OFF otherwise."""
        if not self._connected or self._manager.atv is None:
            return MediaPlayerState.OFF
        return MediaPlayerState.IDLE

    @property
    def app_id(self) -> str:
        return TWITCH_BUNDLE_ID

    @property
    def app_name(self) -> str:
        return "Twitch"

    # ------------------------------------------------------------------
    # Actions — all open the Twitch app (channel navigation not supported)
    # ------------------------------------------------------------------

    async def async_media_play(self) -> None:
        """Open the Twitch app."""
        await self._manager.async_open_twitch()

    async def async_media_pause(self) -> None:
        if self._manager.atv:
            await self._manager.atv.remote_control.pause()

    async def async_media_stop(self) -> None:
        if self._manager.atv:
            await self._manager.atv.remote_control.stop()
