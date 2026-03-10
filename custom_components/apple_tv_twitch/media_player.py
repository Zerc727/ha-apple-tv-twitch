"""Apple TV Twitch media player entity."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, TWITCH_BUNDLE_ID, AppleTVTwitchManager

_LOGGER = logging.getLogger(__name__)

# How long after launch we optimistically report state = PLAYING.
# After this window expires with no re-launch, state reverts to IDLE.
OPTIMISTIC_PLAYING_WINDOW = timedelta(minutes=5)

SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.PLAY_MEDIA
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

    Confirmed capabilities (tvOS 26.3, Apple TV 4K gen 3):
      - Launch Twitch app:        YES  (bundle ID: tv.twitch)
      - Deep link to channel:     NO   (Twitch tvOS rejects all URL schemes)
      - Active app detection:     NO   (MRP removed in tvOS 16+)
      - Channel/playing metadata: NO   (Twitch exposes nothing via Companion)

    State is optimistic: shows PLAYING for OPTIMISTIC_PLAYING_WINDOW after
    launch, then reverts to IDLE.  OFF means not connected to Apple TV.
    """

    _attr_has_entity_name = True
    _attr_name = "Twitch"
    _attr_supported_features = SUPPORTED_FEATURES
    _attr_media_content_type = MediaType.APP

    def __init__(self, manager: AppleTVTwitchManager, entry: ConfigEntry) -> None:
        self._manager = manager
        self._entry = entry
        self._connected = manager.atv is not None
        self._launched_at: datetime | None = None
        self._last_channel: str | None = None

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
        elif event_type == "launched":
            # Service call triggered a launch — update optimistic state.
            # data = channel name string or None.
            self._launched_at = datetime.now()
            if data:
                self._last_channel = str(data).strip().lstrip("#").lower()
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def state(self) -> MediaPlayerState:
        if not self._connected or self._manager.atv is None:
            return MediaPlayerState.OFF
        if self._launched_at and (
            datetime.now() - self._launched_at < OPTIMISTIC_PLAYING_WINDOW
        ):
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
        """Return last-requested channel name, if any."""
        if self._last_channel:
            return self._last_channel
        return "Twitch" if self.state == MediaPlayerState.PLAYING else None

    @property
    def media_content_id(self) -> str | None:
        return self._last_channel

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {}
        if self._last_channel:
            attrs["last_channel"] = self._last_channel
        if self._launched_at:
            attrs["launched_at"] = self._launched_at.isoformat()
        attrs["channel_switching"] = "not supported (Twitch tvOS has no URL handler)"
        return attrs

    # ------------------------------------------------------------------
    # Standard media_player actions
    # ------------------------------------------------------------------

    async def async_media_play(self) -> None:
        """Open the Twitch app."""
        await self._manager.async_launch_twitch()

    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Open Twitch. media_id is treated as a channel name (stored, not navigated).

        Usage from HA service call:
            service: media_player.play_media
            data:
              media_content_type: app
              media_content_id: xqc

        Note: Twitch's tvOS app does not support URL deep links, so the app
        opens to its home screen regardless of the channel name provided.
        The channel name is stored as an attribute for reference only.
        """
        channel = media_id.strip() if media_id else None
        await self._manager.async_launch_twitch(channel)

    async def async_media_pause(self) -> None:
        if self._manager.atv:
            await self._manager.atv.remote_control.pause()

    async def async_media_stop(self) -> None:
        """Stop and clear optimistic state."""
        if self._manager.atv:
            await self._manager.atv.remote_control.stop()
        self._launched_at = None
        self.async_write_ha_state()
