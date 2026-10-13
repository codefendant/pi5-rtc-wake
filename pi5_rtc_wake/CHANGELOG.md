## 0.10.0-rc.6

- Fill the native two- and three-column sections with their generated cards, removing the reserved empty middle column and widening the Pi summary.
- Repair only unchanged starter widths; preserve custom sizes, titles, mixed/personal cards, and later explicit resizing through an internal layout marker.
- Render both grid levels from generated configuration in browser checks, and verify section fill and real Core upgrade/configuration retention. Keep all power and scheduling behavior.

## 0.10.0-rc.5

- Consolidate everyday Pi status, uptime, schedule times, Keep awake, and Settings into one compact summary with the introduction page's Raspberry Pi artwork and Awake indicator.
- Move occasional setup, maintenance, and confirmed red Reboot Pi controls into Settings; retain first-run/problem guidance and shorter optional-card introductions.
- Combine only the five untouched earlier starter header sections, preserving personal cards, customized headers, other views, and settings; retain all individual card types.
- Use the installed companion version in dashboard resource URLs; keep phone edits, dropdown state, confirmations, scheduling, and UPS behavior.

## 0.10.0-rc.4

- Explain companion restart requirements through a Home Assistant notification immediately after installation/update; persist pending status across app restarts and clear after matching dashboard readiness.
- Add a native Settings → Repairs reminder for later updates once the new companion has loaded. The first install uses a notification because the companion is not running yet.
- Show phone choices as visible single-selection rows and highlight the chosen phone; rename discovery refresh and keep selected phones/readings when refreshing, including unavailable saved phones.
- Keep the existing power policy, ten-minute wake test, Calendar dates, phone delivery consent, valid wake evidence, and personal cards. No new physical wake test is required just for this update.

# 0.10.0-rc.3

- First-time Pi setup now explains the first sleep and wake cycle before the test button and again in its confirmation. Home Assistant and automations are unavailable for roughly ten minutes, plus startup time.
- Shows the armed wake time during the test countdown and explains how to confirm the automatic return and continue onboarding. Keeps the 15-minute manual-return guidance and the existing scheduling/UPS test notice.
- Retains the ten-minute alarm, 30-second countdown, power guards, saved settings, and existing wake qualification. No new wake test is needed for an ordinary update.

# 0.10.0-rc.2

- Prevent the fresh-install dashboard link from opening before the integration creates its dashboard. Highlight the required restart and Devices & services confirmation.
- Require matching loaded companion code before registering cards. Show failed setup checks in the Web UI, logs, and support details.
- Recheck dashboard readiness after an app restart while preserving personal cards and settings.
- Reduce repetitive OS-detection logging; hardware checks and power behavior are unchanged.

# 0.9.0-rc.4

- Make the native dashboard the main interface for every feature; reduce the app Web UI to Setup & maintenance and rename its optional sidebar shortcut.
- Move full UPS commissioning, conditional retry requirements, emergency-disable/enable confirmations, status/attempts, and pause-timed-retries into the UPS card. Retain active readings, disabled NUT sensors, refresh, and device links.
- Open phone settings automatically after discovery; add all/category readings, draft preview, and discovery refresh with unsaved choices retained.
- Hide connection instructions only with recent authenticated companion contact; retain repair, protection-mode guidance, diagnostics, and persistent support dropdowns. Point companion/Assist errors to the current repair screen.
- Preserve schema 10, every existing power-policy guard, Keep awake, Calendar dates, feature choices, qualified wake evidence, outage state, and personal cards. Add simulated backend connection and browser onboarding/settings regressions.

# 0.9.0-rc.3

