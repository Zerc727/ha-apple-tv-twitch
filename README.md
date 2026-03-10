# Apple TV Twitch — Home Assistant Custom Integration

A standalone Home Assistant custom integration that adds Twitch awareness to your Apple TV. It piggybacks on the built-in `apple_tv` config entry (no re-pairing required), detects when Twitch is open, and provides a `play_channel` service for switching streams via deep link.

---

## Overview

The built-in HA `apple_tv` component uses the MRP protocol for metadata. Twitch on tvOS **does not** implement the MRP metadata API, so Home Assistant sees the device as "idle" while Twitch is running. This integration works around that by:

- Polling `atv.metadata.app` every 10 seconds to detect when Twitch is the active app.
- Exposing a `media_player` entity that reflects Twitch activity.
- Providing an `apple_tv_twitch.play_channel` service that launches a Twitch channel via the `twitch://stream/<channel>` deep link using the Companion protocol.

---

## Prerequisites

1. **Home Assistant Apple TV integration** must already be set up and working.
   Settings → Integrations → Apple TV
2. The **Companion protocol** must be paired in that integration (required for `launch_app`).
3. `pyatv` 0.17.0 is listed as a requirement and will be installed automatically by HA.

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

| State     | Meaning                                  |
|-----------|------------------------------------------|
| `off`     | Not connected to Apple TV               |
| `playing` | Twitch is the active foreground app     |
| `idle`    | Connected, but Twitch is not active     |

`media_title` shows the channel name when available (depends on `content_identifier` — see Known Limitations).

### Service: `apple_tv_twitch.play_channel`

Launches a Twitch live stream on the Apple TV.

```yaml
service: apple_tv_twitch.play_channel
data:
  channel_name: xqc
```

No URL needed — just the channel name (e.g. `xqc`, `shroud`, `pokimane`).

### Automation Example

```yaml
automation:
  - alias: "Start xqc stream on Apple TV"
    trigger:
      - platform: state
        entity_id: input_button.watch_xqc
    action:
      - service: apple_tv_twitch.play_channel
        data:
          channel_name: xqc
```

---

## Diagnostic Script

Before setting up the integration (or for debugging), run the included diagnostic script **while Twitch is open on your Apple TV**:

```bash
pip install pyatv
python diagnostic.py <apple_tv_ip>
```

This prints:
- The active app's bundle ID (to confirm `TWITCH_BUNDLE_ID` is correct)
- All `Playing` metadata fields including `content_identifier`
- The full list of installed apps and their bundle IDs

If the bundle ID printed differs from `tv.twitch.live.tv`, open a GitHub issue or update `TWITCH_BUNDLE_ID` in `__init__.py`.

---

## Known Limitations

- **No rich metadata**: Twitch does not expose channel info via the MRP protocol. `media_title` may show "Twitch" instead of the channel name, depending on what `content_identifier` contains (determined at runtime — see diagnostic script).
- **10-second detection lag**: App detection relies on polling since Twitch doesn't fire push updates on launch. State changes within ~10 seconds.
- **Companion protocol required**: The `play_channel` service uses `launch_app`, which requires the Companion protocol to be paired in the Apple TV integration.

---

## Troubleshooting

- **"No Apple TV integrations found"**: Set up the built-in Apple TV integration first.
- **`play_channel` does nothing**: Ensure the Companion protocol is enabled/paired in the Apple TV integration settings.
- **Wrong bundle ID**: Run `diagnostic.py` with Twitch open and open a GitHub issue with the output.

---

## Contributing

Issues and PRs welcome at [github.com/Zerc727/ha-apple-tv-twitch](https://github.com/Zerc727/ha-apple-tv-twitch).
