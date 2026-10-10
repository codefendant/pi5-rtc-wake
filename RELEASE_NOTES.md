# Pi 5 Wake & Sleep 0.7.0-rc.1 — phone messages preview

Receive optional wake and status messages through the Home Assistant Companion app. Every message includes Pi uptime and the next shutdown and wake times. Add readings Home Assistant already monitors, using a separate Messages screen.

[Install in Home Assistant](https://my.home-assistant.io/redirect/supervisor_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fcodefendant%2Fpi5-rtc-wake) · [Phone setup](https://github.com/codefendant/pi5-rtc-wake/blob/main/PHONE_MESSAGES.md)

## New behavior

- Discover Companion app phones using current notify entities or legacy mobile-app actions. Choose an explicit phone; broadcast targets are excluded.
- Suggest native battery, temperature, NUT UPS, weather, security/maintenance, and energy/power readings. Search by name/area/type and choose up to twelve fields. Hidden, disabled, and configuration entities are excluded.
- Preview a draft without sending, save settings, and confirm Send status now. Automatic wake messages start off and begin with the next Pi host boot.
- Wait for startup/readings, label missing or old-boot values, and persist an attempt before sending so app restarts and uncertain replies do not cause duplicate automatic pushes.
- Keep phone network work in a separate worker so delivery cannot delay RTC/UPS protection.
- Preserve existing schema-6 Calendar, UPS, wake-test, and outage settings in schema 7. All future shutdown/wake dates still belong to Home Assistant Calendar.

## Setup and updates

Update the same installed app, reload its Web UI, and open **Messages → Find phones and readings**. Install/open the Companion app on your phone and allow notifications if it is not already connected. Choose a phone, optionally select readings, preview, save, and test with **Send status now**. Enable **Send a message after this Pi starts** separately for the next Pi boot.

Phone delivery uses the Companion app's existing local or Apple/Google push connection. **Accepted by Home Assistant** is not proof of phone delivery. Exact dashboard priorities and the Energy dashboard's calculated daily totals are not copied; choose an existing daily energy sensor for today's usage.

## Verification and preview limits

The expanded automated suite passes **301 simulated backend tests**, including 42 phone cases, plus DOM checks locally. Browser, arm64-build, and anonymous-image checks gate publication. The browser flow uses simulated phones only. New real-phone delivery and an actual RTC-wake message still need confirmation. The maintainer's earlier Pi test applies to 0.6.0-rc.1.

Home Assistant is unavailable while the Pi is off. RTC wake needs continuous main power; the RTC battery keeps time but cannot boot the Pi. UPS retries remain conditional on fresh reserve, and a final emergency shutdown has no verified timed wake. This release does not control UPS outputs or provide a complete NUT shutdown handoff. See [VALIDATION.md](https://github.com/codefendant/pi5-rtc-wake/blob/main/VALIDATION.md) and [ACCEPTANCE.md](https://github.com/codefendant/pi5-rtc-wake/blob/main/ACCEPTANCE.md).
