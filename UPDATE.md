# Update Pi 5 Wake & Sleep

## 0.10.0-rc.6 dashboard spacing fix

1. Update the same app to **0.10.0-rc.6**, then **Stop → Start**.
2. Open **Web UI → Maintenance and connection repair → Update / reconnect dashboard** and confirm.
3. Restart Home Assistant when requested, then refresh the dashboard.

The Pi summary, Calendar, Wake other devices, and activity cards fill their unchanged wide sections instead of leaving an empty column. Existing card positions, personal cards, custom sizes/titles, and settings are preserved. Later explicit resizing remains respected. No new wake test is required; do not uninstall or Restore default Pi cards for this fix.

## 0.10.0-rc.5 compact dashboard

1. Update the same installed app to **0.10.0-rc.5**, then **Stop → Start**.
2. Open **Web UI → Maintenance and connection repair → Update / reconnect dashboard** and confirm.
3. Restart Home Assistant when requested, then refresh the browser (Ctrl+F5 if the previous layout is still loaded).

The compact Pi status summary contains the Raspberry Pi artwork, Awake indicator, uptime, next active shutdown/wake, Keep awake / Resume shutdowns, and Settings. Successful setup becomes a small Ready badge. Review setup, maintenance, and the red confirmed reboot are in Settings. First-run guidance and setup problems stay visible when needed. Messages closes back to its summary after saving; optional introductions are shorter.

The update combines only the five untouched starter header sections. Personal cards and dashboard metadata are kept. Edited or incomplete headers and other Pi cards are left as saved; use Edit dashboard → Add card → **Pi status** for the new summary. Older individual cards remain supported. Saved settings, Calendar dates, schema 11, and valid wake evidence are retained. No new wake test is required just to update.

## 0.10.0-rc.4 restart reminders and phone choices

1. Update the **same installed app** to **0.10.0-rc.4**, then **Stop → Start**.
2. Open **Web UI → Maintenance and connection repair → Update / reconnect dashboard** and confirm.
3. Restart **Home Assistant** when requested, then refresh the browser.

Companion installation/update now creates a Home Assistant notification explaining the restart. Once this new companion has loaded, later updates can also show a Settings → Repairs reminder. The first installation uses a notification because the new integration has not loaded yet. Restarting the app preserves the pending reminder; a matching, successfully registered dashboard clears it. This step restarts Home Assistant rather than the entire Pi.

Messages now shows phone choices as visible, selectable rows. Choose one phone, choose your readings, preview, save, and confirm a test send. **Refresh phones and readings** preserves your draft. Your saved phone and readings, scheduling, UPS settings, valid wake test, and personal cards are kept. No new wake test is required just to update. Do not uninstall the app.

## 0.10.0-rc.3 first sleep & wake guidance

1. Update the **same installed app** to **0.10.0-rc.3**, then **Stop → Start**.
2. Open **Web UI → Maintenance and connection repair → Update / reconnect dashboard** and confirm.
3. Restart **Home Assistant** when requested, then refresh the browser.

Pi setup now explains the first sleep and wake cycle before the ten-minute test, repeats the downtime in the confirmation, and describes how to confirm the automatic return and continue onboarding. The actual alarm, countdown, cancellation, power guards, and wake qualification are unchanged. Saved settings, valid wake evidence, Calendar dates, and personal cards are kept. **No new wake test is required just for this update.** Do not uninstall an existing app.

## 0.10.0-rc.2 dashboard connection repair

1. Update the **same installed app** to **0.10.0-rc.2**, then **Stop → Start**.
2. Open **Web UI → Maintenance and connection repair → Update / reconnect dashboard** and confirm.
3. Restart **Home Assistant** through **Settings → ⋮ → Restart Home Assistant** when requested, then refresh the browser.
4. For a first connection, select **Finish in Devices & services**. Under **Discovered**, add **Pi Wake & Sleep**, then **Submit** and **Finish**. An existing configured integration is reused; allow up to a minute for its dashboard check.
5. Open the dashboard after **Your dashboard is connected** appears, or through its sidebar entry.

