"""Config flow for Apple TV Twitch integration."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from . import DOMAIN

BUILTIN_DOMAIN = "apple_tv"


class AppleTVTwitchConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Apple TV Twitch."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Handle the initial step — pick an existing Apple TV entry."""
        apple_tv_entries = self.hass.config_entries.async_entries(BUILTIN_DOMAIN)

        if not apple_tv_entries:
            return self.async_abort(reason="no_apple_tv_configured")

        options = {
            e.entry_id: f"{e.data.get('name', 'Unknown')} ({e.data.get('address', '?')})"
            for e in apple_tv_entries
        }

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {vol.Required("source_entry_id"): vol.In(options)}
                ),
            )

        source = self.hass.config_entries.async_get_entry(user_input["source_entry_id"])
        if source is None:
            return self.async_abort(reason="no_apple_tv_configured")

        await self.async_set_unique_id(source.entry_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=source.data.get("name", "Apple TV"),
            data={
                "address": source.data.get("address"),
                "name": source.data.get("name"),
                "credentials": source.data.get("credentials", {}),
                "source_entry_id": source.entry_id,
            },
        )
