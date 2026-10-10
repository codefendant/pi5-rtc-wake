# 0.7.0-rc.1

- Add a separate Messages screen for optional Companion app wake/status notifications. Discover current phone notify entities and legacy mobile-app actions; require an explicit phone choice.
- Include next shutdown, next wake, and actual host uptime. Explain paused/off/no-event schedules, conditional UPS recovery, and final stops without promising a wake.
- Discover useful existing readings from native entity/device/area metadata, with search, visibility filtering, weather/climate fields, and up to twelve explicitly selected readings. Preview drafts without sending and confirm manual status delivery.
- Automatic messages start off. Wait for startup/readings, record an attempt before sending, and avoid duplicates on app restart or uncertain delivery. Keep phone network work separate from RTC/UPS control.
- Preserve schema 6 Calendar/UPS/wake settings in schema 7 with phone messages off. Add 42 backend regression cases (301 total) and DOM/browser phone flows using simulated phones. Actual Companion app delivery remains to be checked.

# 0.6.0-rc.1

- Organize the app into Overview, Calendar, UPS, and Setup. Open Overview after successful setup; show setup again when checks or the wake test need attention. Keep detailed forms/readings collapsed and retain unsaved edits during status refreshes.
- List disabled sensors from the actual Home Assistant NUT entity registry and offer Enable for the selected UPS. Use the fixed Core WebSocket proxy, validate device/integration ownership, and explain reload/restart requirements. Do not change sensors during a known outage.
- Accept valid auxiliary NUT status flags, including OL TEST. Keep conflicting or untrusted status Unknown.
- Separate timed RTC retries from emergency low-battery protection. Cancelling/pausing a retry, failed RTC checks, and changing Calendar no longer disable commissioned emergency protection. Require explicit confirmation to turn it off; allow an emergency-only policy without RTC/Calendar readiness.
- Honor fresh low-battery/forced-shutdown signals even without runtime data. Discount aging runtime observations and retain the last observed reserve through app restarts. Critical reserve skips optional Calendar calls and countdowns. Emergency stops preserve unrelated alarms and promise no timed wake.
- Show conditional retry runtime requirements beside the settings: 24/39/69 minutes with the defaults. Explain why a 30-minute threshold normally cannot fund the full sequence at unchanged load.
- Check the community NUT app's Host shutdown option without changing it. Conflicts/unknown ownership pause RTC retries; require ownership review and confirmation that NUT was restarted after option changes. No complete NUT shutdown handoff or UPS output-return executor is implemented.
- Migrate to schema 6 while preserving selections, settings, and wake evidence. An enabled older UPS policy requires ownership review before automatic protection resumes. Add 39 regression cases (259 total) and DOM interaction checks; real browser, HAOS, and complete UPS-cycle acceptance remain outstanding.

# 0.5.0-rc.1

- Add opt-in graceful UPS host shutdown and bounded RTC retries with increasing intervals. Keep HA on until runtime threshold by default; early battery-saving shutdown is optional.
- Write/read back retry dates in the existing Calendar before arming; keep generated power records out of ordinary scheduled execution.
- Require explicit remaining-runtime selection for NUT, confirmed supply/wake evidence, writable Calendar, and final-stop acknowledgement. Hooks can provide typed runtime.
- Preserve outage claims/attempt counts across boots, require fresh post-boot readings and stable utility power, pause cancelled/interrupted attempts, and preserve alarms after ambiguous shutdown.
- Protect critical reserve without waiting for nonessential Calendar/notification calls or countdowns; final stops do not promise a timed wake. No UPS output commands are sent.
- Migrate settings to schema 5, preserve existing Calendar/NUT/test settings, and start new control off. Include UPS_RECOVERY.md and expanded failure-path tests.

# 0.4.0-rc.1

- Make Home Assistant Calendar the only source of scheduled dates. Remove the daily scheduler and manual daily-wake action from the app. Keep the upcoming summary and move Open Calendar into a prominent button.
- Migrate selected calendars, preferences, test confirmation, and occurrence claims to schema 4. Strip duplicate daily fields. Pause older daily schedules and show their previous times for migration through Home Assistant's event editor.
- Add read-only discovery of actual Home Assistant NUT devices, grouped by device ID, using raw Status data and typed battery measurements. Do not guess remaining runtime from a seconds unit or an entity name.
- Add version-1 power-hook discovery through a sensor's rtc_wake_power attributes. Validate observation/report freshness, status, and typed readings. Do not load arbitrary plugin code or accept control claims.
- Add explicit source selection, opt-in scoped power notifications, reported readings/settings, stale-data handling, and persistent monitor preferences.
- Keep automatic UPS shutdown, UPS output control, and recovery retries disabled. Include the developer hook contract and a verified recovery design in UPS_HOOKS.md.

