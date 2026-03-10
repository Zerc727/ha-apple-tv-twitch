# Apple TV Twitch — Home Assistant Custom Integration

A Home Assistant custom integration that adds Twitch control to your Apple TV. It piggybacks on the built-in `apple_tv` config entry (no re-pairing required) and provides a service + entity for opening Twitch from HA automations and dashboards.

> **Tested on:** Apple TV 4K (gen 3) running tvOS 26.3

---

## What Works / What Doesn't

| Feature | Status | Notes |
|---|---|---|
| Open Twitch app | ✅ Works | Launches to Twitch home screen |
| Deep link to specific channel | ❌ Not supported | Twitch tvOS app rejects URL schemes |
| Detect if Twitch is currently active | ❌ Not supported | MRP protocol removed in tvOS 16+ |
| Reading channel/playing metadata | ❌ Not supported | Twitch exposes nothing via Companion |

The primary use case is **opening Twitch from HA automations or a dashboard button**, e.g. "When I sit on the couch, open Twitch."

---

## Prerequisites

1. **Home Assistant Apple TV integration** must already be set up and working.
   Settings → Integrations → Apple TV
2. The **Companion protocol** must be paired in that integration (required for app launching).

---

## Installation

### Via HACS (Recommended)

1. Open HACS → Integrations → ⋮ menu → **Custom repositories**
2. Add: `https://github.com/Zerc727/ha-apple-tv-twitch` — Category: **Integration**
3. Click **Download** on "Apple TV Twitch"
4. Restart Home Assistant

### Manual Installation

1. Copy `custom_components/apple_tv_twitch/` into your HA `config/custom_components/` directory
2. Restart Home Assistant

---

## Configuration

1. Settings → Integrations → **Add Integration** → search "Apple TV Twitch"
2. Select your Apple TV device from the dropdown
3. Done — no PIN or re-pairing needed

---

## Usage

### Entity

A `media_player.apple_tv_twitch` entity is created per device.

| State  | Meaning                              |
|--------|--------------------------------------|
| `off`  | Not connected to Apple TV            |
| `idle` | Connected (Twitch may or may not be open — detection not possible on modern tvOS) |

Pressing **Play** on the entity card opens the Twitch app.

### Service: `apple_tv_twitch.play_channel`

Opens the Twitch app on the Apple TV.

```yaml
service: apple_tv_twitch.play_channel
data:
  channel_name: xqc   # accepted but currently ignored — see Known Limitations
```

### Automation Example

```yaml
automation:
  - alias: "Open Twitch when I get home"
    trigger:
      - platform: state
        entity_id: person.me
        to: home
    action:
      - service: apple_tv_twitch.play_channel
        data:
          channel_name: xqc
```

### Dashboard Button

```yaml
type: button
name: Open Twitch
tap_action:
  action: call-service
  service: apple_tv_twitch.play_channel
  data:
    channel_name: ""
icon: mdi:twitch
```

---

## Diagnostic Script

Run this with Twitch open on your Apple TV to inspect raw pyatv output:

```bash
pip install pyatv
python diagnostic.py <apple_tv_ip> [companion_credentials]
```

Companion credentials can be found in your HA config under `.storage/core.config_entries` in the `apple_tv` entry's `credentials` dict.

---

## Known Limitations

### No channel deep links
Twitch's tvOS app does not register URL scheme handlers that the Companion protocol can invoke. Tested URL formats that all fail:
- `twitch://stream/<channel>`
- `twitch://channel/<channel>`
- `twitch://live/<channel>`
- `https://www.twitch.tv/<channel>`

The `channel_name` field in `play_channel` is kept in the API for future compatibility in case Twitch ever adds URL support.

### No active app detection
tvOS 16+ removed the MRP protocol. `metadata.app` (current foreground app) is only available via MRP. The Companion protocol, which replaced MRP on modern tvOS, does not expose current app info. Entity state will always show `idle` when connected, regardless of what's actually on screen.

### No metadata
Twitch does not implement the metadata API for tvOS. Title, channel, and playback state are all unavailable.

---

## Troubleshooting

- **"No Apple TV integrations found"**: Set up the built-in Apple TV integration first.
- **Service does nothing**: Ensure the Companion protocol is enabled/paired in the Apple TV integration settings.
- **Entity shows `off`**: The integration can't connect to the Apple TV — check your network and HA logs.

---

## Contributing

Issues and PRs welcome at [github.com/Zerc727/ha-apple-tv-twitch](https://github.com/Zerc727/ha-apple-tv-twitch).
