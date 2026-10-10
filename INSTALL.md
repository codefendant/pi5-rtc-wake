# Install Pi 5 Wake & Sleep

**Public preview 0.7.0-rc.2.** You need Home Assistant OS 18 or newer running on a Raspberry Pi 5 and a power supply that stays connected while the Pi is off. Installation and setup use Home Assistant screens.

The repository and matching arm64 image are public. The installation image passed its anonymous-download and production-import checks. Use the link below to add the repository.

## Install

1. Open [**Add to Home Assistant**](https://my.home-assistant.io/redirect/supervisor_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fcodefendant%2Fpi5-rtc-wake). Select your Home Assistant and add the repository.
2. Open **Settings → Apps → App store**, find **Pi 5 Wake & Sleep**, and select **Install**. Older versions call Apps **Add-ons**.
3. On the app's **Info** page, turn off **Protection mode**. Enable **Start on boot** and **Show in sidebar**, then select **Start**.
4. Select **Open Web UI** or open **Pi Wake & Sleep** from the sidebar.

Keep this app's **Protection mode off** during use. It needs access to the Pi's wake settings and built-in RTC hardware; updating firmware does not grant that access. Each installation has its own Protection mode setting. If you started the app with it on, select **Stop**, turn it off, then select **Start** and **Setup → Check again**.

If the link cannot open your Home Assistant, open the app store's **⋮ → Repositories**, add `https://github.com/codefendant/pi5-rtc-wake`, then select **⋮ → Check for updates** and look for the app again.

## Confirm that this Pi can wake

1. Open **Setup** and wait for the checks. Follow the next action beside any failed check. If firmware needs updating, use Home Assistant's normal update screen, reboot, and return.
2. If requested, select **Prepare Pi for wake**. When complete, select the red **Reboot Pi** button and wait for Home Assistant to return.
3. Run the **ten-minute wake test**. Home Assistant shuts down for the test; wait for the Pi to wake and Home Assistant to return.
4. Confirm the successful wake in the app. If it did not wake automatically, leave scheduling disabled and follow Setup's instructions.

## Add dates and repeating times

1. Open **Settings → Devices & services → Add integration → Local Calendar** in Home Assistant. Create a dedicated calendar, such as **Pi Sleep**.
2. Return to the app's **Calendar** section, select **Check again**, choose that calendar, and save.
3. Select **Open Home Assistant Calendar**. Add a timed event with **All day** off. Set **start** to shutdown and **end** to wake. For 11 PM to 7 AM, the end date is the following day. Use Calendar's repeat options for recurring times.
4. Return to the app, select **Check again**, and review the upcoming off periods. Enable scheduling and save.

Events must last ten minutes to seven days and must not overlap or touch. All dates and repeat rules stay in Home Assistant Calendar. Use the same Calendar to edit or delete them.

## Optional UPS features

If you already have a working NUT server and Home Assistant's NUT integration, open **UPS → Find power sources**, select the UPS supplying this Pi, and save. You can enable power notices and additional NUT readings there. Follow the app's messages if enabling a sensor requires a reload or Home Assistant restart.

Shutdown protection starts disabled. Before enabling it, read [UPS_RECOVERY.md](UPS_RECOVERY.md) and complete the runtime and shutdown-ownership checks shown in the app. This release does not switch UPS output back on after a final shutdown.

## Optional phone messages

Install/open the Home Assistant Companion app on your phone and allow notifications. In **Messages**, select **Find phones and readings**, choose your phone, optionally choose up to twelve readings, and save. **Preview message** sends nothing; **Send status now** lets you check actual delivery. Every message includes uptime and the next shutdown/wake times. Enable **Send a message after this Pi starts** and save for the next Pi boot. Messages start off and app restarts do not duplicate a wake message. See [PHONE_MESSAGES.md](PHONE_MESSAGES.md).

## Already using the local ZIP installation?

You can keep your tested local app. Adding this public repository does not automatically move its settings. The public app is a separate installation.

1. Leave the local app installed, but **stop it and turn off its Start on boot before starting the public app**. Run only one Wake & Sleep app at a time.
2. Install the public app using the steps above. Complete its checks/wake confirmation and reselect your existing Calendar, UPS, and preferences. Your Calendar dates remain in Home Assistant.
3. Verify the upcoming list and protection settings before enabling scheduling or UPS control. Future updates use Home Assistant's normal Update button.

Do not uninstall an existing app to update it; uninstalling can remove its stored settings. See [UPDATE.md](UPDATE.md).
