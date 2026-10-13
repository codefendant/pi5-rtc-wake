# Pi 5 Wake & Sleep — Public Preview

Home Assistant, on your schedule.

[**Visit the Pi Wake & Sleep website**](https://pi-wake-sleep.humblejam3.chatgpt.site/) for the introduction, examples, and Add to Home Assistant button.

Pi 5 Wake & Sleep lets the Raspberry Pi 5 running Home Assistant OS shut down on a schedule and boot again using its built-in RTC. Set dates and repeats in Home Assistant Calendar, then manage everyday tasks from an editable dashboard.

It is useful for an RV, cabin, battery/solar setup, or a remote installation that needs to check in at selected times. Send your phone Pi uptime, next shutdown/wake times, and existing readings such as battery levels and temperatures. Select Keep awake when you need time to connect and work, then resume your saved shutdown schedule.

Optional cards work with Network UPS Tools (NUT), your existing Home Assistant Assist integration, and Wake on LAN buttons for other compatible devices. Add your own pictures, graphs, and other cards around them.

Install **Pi 5 Wake & Sleep** through the Home Assistant app store: [Add to Home Assistant](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fcodefendant%2Fpi5-rtc-wake). Turn Protection mode off before starting and follow the guided setup. Requires Raspberry Pi 5, Home Assistant OS 18+, Core 2026.10+, and continuous main input power for RTC wake.

Home Assistant and its automations are unavailable while the Pi sleeps. UPS retry recovery is conditional; UPS output-off/return control is outside this release.

**0.10.0 is a public preview**, tested by the maintainer on a Pi 5, with automated backend, browser, native Home Assistant, and public-image checks. Feedback on installation and everyday use is welcome.

[Website](https://pi-wake-sleep.humblejam3.chatgpt.site/) · [Project and screenshots](https://github.com/codefendant/pi5-rtc-wake) · [Installation guide](https://github.com/codefendant/pi5-rtc-wake/blob/main/INSTALL.md) · [Preview release](https://github.com/codefendant/pi5-rtc-wake/releases/tag/v0.10.0) · [Report a problem or suggest an improvement](https://github.com/codefendant/pi5-rtc-wake/issues/new/choose)

MIT licensed.

---

This announcement is prepared for the maintainer to post. No community post or invitation is sent by the release process.
