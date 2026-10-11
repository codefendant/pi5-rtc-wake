# Pi 5 Wake & Sleep 0.10.0-rc.1 — Wake other devices

The optional **Wake other devices** dashboard card reuses Home Assistant's existing Wake on LAN buttons. Choose compatible computers, optionally associate a Ping sensor with each, save, and test **Wake selected**. Automatic waking starts **off**.

- Wake manually, after a recorded Calendar RTC wake, or after every Pi boot.
- Optionally require fresh UPS readings showing utility power before waking other loads.
- Show each device's result: requested, checking, reachable, or not confirmed. Ping proves network reachability at that time, not application readiness.
- Add devices and online checks through Home Assistant's integration screens. Device selection and sending require an administrator.
- Preserve unsaved settings and expanded details during dashboard refreshes. Add the new card once without replacing personal cards or the existing layout.
- Claim requests on disk before sending; do not repeat uncertain automatic requests after an app restart. Device requests run separately from Pi/UPS power control.

Calendar remains the date store. Existing RTC setup, Pi shutdown policy, Keep awake, UPS protection, Messages, and Assist behavior are retained. Saving device settings never sends a packet or starts automation on the current boot.

## Update your existing installation

1. Update the same installed app to **0.10.0-rc.1**, then **Stop → Start**.
2. Open **Web UI → Maintenance and connection repair → Update / reconnect dashboard** and confirm.
3. Restart **Home Assistant** if requested, refresh your browser, and open **Pi Wake & Sleep**.
4. Select **Wake other devices → Choose devices**. Select your Wake on LAN buttons and matching Ping sensors if wanted. Choose a UPS or turn off **Only wake on utility power**. Save and test **Wake selected**, then enable automatic waking if wanted.

Do not uninstall or restore default cards. Schema 11 preserves existing settings, dates, wake evidence, and personal cards. A new Pi wake test is needed only when firmware or wake settings changed.

## Verification and scope

400 simulated backend cases pass locally, with JavaScript syntax and maintenance UI logic checks. Publication also requires Chromium desktop/mobile checks, actual Home Assistant 2026.10.1 registry/button/template and admin-boundary checks, an arm64 image build, and anonymous public image/import verification. Network packet sending is patched in the real Core check; no physical computer was woken during automated tests.

This remains a public preview. Test the chosen computers and Ping sensors on your own network before relying on automatic waking. This feature adds no remote shutdown, PoE switching, or external RTC support. See [WAKE_DEVICES.md](https://github.com/codefendant/pi5-rtc-wake/blob/main/WAKE_DEVICES.md), [UPDATE.md](https://github.com/codefendant/pi5-rtc-wake/blob/main/UPDATE.md), and [VALIDATION.md](https://github.com/codefendant/pi5-rtc-wake/blob/main/VALIDATION.md).
