# Pi 5 Wake & Sleep 0.9.0-rc.3 — Keep awake and dashboard fixes

**Keep awake** now suspends every shutdown and reboot from this app, including future Calendar shutdowns, UPS retries, emergency low-battery UPS shutdowns, wake tests, and reviewed AI power operations. It cancels an unsubmitted countdown and stays on until you select **Resume shutdowns**, including after an app restart. The **Pi status power icon** toggles the same switch with confirmation. An amber state explains that UPS shutdown protection is suspended.

Resume restores your saved choices without enabling previously disabled features. Calendar dates, wake-test evidence, UPS policy, phones, AI settings, and personal cards are kept. Monitoring, messages, and status access continue. A shutdown already submitted to Home Assistant, or independently issued by NUT or another controller, cannot be cancelled by this app.

- Activity, message preview, Pi checks, NUT readings, and Assist dropdowns stay open during refresh until you close them.
- Select a Calendar item to open Home Assistant's native Calendar/event view, then select **Edit**. Home Assistant handles recurrence and permissions. **Open Calendar** remains available if the shortcut cannot load.
- The UPS card can display verified Battery runtime while protection is off. It uses the saved sensor or one registry-identified runtime measurement for this UPS. Disabled, missing, unavailable, and stale readings give different next actions instead of waiting indefinitely.
- Phone and Assist status explain when Keep awake is on.

## Update the existing app and cards

1. Update the same installed app to **0.9.0-rc.3**, then **Stop → Start**.
2. Open its Web UI and select **Connect dashboard** to update the companion and cards.
3. Restart **Home Assistant** if requested, then refresh your browser and open **Pi Wake & Sleep**.

Existing installations start with Keep awake **off**; no power feature is silently enabled. Your personal dashboard layout is preserved. Another physical wake test and **Restore default Pi cards** are not needed for this update.

[Dashboard guide](https://github.com/codefendant/pi5-rtc-wake/blob/main/DASHBOARD.md) · [Update guide](https://github.com/codefendant/pi5-rtc-wake/blob/main/UPDATE.md)

Publication requires backend regressions, Chromium desktop/phone checks, actual Home Assistant 2026.10.1 interface checks, an arm64 build, and anonymous image/import verification. Automated hardware, phone services, and the browser Calendar bridge are simulated; actual Core APIs are checked separately. This remains a preview.
