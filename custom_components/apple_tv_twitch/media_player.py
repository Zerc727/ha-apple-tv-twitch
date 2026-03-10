"""Apple TV Twitch media player entity."""
from __future__ import annotations

import logging
from datetime import timedelta
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

SCAN_INTERVAL = timedelta(seconds=10)

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


def _extract_channel_name(content_id: str | None) -> str | None:
    """
    Parse channel name from content_identifier.

    Update this function after running diagnostic.py — the actual format
    depends on what Twitch sends.  Common patterns:
      - "channel:xqc"         → split on ":" → "xqc"
      - "twitch:stream:xqc"  → last segment → "xqc"
      - raw channel name      → returned as-is
    """
    if not content_id:
        return None
    parts = content_id.split(":")
    # Return the last non-empty segment
    for part in reversed(parts):
        if part:
            return part
    return content_id


class AppleTVTwitchMediaPlayer(MediaPlayerEntity):
    """Media player that reflects Twitch activity on an Apple TV."""

    _attr_has_entity_name = True
    _attr_name = "Twitch"
    _attr_supported_features = SUPPORTED_FEATURES

    def __init__(self, manager: AppleTVTwitchManager, entry: ConfigEntry) -> None:
        self._manager = manager
        self._entry = entry
        self._playing = None
        self._is_twitch_active = False
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
        """Handle push events from the manager."""
        if event_type == "playstatus_update":
            self._playing = data
        elif event_type in ("connection_lost", "connection_closed"):
            self._connected = False
            self._playing = None
        elif event_type == "connected":
            self._connected = True
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # HA polling fallback (app detection doesn't fire push updates)
    # ------------------------------------------------------------------

    async def async_update(self) -> None:
        """Poll the Apple TV for active app — Twitch doesn't send MRP push on launch."""
        atv = self._manager.atv
        if atv is None:
            self._connected = False
            self._is_twitch_active = False
            return

        self._connected = True
        try:
            app = atv.metadata.app
            self._is_twitch_active = (
                app is not None and app.identifier == TWITCH_BUNDLE_ID
            )

            # Also refresh playing metadata when Twitch is active
            if self._is_twitch_active:
                try:
                    self._playing = await atv.metadata.playing()
                except Exception:
                    pass
        except Exception as err:
            _LOGGER.debug("Error polling Apple TV metadata: %s", err)

    # ------------------------------------------------------------------
    # State properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> MediaPlayerState:
        if not self._connected or self._manager.atv is None:
            return MediaPlayerState.OFF
        if self._is_twitch_active:
            return MediaPlayerState.PLAYING
        return MediaPlayerState.IDLE

    @property
    def app_id(self) -> str:
        return TWITCH_BUNDLE_ID

    @property
    def app_name(self) -> str:
        return "Twitch"

    @property
    def media_title(self) -> str | None:
        if self._playing is not None:
            channel = _extract_channel_name(
                getattr(self._playing, "content_identifier", None)
            )
            if channel:
                return channel
        return "Twitch" if self._is_twitch_active else None

    @property
    def media_content_id(self) -> str | None:
        if self._playing is not None:
            return getattr(self._playing, "content_identifier", None)
        return None

    @property
    def media_content_type(self) -> str | None:
        return "channel" if self._is_twitch_active else None

    # ------------------------------------------------------------------
    # Playback controls (forwarded to pyatv remote_control)
    # ------------------------------------------------------------------

    async def async_media_play(self) -> None:
        if self._manager.atv:
            await self._manager.atv.remote_control.play()

    async def async_media_pause(self) -> None:
        if self._manager.atv:
            await self._manager.atv.remote_control.pause()

    async def async_media_stop(self) -> None:
        if self._manager.atv:
            await self._manager.atv.remote_control.stop()