# 0.3.0-rc.1

- Make Reboot Pi and its confirmation button red. Show a scoped reboot reminder in Home Assistant's persistent Notifications; clear it after successful post-reboot checks. Host-check failures retain a known reminder, and notification failures do not block daily scheduling.
- Show a Saved schedule list with shutdown, wake, repeat/source, time zone, status, and paired next times. Keep unsaved form edits separate from saved values.
- Add optional Home Assistant calendar scheduling. Read native expanded events, with start = shutdown and end = wake, and use Home Assistant's existing event and recurrence editor. Keep daily mode as the default; no custom calendar editor or recurrence engine is installed.
- Program the RTC with the exact absolute event end and re-read the calendar before arming and before shutdown. Invalid, all-day, overlapping, stale, changed, or unavailable periods keep the Pi on. Persist occurrence claims to prevent duplicate retries after cancellation or restart.
- Migrate existing daily settings and successful test evidence without resetting them. Add calendar setup links and plain instructions.
- The user reports the rc.4 ten-minute physical wake test succeeded. New calendar/API behavior still needs live Home Assistant testing. The Supervisor API does not provide generic app-created Settings repair issues; the reminder uses Notifications.

# 0.2.0-rc.4

- Add the missing `SYS_PTRACE` capability. Linux applies a ptrace access check to the host PID's namespace and root files; `SYS_ADMIN` and hardware access alone do not pass that check for a more privileged host process.
- On host-entry failure, show the three effective bridge capabilities in support details and logs. This distinguishes a missing applied permission from a remaining access denial without exposing raw process metadata.
- Preserve the app identity, settings format, host-operation limits, and firmware preparation guards. No firmware version update or automatic preparation was added.
- The rc.3 log confirms access denied before helper startup. This fixes a matching permission defect; physical HAOS confirmation is still needed.

# 0.2.0-rc.3

- Correct host directory selection to happen after entering the host mount namespace and root. Use the explicit util-linux nsenter path, install its package directly, and require the needed option at image build time.
- Report the failed host step, error type, and error codes in a collapsed **Details for support** section and app logs. Catch helper import errors as well as command failures. Preserve both inner-command and helper exit codes.
- Give access-denied guidance only for an access-denied failure. Missing/incompatible app tools and firmware-check failures have their own messages.
- Give the host helper a minimal environment and discard raw output and unknown diagnostic fields. Keep preparation, wake testing, and scheduling blocked when host verification fails.
- Preserve the existing app slug, settings format, and original firmware-preparation guards. No automatic retry or firmware version upgrade was added.
- The user's rc.2 log cannot establish the original cause; rc.3 needs checking on the Pi.

# 0.2.0-rc.2

- Fix Pi 5 detection to use Home Assistant OS's `rpi5-64` board ID. The previous candidate compared the board with the separate `raspberrypi5-64` machine ID and incorrectly disabled preparation.
- Record the detected board, OS version, and the plain-language reason for a failed check in the app logs. No tokens or credentials are logged.
- Add regression coverage using the HAOS board ID and retain refusal of unsupported or unknown boards.
- Keep the app slug and saved-settings format unchanged for an in-place update.

# 0.2.0-rc.1

- Replace separate YAML, API-token setup, helper entities, and dashboard installation with a single Home Assistant Ingress screen.
- Detect Home Assistant OS 18+, Pi 5, RTC alignment, native firmware status, and running wake settings.
- Add guided preparation that backs up boot configuration, pins the current firmware version, preserves boot order, and verifies a new boot.
- Add a ten-minute physical wake test with host-boot evidence and user confirmation.
- Store daily scheduling settings atomically and preserve them across app updates.
- Pause scheduling when firmware or boot settings change; protect unsupported future settings.
- Add plain-language errors, cancellable shutdown countdowns, and fail-closed RTC checks.
- Keep wake alarms after ambiguous shutdown-request failures.
- Add repository metadata preparation and an aarch64 image workflow. Publication and physical validation are still pending.
