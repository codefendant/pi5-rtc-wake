# Pi 5 Wake & Sleep 0.9.0-rc.4 — Dashboard interface cleanup

Pi Wake & Sleep is now the main place to manage every feature. The add-on Web UI is **Setup & maintenance**, with first-time dashboard connection, companion updates/reconnection, and support diagnostics. It no longer duplicates Calendar, UPS, Messages, Assist, or everyday power controls. Working connections hide installation instructions; a saved installation choice alone is not treated as proof of a live connection.

- **UPS protection is on the dashboard:** runtime selection, all timings/thresholds, shutdown ownership, supply/final-stop acknowledgements, enable/disable confirmations, the conditional retry table, and pause-timed-retries control.
- **UPS details remain available:** active readings, disabled NUT readings, refresh, and the native UPS device link.
- **Phone setup opens after discovery:** choose a phone, show suggested/all readings or a category, preview a draft without sending, and refresh discovery while preserving unsaved choices.
- **Completed Pi setup stays compact:** Review setup and Setup & maintenance remain accessible. User-opened details and unsaved forms retain their state during refreshes.

Scheduling, RTC checks, UPS shutdown policy, phone delivery, and reviewed AI actions retain their existing behavior. **Keep awake**, Calendar dates, feature choices, qualified wake evidence, outage records, and personal dashboard cards are kept. No optional feature is enabled automatically. Calendar remains the only date store.

## Update your existing installation

1. Update the same installed app to **0.9.0-rc.4**, then **Stop → Start**.
2. Select **Open Web UI → Maintenance and connection repair → Update / reconnect dashboard**, and confirm.
3. Restart **Home Assistant** if requested, then refresh your browser and open **Pi Wake & Sleep** in the sidebar. An existing integration is reused; add the discovered integration in Devices & services only if this is the first connection.
4. The optional app sidebar entry is renamed **Pi setup & maintenance**. You can turn off its **Show in sidebar** option once the dashboard works; Open Web UI and the dashboard setup area keep it accessible.

Do not uninstall or restore default cards for this update. A new physical wake test is needed only when firmware or wake settings changed.

## Validation and scope

368 simulated backend tests pass locally. Publication requires the Chromium installation/dashboard/mobile suites, real Home Assistant 2026.10.1 API checks, arm64 image build, and anonymous public image/import checks. The browser's Home Assistant chrome, Calendar focus bridge, Pi/UPS services, and phone are simulated. A new user still needs to try the complete installation/activation path on real HAOS before the beginner acceptance requirement can be declared complete.

This remains a public preview. Existing physical UPS output-return and independent-controller limits apply; this interface cleanup adds no UPS output command or new shutdown policy. See [INSTALL.md](https://github.com/codefendant/pi5-rtc-wake/blob/main/INSTALL.md), [DASHBOARD.md](https://github.com/codefendant/pi5-rtc-wake/blob/main/DASHBOARD.md), and [VALIDATION.md](https://github.com/codefendant/pi5-rtc-wake/blob/main/VALIDATION.md).
