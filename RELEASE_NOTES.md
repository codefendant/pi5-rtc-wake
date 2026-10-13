# Pi 5 Wake & Sleep 0.10.0 — Public Preview

**Home Assistant, on your schedule.** Schedule shutdown and automatic RTC wake for the Raspberry Pi 5 running Home Assistant OS, send useful phone updates, and manage everything from an editable Home Assistant dashboard.

This formal public preview packages the behavior tested in **0.10.0-rc.6**. It includes guided setup, the compact Pi status card, native Calendar dates and repeats, optional Network UPS Tools (NUT) monitoring/protection, phone status messages, native Assist tools, and Wake other devices using Home Assistant Wake on LAN buttons. Add personal pictures, graphs, and other cards around the Pi cards.

The public introduction now uses the approved use-case artwork and a current dashboard example. Installation and update guides are current, and simple bug-report and suggestion forms are available.

## Install through Home Assistant

[**Add to Home Assistant**](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fcodefendant%2Fpi5-rtc-wake), confirm the repository, and install **Pi 5 Wake & Sleep** from the app store. Turn **Protection mode off** before starting, then follow [INSTALL.md](INSTALL.md). Use Home Assistant OS 18+ and Core 2026.10+ on a Raspberry Pi 5. No terminal, YAML, personal token, or separate dashboard-card download is needed.

The first sleep and wake test makes Home Assistant unavailable for roughly ten minutes plus startup time. Main input power must remain connected for RTC wake. The RTC battery keeps time and cannot power the Pi.

## Update your existing installation

1. Update the **same installed app** to **0.10.0**, then **Stop → Start**.
2. Open **Web UI → Maintenance and connection repair → Update / reconnect dashboard** and confirm.
3. Restart **Home Assistant** when requested, then refresh the browser.
4. Check your Calendar selection, feature preferences, and personal cards.

Schema 11, Calendar dates, settings, personal cards, and valid wake-test evidence are retained. No new wake test is required solely for this release. Keep Protection mode off; do not uninstall the app or delete the dashboard to update. See [UPDATE.md](UPDATE.md).

## Preview validation and limits

The maintainer reports successful repeated fresh installs after deleting the app and dashboard on their Pi 5, alongside earlier successful wake and feature tests. The tested baseline passes **418 simulated backend tests**, browser checks, actual Home Assistant Core 2026.10.1 API checks, and arm64 build/public-image checks. This release goes through those gates again; [VALIDATION.md](VALIDATION.md) records the exact publication evidence.

This is a public preview, with the app still experimental. Independent novice installation, broader boot-device testing, and a physical in-place update remain later validation work. Automated Pi, UPS, and phone operations are simulated; they do not establish unattended long-outage recovery on every UPS.

UPS retries need sufficient reserve and continuous input power. This app does not switch UPS output or provide a complete NUT shutdown handoff. Read [UPS_RECOVERY.md](UPS_RECOVERY.md) before enabling protection. **Keep awake** suspends every shutdown/reboot from this app, including emergency UPS shutdowns, until resumed.

## Help improve the preview

[Report a problem](https://github.com/codefendant/pi5-rtc-wake/issues/new?template=bug_report.yml) · [Suggest an improvement](https://github.com/codefendant/pi5-rtc-wake/issues/new?template=feature_request.yml) · [Help and support details](SUPPORT.md)

Installation and everyday usability feedback are especially welcome. MIT licensed.
