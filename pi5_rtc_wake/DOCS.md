# Getting started

## Before you select Start

**On the Info tab, turn Protection mode OFF in the Controls card before starting this app.** This lets Pi Wake & Sleep access the Raspberry Pi's wake alarm. Keep it off while using the app.

![Example Controls card showing Protection mode switched off before selecting Start](https://raw.githubusercontent.com/codefendant/pi5-rtc-wake/main/pi5_rtc_wake/protection-mode.svg)

Enable **Start on boot**, then select **Start**. If the app is already running with Protection mode on, select **Stop → turn Protection mode off → Start**. Home Assistant displays its standard permission warning once protection is disabled.

## Connect your dashboard

When the companion is installed or updated, a Home Assistant notification says **Pi Wake & Sleep: restart Home Assistant to finish setup**. Open **Settings → ⋮ → Restart Home Assistant**. After this companion has loaded once, later updates can also show a reminder in **Settings → Repairs**. The first installation uses a notification because the new integration cannot create a repair until Home Assistant loads it. The reminder survives an app restart and clears after the matching companion successfully connects the dashboard.

The editable **Pi Wake & Sleep** dashboard is the main interface. This app's **Open Web UI** opens **Setup & maintenance** for installation, companion updates/reconnection, and diagnostics.

1. On this app's Info page turn **Protection mode off**, enable **Start on boot**, and start the app. If it is already running, select Stop before changing Protection mode and Start afterward.
2. Select **Open Web UI → Connect dashboard** and confirm. Requires Home Assistant Core 2026.10 or newer.
3. If requested, restart **Home Assistant** through **Settings → ⋮ → Restart Home Assistant**. Then select **Finish in Devices & services**. Under **Discovered**, add **Pi Wake & Sleep**, then **Submit** and **Finish**. Existing companion connections are reused and AI access stays a separate choice.
4. Once **Your dashboard is connected** appears, open **Pi Wake & Sleep** from the setup page or sidebar. Its setup card guides permissions, Pi checks, preparation/reboot only if needed, and the ten-minute wake test. Confirm whether Home Assistant returned by itself.
5. On the Calendar card, create **Pi Sleep** or choose an existing calendar. Add timed events in Home Assistant Calendar: start = shutdown, end = wake. For overnight operation choose the next day as the end. Turn All day off, use periods from ten minutes to seven days, and avoid overlaps or touching events. Review and enable scheduling on the card.

### Find the discovery card

After any requested Home Assistant restart, open **Settings → Devices & services**. Under **Discovered**, look for **Pi Wake & Sleep** and select **Add**, then **Submit → Finish**.

![Example Pi Wake and Sleep discovery card with the Add button highlighted](https://raw.githubusercontent.com/codefendant/pi5-rtc-wake/main/pi5_rtc_wake/finish-dashboard.svg)

Return to Setup & maintenance and select **Check again** if needed. Wait for **Your dashboard is connected**, then select **Open Pi Wake & Sleep**. If the integration is already configured, allow its connection check to finish instead of adding it again. The picture is an example; use the actual discovery card in Home Assistant.

No terminal, YAML, personal token, or separate card download is needed. Home Assistant Calendar holds every date and repeat. Use Edit dashboard to add your pictures, graphs, and other cards. Completed setup stays compact; Review setup brings it back. The optional app sidebar shortcut can be hidden on Info after the dashboard works; Open Web UI and the dashboard setup area still open maintenance.

Keep main power connected for RTC wake. The RTC battery retains time and cannot power the Pi. Home Assistant and its automations are unavailable while the Pi is off. Keep Protection mode off during normal use so the app can check wake settings and program alarms. Home Assistant handles firmware version updates; this app checks/prepares the low-power wake settings while preserving boot order.

## Your first sleep & wake cycle

The ten-minute test shuts down the Pi and Home Assistant after a 30-second countdown. **Home Assistant and its automations will be unavailable for roughly ten minutes, plus startup time.** Keep main power connected: the RTC is set to wake the Pi about ten minutes after the test starts.

When Home Assistant returns, open Pi Wake & Sleep and confirm **Yes, it returned by itself** if it woke automatically. Then continue setup on the Calendar and other dashboard cards. If it has not returned after 15 minutes, press the Pi power button and choose **No / I’m not sure**. Scheduling and UPS recovery turn off for the test; review them afterward.

## Everyday controls

Use Pi status, the next shutdown/wake cards, Calendar, UPS power, Messages, Assist, and Recent activity on the dashboard. Each feature's settings open on its card. User-opened details and unsaved forms survive status refreshes.

**Keep awake** suspends every shutdown/reboot issued by this app, including future Calendar dates, timed retries, emergency UPS shutdowns, wake tests, and approved AI power operations. It survives app restarts until **Resume shutdowns**. Saved dates and choices are kept; monitoring and messages continue. The Pi status power icon uses the same confirmed switch. Other controllers retain their own shutdown authority; a submitted OS request cannot be retracted. Reboot Pi has a red background and confirmation.

## UPS power and protection

Connect a NUT server to the UPS and use Home Assistant's Network UPS Tools integration, or an integration publishing a compatible power sensor. On the UPS card find and select the source supplying this Pi. Monitoring, notices, and automatic protection are separate choices. Runtime can display with protection off. Active readings, disabled readings, refresh, and the native NUT device link are available on the card.

Select **Set up protection** or **Protection settings** on the UPS card. Review the remaining-runtime measurement and who shuts down the Pi. For timed retries, turn off NUT's Host shutdown option, restart NUT, review other controllers, choose a writable Calendar, and confirm the wake test on the actual continuous supply path. A compatible hook provides typed runtime. Emergency-only protection can be configured with timed retries off, without RTC/Calendar readiness.

All existing timings and acknowledgements are on the card. Default 15/30/60-minute retries require at least 24/39/69 minutes of fresh estimated runtime at each decision. A 30-minute threshold normally funds the first attempt only at unchanged load; later attempts are conditional. Pausing timed retries leaves configured emergency protection active. Disabling emergency protection requires its own confirmation. Global Keep awake suspends emergency protection too.

Low reserve, exhausted retries, or lost readings during a known outage can cause a final stop without a timed wake. This app does not switch UPS outputs or implement a complete NUT shutdown handoff. If the UPS keeps supplying a halted Pi, utility power returning alone will not restart it. Test the actual output-return path before relying on unattended recovery. [UPS setup and limits](https://github.com/codefendant/pi5-rtc-wake/blob/main/UPS_RECOVERY.md).

## Wake other devices

On the optional Wake other devices card choose your existing Home Assistant Wake on LAN buttons. Add devices and Ping checks through its Home Assistant links, select the matching online sensor if wanted, and save. Test Wake selected before enabling automatic waking after a recorded Calendar wake or every Pi boot. Automatic waking starts off; saving sends nothing. Only wake on utility power uses fresh readings from the UPS card and also applies to manual requests. The card distinguishes requested packets from fresh confirmed network reachability. [Device wake setup](https://github.com/codefendant/pi5-rtc-wake/blob/main/WAKE_DEVICES.md).

## Messages and Assist

On Messages select Choose phone; discovery opens the settings automatically with a visible phone list. Choose one phone from that list. Refresh phones and readings updates the list while keeping your draft. Connect the Home Assistant Companion app on the phone first and allow notifications. Select up to twelve readings using suggestions, all readings, categories, or search. Preview a draft without sending, save, and confirm Send status now to check delivery. Optional boot messages include uptime and the next shutdown/wake times. Discovery refresh preserves your draft; a saved missing phone is never silently replaced. [Phone messages](https://github.com/codefendant/pi5-rtc-wake/blob/main/PHONE_MESSAGES.md).

On Assist select Connect Assist to enable status access, then choose Assist under Control Home Assistant in your existing AI integration, such as local Ollama. Change requests are separately enabled and require approval on the dashboard. Approved dates stay in Home Assistant Calendar. [Assist setup](https://github.com/codefendant/pi5-rtc-wake/blob/main/ASSIST.md).

## Updates and support

Update the same app, Stop → Start, and open **Maintenance and connection repair → Update / reconnect dashboard**. Restart Home Assistant if requested and refresh the browser. Valid wake evidence, settings, Calendar dates, outage records, and personal cards are kept. A new wake test is needed only when firmware or wake settings changed.

A first installation creates its dashboard only after you add the discovered integration in **Settings → Devices & services**. An installed companion alone is not a completed dashboard connection. If the dashboard will not load, use Open Web UI for reconnection, Check again, and Details for support. The setup page keeps its failed connection check and next action visible. Errors explain the next action; diagnostics contain no API token. This is a public preview. Simulations and API checks do not establish physical wake/UPS recovery or the novice installation requirement. [Installation](https://github.com/codefendant/pi5-rtc-wake/blob/main/INSTALL.md) · [Validation](https://github.com/codefendant/pi5-rtc-wake/blob/main/VALIDATION.md).
