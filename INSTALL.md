# Install Pi 5 Wake & Sleep

**Public preview 0.10.0-rc.2.** Use Home Assistant OS 18 or newer on a Raspberry Pi 5, Home Assistant Core 2026.10 or newer, and a main power supply that stays connected while the Pi is off. Installation and setup use Home Assistant screens.

## Install once

1. Open [Add to Home Assistant](https://my.home-assistant.io/redirect/supervisor_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fcodefendant%2Fpi5-rtc-wake), confirm the repository, and install **Pi 5 Wake & Sleep** from the app store.
2. On the app's Info page, turn **Protection mode off**, enable **Start on boot**, and select **Start**. If it was already running with Protection mode on, use **Stop → turn Protection mode off → Start**.
3. Select **Open Web UI**. This opens **Setup & maintenance**. Select **Connect dashboard** and confirm.
4. If requested, open **Settings → ⋮ → Restart Home Assistant**, select the normal restart, and wait for it to return.
5. Select **Finish in Devices & services** on the setup page, or open **Settings → Devices & services**. Under **Discovered**, select **Add** for **Pi Wake & Sleep**, then **Submit** and **Finish**. An existing companion is reused.
6. Wait for **Your dashboard is connected**, then select **Open Pi Wake & Sleep**, or use its sidebar entry. Continue Pi setup and activate the features you want on its cards.

No terminal, YAML, personal API token, extra card download, or AI account is needed. The dashboard works with AI access off. If the repository link cannot open your Home Assistant, use the app store's **⋮ → Repositories** to add `https://github.com/codefendant/pi5-rtc-wake`, then **⋮ → Check for updates**.

The app's separate sidebar shortcut is optional. Once the dashboard works, you can turn off **Show in sidebar** on the app's Info page. **Setup & maintenance** remains available through **Open Web UI** and the dashboard's setup area. Keep Protection mode off during normal use: it grants access to wake settings and the RTC; a firmware update does not grant those permissions.

## Confirm this Pi can wake

1. The dashboard's setup card checks **Permissions → Pi checks → Wake test**. Follow the next action beside a failed check. Home Assistant handles firmware version updates.
2. Select **Prepare this Pi** only if requested, then the red **Reboot Pi** button if requested. Keep power connected and wait for Home Assistant to return.
3. Run the **ten-minute wake test**, wait for Home Assistant to return, and confirm whether it returned by itself.
4. If it did not return automatically, leave timed scheduling disabled and follow the setup guidance.

Completed setup becomes **Pi ready · Wake test passed**. **Review setup** opens it again; **Back to dashboard** closes it. A later readiness problem brings guidance back.

## Add dates and repeating times

1. On the Calendar card, select **Create Pi Sleep calendar**, or **Choose existing calendar**. Creating a calendar leaves scheduling off.
2. Open Calendar and add a timed event with **All day off**. Event **start = shutdown**, **end = wake**. For an overnight period, choose the following day as the end date. Use Home Assistant's repeat options for recurring times.
3. Review the upcoming list, then select **Enable scheduling** and confirm.

Periods must last ten minutes to seven days and must not overlap or touch. All dates and repeat rules remain in Home Assistant Calendar. Select a listed period to open its native Calendar view and edit it there.

**Keep awake** suspends every shutdown and reboot from this app, including future Calendar dates and emergency UPS shutdowns, until **Resume shutdowns**. Dates and feature choices are kept. Independent NUT/Home Assistant shutdowns remain outside this app's control.

## Activate optional features on the dashboard

- **UPS power:** With a working NUT server and Home Assistant NUT integration, select **Find my UPS**, then **Choose UPS**, and save the source supplying this Pi. Enable wanted NUT readings on this card. **Set up protection** opens runtime, ownership, reserve, and retry settings on the dashboard. Automatic protection starts off; review [UPS_RECOVERY.md](UPS_RECOVERY.md) before enabling it.
- **Wake other devices:** Choose existing Home Assistant Wake on LAN buttons, optionally associate Ping sensors, save, and test **Wake selected**. Automatic waking after a scheduled Calendar wake or every Pi boot is separately enabled. See [WAKE_DEVICES.md](WAKE_DEVICES.md).
- **Messages:** Connect the Home Assistant Companion app on your phone and allow notifications. Select **Choose phone**; discovery opens the settings automatically. Select a phone and up to twelve readings, preview the draft, save, and confirm **Send status now** to check delivery. Automatic messages after Pi boot are separately enabled. See [PHONE_MESSAGES.md](PHONE_MESSAGES.md).
- **Assist:** Select **Connect Assist** on its card to enable status access. In your existing AI integration, such as local Ollama, choose **Assist** under **Control Home Assistant**. Change requests are separately enabled and require approval on the dashboard. See [ASSIST.md](ASSIST.md).

Use **Edit dashboard → Add card** to add your own pictures, graphs, and other Home Assistant cards. Settings, valid wake evidence, and personal cards are kept through ordinary updates. [DASHBOARD.md](DASHBOARD.md) explains every card.

## Already using the local ZIP installation?

The public app is a separate installation. Adding its repository does not move settings from a local app.

1. Keep the local app installed, but **stop it and turn off Start on boot before starting the public app**. Run only one Wake & Sleep app at a time.
2. Install the public app, complete its checks/wake confirmation, and reselect the existing Calendar, UPS, and preferences. Calendar dates remain in Home Assistant.
3. Review dates and protection settings before enabling automatic control. Future updates use Home Assistant's Update button on the same app.

Do not uninstall an existing app to update it. See [UPDATE.md](UPDATE.md).