The setup page previously offered a dashboard link as soon as the companion was installed, before a first-time user had added its integration. That could open **404: Not Found**. The link now waits for successful dashboard creation, and the page highlights the required restart/integration step. Setup errors stay visible in the Web UI and support details. A loaded older companion cannot register new cards until it has been updated and Home Assistant restarted. App restarts trigger another dashboard check without replacing personal cards.

Schema 11, feature choices, valid wake evidence, Calendar dates, and personal cards are retained. RTC/UPS scheduling, phone messages, Assist permissions, and device waking behavior are unchanged. Routine OS detection is logged once per detected board/version change; checks continue normally.

## 0.10.0-rc.1 Wake other devices

1. Update the **same installed app** to **0.10.0-rc.1**, then **Stop → Start**.
2. Open **Web UI → Maintenance and connection repair → Update / reconnect dashboard** and confirm.
3. Restart **Home Assistant** if requested, refresh the browser, and open **Pi Wake & Sleep**.
4. On **Wake other devices**, select **Choose devices**, select your existing Home Assistant Wake on LAN buttons, optionally associate Ping sensors, and save. Test **Wake selected** before enabling automatic waking.

The new card is added once while preserving your custom layout and personal cards. Device waking starts off. Existing Calendar dates, Keep awake, UPS protection, messages, Assist choices, and valid wake evidence are retained in schema 11. No new Pi wake test is required unless firmware or wake settings changed. Do not uninstall or restore default cards. See [WAKE_DEVICES.md](WAKE_DEVICES.md).

## 0.9.0-rc.4 dashboard cleanup

1. Update the **same installed app** to **0.9.0-rc.4**, then **Stop → Start**.
2. Open **Web UI → Maintenance and connection repair → Update / reconnect dashboard** and confirm.
3. Restart **Home Assistant** if requested, then refresh the browser and open **Pi Wake & Sleep** in the sidebar. An existing companion is reused. Add the discovered integration in Devices & services only for a first connection.

UPS protection settings now open on the UPS card. Calendar, UPS, Messages, Assist, and Pi controls are managed on the dashboard. The Web UI becomes **Setup & maintenance** for connection and diagnostics, and connected installations hide initial instructions. The optional app sidebar shortcut is renamed **Pi setup & maintenance**; you can turn off Show in sidebar on its Info page. This update keeps your sidebar preference.

Scheduling and protection behavior are unchanged. Schema 10, Keep awake, Calendar dates, saved feature choices, qualified wake evidence, outage records, phones, AI permissions, and personal dashboard cards are kept. No optional feature is automatically enabled. Do not uninstall or Restore default Pi cards. Another physical wake test is needed only when firmware or wake settings changed. See [DASHBOARD.md](DASHBOARD.md).

The earlier 0.9.0-rc.3 release introduced the persistent global **Keep awake / Resume shutdowns** switch, stable dropdowns, Calendar shortcuts, and runtime display while monitoring. Those changes are retained. Independent NUT/Home Assistant shutdowns remain outside this app's control.

The current update path is above; the older sequences below describe the releases that introduced those features.

## Public repository installation

Open **Settings → Apps → Pi 5 Wake & Sleep** and select **Update** when Home Assistant offers a new version. Keep the same installed app so its settings are retained. Do not uninstall it. If an update is missing, open the app store's **⋮ → Check for updates** and refresh.

After updating, reload the Web UI and check the calendar summary. Firmware or boot-setting changes require a new wake test. An enabled 0.5 UPS policy keeps its preferences but waits for shutdown-ownership review in **UPS → Configure UPS protection** before automatic protection resumes.

