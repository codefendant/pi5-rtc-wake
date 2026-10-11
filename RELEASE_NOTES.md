# Pi 5 Wake & Sleep 0.9.0-rc.1 — native dashboard preview

Pi Wake & Sleep now has a native Home Assistant dashboard with guided setup and individual Calendar, UPS, Messages, and Assist cards. **Edit dashboard** lets users add pictures, graphs, and other Home Assistant cards. Completed setup collapses into a small ready strip. Next shutdown/wake cards show local times and how long remains.

**Create Pi Sleep calendar** creates or reuses a native Local Calendar and selects it without enabling shutdowns. All dates and repeats remain in Home Assistant Calendar. Protection mode is checked before firmware/host access, with an Info-page link and highlighted switch illustration. Reboot Pi is red and requires confirmation.

## Update and open

1. Update the same installed app to **0.9.0-rc.1**, then **Stop → Start**.
2. Open its Web UI and select **Connect dashboard**.
3. Restart **Home Assistant** if requested, then add the discovered **Pi Wake & Sleep** integration in **Devices & services**. An existing Assist companion is reused.
4. Open **Pi Wake & Sleep** in the sidebar. The app's entry is now **Pi Wake & Sleep settings** for detailed settings.

[Dashboard guide](https://github.com/codefendant/pi5-rtc-wake/blob/main/DASHBOARD.md) · [Install](https://my.home-assistant.io/redirect/supervisor_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fcodefendant%2Fpi5-rtc-wake) · [Update guide](https://github.com/codefendant/pi5-rtc-wake/blob/main/UPDATE.md)

## Settings and boundaries

Dashboard setup does not enable AI, automatic messages, Calendar shutdowns, or UPS protection. Existing choices and a valid wake test are preserved through schema 8 → 9. Updates keep personal cards; restoring Pi cards keeps other cards. Nine read-only Pi entities support user-created cards and graphs. Native writes and power operations require a Home Assistant administrator and retain the backend checks and confirmations.

Detailed UPS commissioning remains in **Set up protection**. Physical RTC/UPS and final-shutdown recovery limits have not changed. This remains a preview pending observation of the new interface on the actual Pi and first-time-user setup.

Publication requires backend regressions, browser/mobile interaction checks, real Home Assistant 2026.10.1 Assist/dashboard/Calendar API checks, an arm64 build, and anonymous image/import verification. Simulated hardware services do not establish physical wake or phone delivery.
