"""
Probe script: intercept ALL Companion protocol events and test undocumented commands.

Patches api.event_received to log every event the Apple TV sends, regardless of
whether pyatv has registered a listener for it.

Usage:
    python probe_companion.py <apple_tv_ip> <companion_credentials> [listen_seconds]

Example:
    python probe_companion.py 192.168.1.141 "aaa:bbb:ccc:ddd" 60
"""

import asyncio
import sys
from datetime import datetime


# Candidate request commands — "No request handler" means the command is unknown.
# An OK response means we found a supported command.
CANDIDATE_COMMANDS = [
    "FetchFrontmostApplicationEvent",
    "FetchActiveApplicationEvent",
    "FetchFocusedApplicationEvent",
    "FetchForegroundApplicationEvent",
    "FetchNowPlayingApplicationEvent",
    "FetchApplicationStateEvent",
    "FetchRunningApplicationsEvent",
    "GetFrontmostApplication",
    "GetActiveApplication",
    "GetFocusedApplication",
    "_fetchForegroundApp",
    "_fetchFocusedApp",
    "_getFocusedApp",
    "_getActiveApp",
    # Candidates based on Apple's private framework naming conventions
    "SBGetFrontmostApplication",
    "SpringBoardGetFocusedApp",
    "FBSGetFrontmostApplication",
    "FetchTopApplication",
    "GetNowPlayingApp",
    "FetchNowPlayingInfo",
]


async def run(ip: str, creds: str, listen_secs: int) -> None:
    try:
        import pyatv
        from pyatv.const import Protocol
    except ImportError:
        print("ERROR: pyatv not installed.")
        sys.exit(1)

    loop = asyncio.get_event_loop()

    print(f"\n=== Scanning {ip} ===")
    results = await pyatv.scan(hosts=[ip], timeout=5, loop=loop)
    if not results:
        print("ERROR: No device found.")
        sys.exit(1)

    conf = results[0]
    svc = conf.get_service(Protocol.Companion)
    if not svc:
        print("ERROR: No Companion service found.")
        sys.exit(1)

    conf.set_credentials(Protocol.Companion, creds)
    print(f"Connecting to {conf.name}...")
    atv = await pyatv.connect(conf, loop)

    companion_apps = atv.apps.get(Protocol.Companion)
    if companion_apps is None:
        print("ERROR: Companion apps interface not available.")
        atv.close()
        return

    api = companion_apps.api

    # ---------------------------------------------------------------
    # HOOK: Patch event_received to capture ALL incoming protocol events
    # ---------------------------------------------------------------
    all_events = []
    original_event_received = api.event_received

    def patched_event_received(event_name, data):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"  [{ts}] EVENT: {event_name!r:45s} data={data}")
        all_events.append((event_name, data))
        original_event_received(event_name, data)

    api.event_received = patched_event_received
    print("  Event intercept hook installed — ALL events will be printed.\n")

    # ---------------------------------------------------------------
    # 1. Probe request commands
    # ---------------------------------------------------------------
    print("=== Probing request commands ===")
    for cmd in CANDIDATE_COMMANDS:
        try:
            resp = await api._send_command(cmd, {})
            content = resp.get("_c", {})
            print(f"  *** OK ***  {cmd}")
            print(f"              Response: {content}")
        except Exception as e:
            short = str(e)[:100]
            print(f"  FAILED:    {cmd:<50s} {short}")

    # ---------------------------------------------------------------
    # 2. FetchAttentionState (known working command for reference)
    # ---------------------------------------------------------------
    print("\n=== FetchAttentionState (sanity check) ===")
    try:
        resp = await api._send_command("FetchAttentionState", {})
        print(f"  state = {resp.get('_c', {}).get('state')}  "
              f"(3=Awake, 1=Asleep, 2=Screensaver)")
    except Exception as e:
        print(f"  ERROR: {e}")

    # ---------------------------------------------------------------
    # 3. Listen for ALL push events
    # ---------------------------------------------------------------
    print(f"\n=== Listening for {listen_secs}s — DO THIS NOW: ===")
    print("  1. Open Twitch -> wait 3s")
    print("  2. Play a stream -> wait 3s")
    print("  3. Pause the stream -> wait 3s")
    print("  4. Switch to a different app -> wait 3s")
    print("  5. Come back to Twitch -> wait 3s")
    print("  Watching for any events the Apple TV pushes...\n")

    await asyncio.sleep(listen_secs)

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------
    print(f"\n=== Summary: {len(all_events)} total events received ===")
    by_name: dict = {}
    for name, data in all_events:
        by_name.setdefault(name, []).append(data)

    if by_name:
        print("\nEvent names seen:")
        for name, instances in sorted(by_name.items()):
            print(f"  {name!r:45s} x{len(instances)}")
            for d in instances[:2]:
                print(f"    {d}")
    else:
        print("  No events received — Apple TV did not push any data.")

    atv.close()


def main():
    if len(sys.argv) < 3:
        print(f"Usage: python {sys.argv[0]} <ip> <credentials> [seconds=60]")
        sys.exit(1)
    ip = sys.argv[1]
    creds = sys.argv[2]
    secs = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    asyncio.run(run(ip, creds, secs))


if __name__ == "__main__":
    main()