Version **0.8.0-rc.2** fixes Connect Assist stopping with "Home Assistant's configuration folder is not available." The app now explicitly maps that folder to the installer's path. Update the same app, then **Stop → Start → Open Web UI → Assist → Connect Assist**. Restart Home Assistant if requested and add the discovered integration in Devices & services. Existing Calendar, UPS, wake evidence, phone, and Assist settings are retained in schema 8. No new wake test is required for this fix. See [ASSIST.md](ASSIST.md).

Version **0.8.0-rc.1** adds optional native AI/voice tools in **Assist**. AI access starts off on upgrade; Core 2026.10 or newer is required only for this optional feature. Future companion changes are installed through Connect Assist, with consent settings and connection retained.

Version **0.7.0-rc.2** improves setup guidance. The host-access error now names **Protection mode** and gives the complete **Stop → turn Protection mode off → Start → Setup → Check again** sequence. This repair preserves settings and wake-test evidence; it does not change firmware, wake policy, or permissions. Keep this app's Protection mode off during use.

Version **0.7.0-rc.1** adds **Messages**. Your existing 0.6 Calendar selection, confirmed wake test, UPS policy, and outage state are retained. Phone messages start off. Use **Messages → Find phones and readings** to select a Companion app phone, preview/select existing readings, save, and check delivery with **Send status now**. Enable wake messages separately for the next Pi boot. See [PHONE_MESSAGES.md](PHONE_MESSAGES.md).

Moving from a local ZIP to the public repository is a separate installation, not an in-place update. Follow [INSTALL.md](INSTALL.md), stop the local app before starting the public app, and reselect your existing Calendar and preferences.

## Existing local source installation: update to 0.8.0-rc.2

This update adds optional native AI tools in Assist. Overview, Calendar, UPS, Messages, and Setup remain available. Calendar remains the only source of planned dates; AI access and phone delivery do not pause existing shutdown protection.

1. Download and extract the release's source ZIP from GitHub.
2. Open **Settings → Apps → Pi 5 Wake & Sleep → Info** and select **Stop**. Older versions call Apps **Add-ons**.
3. Open the same Samba share used for installation: **local_apps**, or **addons** on older versions.
4. Copy the contents of the ZIP's inner **pi5_rtc_wake** folder into the existing folder with that name. Choose **Replace files**. Do not create a second folder inside it.
5. In the app store select **⋮ → Check for updates**, refresh, open **Pi 5 Wake & Sleep**, and select **Update**.
6. Keep **Protection mode off** and start the app. Open Web UI and reload the page. The footer should show **0.8.0-rc.2**.
7. Check the saved calendar selection and upcoming list. Existing calendar events, enable preference, display time zone, and confirmed wake test are preserved. No new hardware test is needed unless firmware or wake settings changed.
8. If updating from 0.5 with UPS control enabled, open **UPS → Configure UPS protection**, review shutdown ownership, restart NUT if its Host shutdown option was changed, confirm ownership, and save. That older policy is paused until review. An update from 0.6 preserves its commissioned policy without another ownership pause. Perform updates while utility power is available.

Update the existing app; do not uninstall it. If Update is missing, confirm **config.yaml** in the shared app folder shows **0.8.0-rc.2**, then repeat Check for updates.

In the current dashboard, completed Pi setup collapses into a ready strip. Review setup opens checks/preparation/test. Calendar and UPS settings open on their cards; detailed readings remain collapsed until selected.

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

Current saved settings use schema 10. Legacy migrations retain preferences; Assist access starts off; schema 7 preferences are retained. Schema 6 settings keep their commissioned policy, Calendar/UPS selections, notices, wake evidence, and outage attempts; phone messages start off. An enabled 0.5 policy retains its preferences but requires shutdown-ownership review before protection resumes. Calendar events remain in Home Assistant. Changing Calendar pauses RTC retry qualification while emergency protection remains bound to the saved UPS. Changing the physical source requires new qualification and is blocked during a known outage. Older versions protect this newer format, so rollback requires a matching Home Assistant backup. Red reboot controls and the native notification remain.
