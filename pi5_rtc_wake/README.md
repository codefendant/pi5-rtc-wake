## Before you select Start

**Turn Protection mode OFF in the Controls card on this Info tab.** Pi Wake & Sleep needs this permission to access the Raspberry Pi's wake alarm. Keep it off while using the app.

![Example Controls card showing Protection mode switched off before selecting Start](https://raw.githubusercontent.com/codefendant/pi5-rtc-wake/main/pi5_rtc_wake/protection-mode.svg)

1. Turn **Protection mode off**. If Home Assistant asks you to confirm, review and confirm the change.
2. Enable **Start on boot**, then select **Start**.
3. Select **Open Web UI** and follow **Connect dashboard**.

If the app is already running with Protection mode on, select **Stop → turn Protection mode off → Start**.

The picture is an example. Change the actual switch in your Home Assistant Controls card. Once Protection mode is off, Home Assistant displays its standard permission warning; keep it off for this app.

## Finish connecting your dashboard

After selecting **Connect dashboard**, restart **Home Assistant** only if requested. When it returns, select **Finish in Devices & services**, or open **Settings → Devices & services**.

Under **Discovered**, look for the **Pi Wake & Sleep** card shown below. Select **Add**, then **Submit → Finish**.

![Example Pi Wake and Sleep discovery card with the Add button highlighted](https://raw.githubusercontent.com/codefendant/pi5-rtc-wake/main/pi5_rtc_wake/finish-dashboard.svg)

Return to the setup page and select **Check again** if needed. When it says **Your dashboard is connected**, select **Open Pi Wake & Sleep**. The dashboard is also available in Home Assistant's sidebar.

The picture is an example; click **Add** on the actual discovery card in Home Assistant. If Pi Wake & Sleep is already configured, wait for its connection check instead of adding it again.

## Your first sleep & wake cycle

The ten-minute test shuts down the Pi and Home Assistant after a 30-second countdown. **Home Assistant and its automations will be unavailable for roughly ten minutes, plus startup time.** Keep main power connected: the RTC is set to wake the Pi about ten minutes after the test starts.

When Home Assistant returns, open Pi Wake & Sleep and confirm **Yes, it returned by itself** if it woke automatically. Then continue setup on the Calendar and other dashboard cards. If it has not returned after 15 minutes, press the Pi power button and choose **No / I’m not sure**. Scheduling and UPS recovery turn off for the test; review them afterward.

For the complete setup, open the **Documentation** tab above or the [installation guide](https://github.com/codefendant/pi5-rtc-wake/blob/main/INSTALL.md).
