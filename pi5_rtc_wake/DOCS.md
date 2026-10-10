# Getting started

This is a preview release. Calendar scheduling and automatic UPS protection start off. Timed RTC retries require a confirmed continuous supply path; every automatic protection policy requires reviewed shutdown ownership and acknowledgement of a final stop without a verified timed wake.

1. On this app's Info page turn off **Protection mode**, enable **Start on boot** and **Show in sidebar**, and start the app.
2. Open the Web UI. In **Setup**, follow the checks, preparation if needed, reboot, and ten-minute wake test. Confirm that Home Assistant returned by itself.
3. In **Calendar**, choose a dedicated Home Assistant **Local Calendar**, such as **Pi Sleep**. Use **Open Home Assistant Calendar** to enter all dates and repeats there.
4. Each timed event is an off period: **start = shutdown, end = wake**. For overnight operation choose the following day for the end. Turn off All day. Use periods from ten minutes to seven days without overlaps or touching events.
5. Save the calendar selection, review the upcoming list, then enable scheduling and save.

The app stores the calendar selection and display preferences. It does not have a separate daily scheduler. Dates and repeats stay in Home Assistant's Calendar. Changes appear within a minute; Check again refreshes immediately. Empty calendars are allowed: the Pi stays on until the next event.

The RTC is programmed before shutdown. Keep the main power supply connected. Home Assistant and its automations are unavailable while the Pi is off. A backup RTC battery retains time; it cannot boot the Pi without main power. Keep Pi awake cancels the current countdown; the occurrence is not retried after restart. To stop future scheduled shutdowns, turn scheduling off and save.

Your selected calendar and confirmed wake test survive ordinary app updates. Firmware or boot-setting changes require a new test. Use Settings → System → Updates for firmware version changes. A required preparation reboot has a red button and a scoped Home Assistant notification, which clears after successful checks.

## Everyday use

Successful setup opens **Overview**, with compact status and the upcoming saved schedule. **Calendar** holds schedule preferences. **UPS** holds power monitoring and protection. **Setup** keeps checks/preparation/test available for review and returns when attention is needed. Drafts are preserved during background refreshes. Detailed readings and forms are collapsed; countdowns and action messages remain visible across sections.

## UPS & power sources

This preview finds NUT devices already connected to Home Assistant and compatible power hooks. Monitoring is read-only; the separately enabled RTC recovery policy can request a graceful Pi shutdown. The app does not install a NUT server, probe the network, or send UPS commands.

NUT requires a server connected to the UPS. Add it through Home Assistant's Network UPS Tools integration. In **UPS**, select Find power sources, choose the source supplying this Pi, optionally enable power notices, and save. Raw statuses including `OL TEST` are accepted; conflicting status stays Unknown. The warning charge changes this app's notification preference, not the UPS hardware cutoff.

Expand **Additional NUT readings you can enable**. The Enable buttons activate actual Home Assistant sensors for your selected NUT device, including Battery runtime or Status data that are off by default. Home Assistant may reload NUT; wait for stable readings and scan again. Follow the message if a Home Assistant restart is required. Device/integration disablement is resolved on the linked native device page. Changes are blocked during a known outage. Active readings stay in their own collapsed list.

Unknown/unavailable data is shown as Unknown, never as restored power. A stale source cannot claim recovery support. The optional policy below uses RTC retries while main power stays supplied. UPS output-off/return control is a future phase that requires physical verification.

If a setup check fails, follow the next action shown. Details for support remains available for host-access failures. This app has host access for firmware-setting preparation and verification; install it only from a maintainer you trust. It uses Home Assistant authentication and has no public network port or separate password.

## UPS shutdown and RTC recovery

In **UPS → Configure UPS protection**, choose the remaining-runtime reading and review **Who shuts down this Pi?**. For timed retries, the community NUT app's Host shutdown option must be off; restart NUT after changing it and review other controllers. The app reads available settings and requires confirmation but does not change NUT or provide a complete shutdown handoff.

For timed retries, choose a writable Calendar and confirm this UPS keeps the tested Pi supplied while off. A compatible hook supplies typed runtime automatically. Emergency-only protection can be enabled with retries off, without a working RTC or selected Calendar. New control starts off; an enabled policy upgraded from 0.5 requires ownership review and Save before any protection resumes.

By default Home Assistant stays on until runtime reaches 30 minutes; early shutdown is optional. Conditional retries of 15/30/60 minutes require 24/39/69 minutes of fresh estimated runtime at their respective decisions. The table updates with your settings. The 30-minute threshold normally supports only the first at unchanged load. Planned retries are written/read back in the native Calendar before arming.

**Cancel this retry** or **Pause RTC retries for this outage** pauses timed retries while separately enabled emergency protection stays active. Failed RTC checks and Calendar changes also preserve commissioned emergency protection for the same UPS. Low battery, forced shutdown, the separate five-minute runtime reserve, or lost readings in a known outage can trigger an emergency graceful stop. Disabling that protection requires a separate confirmation. An emergency countdown cannot be cancelled by Keep Pi awake; fresh utility power can still cancel it before the host request.

Fresh stable utility power resumes normal scheduling. Low reserve/exhausted retries lead to a final stop with no verified timed wake. Critical reserve skips optional recording/countdown delays. Emergency shutdown does not require RTC access; unrelated alarms are preserved. Uncertain host requests are not repeated on the same boot.

The app does not control UPS outlets. If the UPS continues supplying a halted Pi, utility power returning alone will not restart it. Final recovery needs a tested output-off/return path, an external controller, a power cycle, or the Pi power button. Native sensor activation, ownership coordination, and the complete outage/return path still require real-device acceptance. Full setup is in UPS_RECOVERY.md in the ZIP.
