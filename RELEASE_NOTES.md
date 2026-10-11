# Pi 5 Wake & Sleep 0.9.0-rc.2 — dashboard navigation fix

Expanded setup now has **Back to dashboard**. Completed setup collapses to the ready strip. Leaving unfinished setup shows **Pi setup needs attention** and keeps all wake and power checks enforced.

With no shutdown countdown, Pi controls offer **Pause calendar** and **Resume calendar**. Pause keeps every Calendar date and does not change emergency UPS protection. Resume requires a review and confirmation. **Keep awake** remains available during an ordinary shutdown countdown and cancels that shutdown only. Emergency shutdowns cannot be cancelled here.

## Update the existing app and cards

1. In Home Assistant, update the same installed app to **0.9.0-rc.2**, then **Stop → Start**.
2. Open the app's Web UI and select **Connect dashboard** to update the bundled companion and cards.
3. Restart **Home Assistant** if requested, then refresh your browser and open **Pi Wake & Sleep**.

Your Calendar, UPS, phone, Assist choices, valid wake-test result, and personal dashboard cards are preserved. This fix does not require another physical wake test. **Restore default Pi cards is not needed.**

[Dashboard guide](https://github.com/codefendant/pi5-rtc-wake/blob/main/DASHBOARD.md) · [Update guide](https://github.com/codefendant/pi5-rtc-wake/blob/main/UPDATE.md)

Publication requires backend regressions, Chromium desktop/phone checks, actual Home Assistant 2026.10.1 interface checks, an arm64 build, and anonymous image/import verification. Automated hardware and phone services are simulated. This remains a preview.
