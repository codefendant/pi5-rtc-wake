# Update Pi 5 Wake & Sleep

## Public repository installation

Open **Settings → Apps → Pi 5 Wake & Sleep** and select **Update** when Home Assistant offers a new version. Keep the same installed app so its settings are retained. Do not uninstall it. If an update is missing, open the app store's **⋮ → Check for updates** and refresh.

After updating, reload the Web UI and check the calendar summary. Firmware or boot-setting changes require a new wake test. An enabled 0.5 UPS policy keeps its preferences but waits for shutdown-ownership review in **UPS → Configure UPS protection** before automatic protection resumes.

Version **0.8.0-rc.1** adds optional native AI/voice tools in **Assist**. Existing Calendar, UPS, wake evidence, and phone settings are retained in schema 8; AI access starts off. Core 2026.10 or newer is required only for this optional feature. Use **Assist → Connect Assist**, restart Home Assistant if requested, and add the discovered companion. See [ASSIST.md](ASSIST.md). Future companion changes are installed through the same button, with consent settings and connection retained.

Version **0.7.0-rc.2** improves setup guidance. The host-access error now names **Protection mode** and gives the complete **Stop → turn Protection mode off → Start → Setup → Check again** sequence. This repair preserves settings and wake-test evidence; it does not change firmware, wake policy, or permissions. Keep this app's Protection mode off during use.

Version **0.7.0-rc.1** adds **Messages**. Your existing 0.6 Calendar selection, confirmed wake test, UPS policy, and outage state are retained. Phone messages start off. Use **Messages → Find phones and readings** to select a Companion app phone, preview/select existing readings, save, and check delivery with **Send status now**. Enable wake messages separately for the next Pi boot. See [PHONE_MESSAGES.md](PHONE_MESSAGES.md).

Moving from a local ZIP to the public repository is a separate installation, not an in-place update. Follow [INSTALL.md](INSTALL.md), stop the local app before starting the public app, and reselect your existing Calendar and preferences.

## Existing local source installation: update to 0.8.0-rc.1

This update adds optional native AI tools in Assist. Overview, Calendar, UPS, Messages, and Setup remain available. Calendar remains the only source of planned dates; AI access and phone delivery do not pause existing shutdown protection.

1. Download and extract the release's source ZIP from GitHub.
2. Open **Settings → Apps → Pi 5 Wake & Sleep → Info** and select **Stop**. Older versions call Apps **Add-ons**.
3. Open the same Samba share used for installation: **local_apps**, or **addons** on older versions.
4. Copy the contents of the ZIP's inner **pi5_rtc_wake** folder into the existing folder with that name. Choose **Replace files**. Do not create a second folder inside it.
5. In the app store select **⋮ → Check for updates**, refresh, open **Pi 5 Wake & Sleep**, and select **Update**.
6. Keep **Protection mode off** and start the app. Open Web UI and reload the page. The footer should show **0.8.0-rc.1**.
7. Check the saved calendar selection and upcoming list. Existing calendar events, enable preference, display time zone, and confirmed wake test are preserved. No new hardware test is needed unless firmware or wake settings changed.
8. If updating from 0.5 with UPS control enabled, open **UPS → Configure UPS protection**, review shutdown ownership, restart NUT if its Host shutdown option was changed, confirm ownership, and save. That older policy is paused until review. An update from 0.6 preserves its commissioned policy without another ownership pause. Perform updates while utility power is available.

Update the existing app; do not uninstall it. If Update is missing, confirm **config.yaml** in the shared app folder shows **0.8.0-rc.1**, then repeat Check for updates.

After successful setup, the app opens **Overview**. Checks/preparation/test remain available in **Setup** and return when attention is required. Calendar and UPS forms are in their own sections; detailed readings and protection settings are collapsed.

## Calendar is the schedule

Use the large **Open Home Assistant Calendar** button to edit dates and repeats. The app no longer has separate daily shutdown/wake fields. A daily rest is a repeating calendar event: start = shutdown, end = wake. For overnight operation choose the following day for the end.

If your old installation used Daily times, it is paused during migration. A message shows the old times so you can create the repeating event in Calendar. Choose the calendar, review its off periods, and enable scheduling. Historical backup files retain old settings for recovery, but no daily scheduler runs.

## Try the power monitor

A NUT server must be running and connected to the UPS, and Home Assistant's NUT integration must show its readings. NUT's integration connects to the NUT server, not directly to the UPS's own IP address.

1. Open **UPS** and select **Find power sources**.
2. Select the UPS or compatible hook that actually supplies this Pi.
3. Optionally enable **Show power notices in Home Assistant**, set the warning charge, and save.
4. Check utility/battery state and charge. Expand **Active readings from this UPS** if needed.
5. Expand **Additional NUT readings you can enable**, select **Enable** beside Battery runtime or another wanted sensor, and accept the sensor confirmation. Wait for NUT readings to return, then select **Find power sources** again. If the message requires a Home Assistant restart, use its normal system restart screens. Changes are blocked during a known outage.

Nothing is automatically selected or controlled. Disabled registry sensors can be shown even when no Status data is active. Save that NUT source, enable Status data, and scan again; an integration/device disabled as a whole must be enabled on the linked native device page. If there is no NUT server yet, set it up before using Connect NUT. See **UPS_HOOKS.md** and **UPS_RECOVERY.md**.

The monitor reads UPS data; the new Enable buttons alter Home Assistant sensor availability only. The optional host shutdown policy remains separate. **Cancel this retry** pauses timed retries for that outage while emergency protection stays active if enabled. Turning off emergency protection or the whole active policy requires a separate confirmation. The default retry requirements are 24/39/69 minutes, conditional on each fresh reserve decision.

An RTC retry needs continuous input power. A final stop does not promise a timed wake. If the UPS cuts output, restart requires verified output restoration or another powered controller. This app has no UPS output-return executor or complete NUT shutdown handoff.

## Compatibility

Saved settings migrate to schema 8. Assist access starts off; schema 7 preferences are retained. Schema 6 settings keep their commissioned policy, Calendar/UPS selections, notices, wake evidence, and outage attempts; phone messages start off. An enabled 0.5 policy retains its preferences but requires shutdown-ownership review before protection resumes. Calendar events remain in Home Assistant. Changing Calendar pauses RTC retry qualification while emergency protection remains bound to the saved UPS. Changing the physical source requires new qualification and is blocked during a known outage. Older versions protect this newer format, so rollback requires a matching Home Assistant backup. Red reboot controls and the native notification remain.