- Make Keep awake persistently suspend every app shutdown and reboot, including Calendar dates, UPS retries, emergency UPS shutdowns, wake tests, and reviewed AI power operations. Resume shutdowns restores saved choices without erasing dates or wake evidence.
- Make the Pi status power icon toggle the same confirmed switch; show suspension clearly and preserve it across restarts and updates in schema 10.
- Keep activity, message preview, Pi checks, NUT readings, and Assist dropdowns open across status refreshes.
- Open listed Calendar occurrences in Home Assistant's native Calendar/event view, retaining an Open Calendar fallback.
- Display verified NUT runtime in monitoring mode without enabling shutdown protection. Explain disabled, missing, unavailable, and stale readings separately.
- Preserve submitted/uncertain power requests and their alarm; a shutdown already submitted or issued by another controller cannot be cancelled.
- Extend backend, browser, and actual Home Assistant API checks. Refresh bundled cards with Connect dashboard after updating.

# 0.9.0-rc.2

- Add Back to dashboard to expanded setup. Leaving unfinished setup shows a needs-attention strip and keeps power checks enforced.
- Show Pause calendar and Resume calendar in Pi controls when no shutdown countdown is running. Pausing keeps Calendar dates and emergency UPS protection; resuming requires review and confirmation.
- Keep awake cancels a running ordinary countdown. Emergency shutdowns remain protected; controls explain each state.
- Retain settings, wake evidence, and personal dashboard cards. Refresh the companion with Connect dashboard after updating.

# 0.9.0-rc.1

- Add native cards, visual card editors, and an editable starter dashboard; preserve user layouts on updates.
- Connect the dashboard without enabling AI; expose nine read-only Pi entities for other cards and graphs.
- Guide Protection mode before host inspection, collapse completed setup, and show next times with relative timing.
- Create/reuse a native Pi Sleep Local Calendar with scheduling off; retain Calendar as the only date store.
- Add Calendar/UPS/phone/Assist card setup, red confirmed reboot, and safe current-countdown cancellation.
- Restore Pi cards without removing other cards; retain schema-8 settings and wake evidence in schema 9.
- Extend browser and real Core 2026.10.1 API checks. Detailed UPS commissioning remains in linked app settings.

# 0.8.0-rc.2

- Fix Connect Assist failing with "Home Assistant's configuration folder is not available" by explicitly mapping the Core configuration folder to the installer's path. Supervisor's default mount is /homeassistant, while the installer expects /homeassistant_config.
- Show setup errors and their next action beside Connect Assist instead of leaving the initial "Not connected" prompt after a failed attempt.
- Check the published YAML mount against the installer in the actual Home Assistant CI check, before using simulated hardware. Add a missing-folder/reconnect regression and retain schema 8, Calendar, UPS, phone, wake-test, and Assist preferences.

# 0.8.0-rc.1

- Add an optional Assist section and a bundled Home Assistant companion using Core 2026.10's native LLM tool platform. Connect through screens and authenticated Supervisor discovery; no user token or YAML is needed.
- Report fresh Pi uptime, Calendar shutdown/wake dates, readiness, and selected UPS readings through the existing AI conversation agent, including local Ollama. Start with status only; change requests start off.
- Let enabled AI request single Calendar off periods, scheduling on/off, wake tests, and reboots for explicit approval in the app. Keep every approved date in native Calendar. Check/read back writes and do not duplicate uncertain requests.
- Allow ordinary current countdown cancellation while preserving emergency protection. AI cannot approve requests, confirm wake evidence, change firmware, or disable emergency protection.
- Install/update only owned companion files through Connect Assist. Add a private authenticated API with no published host port or approval endpoint. Mount the Core configuration folder for the fixed companion; preserve unrelated configuration.
- Preserve existing settings in schema 8 with AI access off. Add backend boundary/migration cases, browser connection/review flows, and real Home Assistant 2026.10.1 native platform/flow/tool checks using simulated hardware.

# 0.7.0-rc.2

- Explain Protection mode in the container-OS host-check error and give the complete Info-page Stop/off/Start/Check again sequence. Keep support details available if that does not restore access.
- Use the same sequence for access-denied errors and explain that normal RTC operation still needs Protection mode off. Firmware updates remain owned by Home Assistant; wake checks remain in place.
- Preserve all existing settings, wake-test evidence, permissions, firmware guards, Calendar behavior, UPS policy, and phone behavior. Add regression coverage for the reported error and Setup recovery.

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
