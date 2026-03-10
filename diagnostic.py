"""
Diagnostic script for Apple TV Twitch integration.

Run this while Twitch is open on your Apple TV to discover:
  - Twitch's bundle ID (TWITCH_BUNDLE_ID constant)
  - Whether content_identifier or any Playing field contains channel info

Usage:
    python diagnostic.py <apple_tv_ip>

Requires pyatv:
    pip install pyatv
"""

import asyncio
import sys


async def run(ip: str) -> None:
    try:
        import pyatv
    except ImportError:
        print("ERROR: pyatv not installed. Run: pip install pyatv")
        sys.exit(1)

    print(f"\n=== Scanning for Apple TV at {ip} ===\n")
    results = await pyatv.scan(hosts=[ip], timeout=5)

    if not results:
        print("ERROR: No Apple TV found at that address.")
        sys.exit(1)

    conf = results[0]
    print(f"Found: {conf.name}")
    print(f"  Address:  {conf.address}")
    print(f"  Services: {[str(s.protocol) for s in conf.services]}\n")

    print("=== Connecting (no credentials required for read) ===\n")
    loop = asyncio.get_event_loop()
    atv = await pyatv.connect(conf, loop)

    try:
        # --- Active app ---
        print("=== Active App ===")
        try:
            app = atv.metadata.app
            if app:
                print(f"  Bundle ID : {app.identifier}")
                print(f"  App Name  : {app.name}")
            else:
                print("  (no app info returned)")
        except Exception as e:
            print(f"  ERROR reading app: {e}")

        # --- Playing metadata ---
        print("\n=== Playing Metadata ===")
        try:
            playing = await atv.metadata.playing()
            fields = [
                "title",
                "artist",
                "album",
                "genre",
                "total_time",
                "position",
                "shuffle",
                "repeat",
                "media_type",
                "device_state",
                "content_identifier",
                "series_name",
                "season_number",
                "episode_number",
                "itunes_store_identifier",
            ]
            for field in fields:
                value = getattr(playing, field, "N/A")
                print(f"  {field:<30} = {value!r}")
        except Exception as e:
            print(f"  ERROR reading playing metadata: {e}")

        # --- Installed apps ---
        print("\n=== Installed Apps (all) ===")
        try:
            app_list = await atv.apps.app_list()
            for a in sorted(app_list, key=lambda x: x.name or ""):
                print(f"  {a.name:<40} {a.identifier}")
        except Exception as e:
            print(f"  ERROR reading app list: {e}")

    finally:
        atv.close()

    print("\n=== Done ===")
    print("\nNext steps:")
    print("  1. Note the Twitch bundle ID above.")
    print("  2. Update TWITCH_BUNDLE_ID in custom_components/apple_tv_twitch/__init__.py")
    print("  3. Inspect 'content_identifier' — update _extract_channel_name() in media_player.py")


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <apple_tv_ip>")
        sys.exit(1)
    asyncio.run(run(sys.argv[1]))


if __name__ == "__main__":
    main()
