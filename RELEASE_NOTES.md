# Pi 5 Wake & Sleep 0.6.0-rc.1 — public preview

Schedule a safe shutdown and automatic RTC wake for the Raspberry Pi 5 that runs Home Assistant OS. Install and configure it through Home Assistant screens. Home Assistant Calendar owns all scheduled dates and repeating events.

[Install in Home Assistant](https://my.home-assistant.io/redirect/supervisor_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fcodefendant%2Fpi5-rtc-wake) · [Installation guide](https://github.com/codefendant/pi5-rtc-wake/blob/main/INSTALL.md)

## In this release

- Overview, Calendar, UPS, and Setup sections keep completed setup out of everyday use.
- Guided Pi checks, a red reboot control, a Home Assistant reboot notification, and a ten-minute wake test.
- Native Calendar editing, recurring dates, and an upcoming schedule summary. Event start means shutdown; event end means wake.
- NUT discovery accepts valid auxiliary flags such as `OL TEST`. Default-disabled NUT sensors can be enabled from the selected UPS page.
- Optional UPS notices, explicit runtime selection, conditional RTC retry intervals, and separate emergency low-battery protection.
- Cancelling a retry or failing an RTC check preserves commissioned emergency protection for the same UPS.
- Shutdown ownership review and settings migration for earlier versions.

The app maintainer reports that this build works on their Pi 5. The local suite passes 259 simulated backend tests and DOM interaction checks. See [VALIDATION.md](https://github.com/codefendant/pi5-rtc-wake/blob/main/VALIDATION.md) for the scope of validation and [ACCEPTANCE.md](https://github.com/codefendant/pi5-rtc-wake/blob/main/ACCEPTANCE.md) for remaining stable-release checks.

## Existing installations

Update the same installed app to retain settings. An enabled 0.5 UPS policy keeps its preferences but waits for shutdown-ownership review before automatic protection resumes. Moving from a local ZIP installation to the public repository creates a separate app installation; follow the migration instructions in INSTALL.md and stop the local app first.

## Preview limits

While the Pi is off, Home Assistant and its automations are unavailable. RTC wake needs continuous main power. The RTC battery keeps time; it cannot boot the Pi.

Default retries of 15, 30, and 60 minutes require at least 24, 39, and 69 minutes of estimated remaining runtime at each decision. The sequence is conditional. A final emergency shutdown has no verified timed wake.

This app does not control UPS outputs or implement a complete NUT shutdown handoff. Restored utility power does not restart a halted Pi if the UPS has continuously supplied its input. Long-outage output restoration and automatic restart need verification on the actual UPS before relying on unattended recovery.
