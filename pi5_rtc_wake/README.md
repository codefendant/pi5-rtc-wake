## Before you select Start

**Turn Protection mode OFF in the Controls card on this Info tab.** Pi Wake & Sleep needs this permission to access the Raspberry Pi's wake alarm. Keep it off while using the app.

![Example Controls card showing Protection mode switched off before selecting Start](https://raw.githubusercontent.com/codefendant/pi5-rtc-wake/main/pi5_rtc_wake/protection-mode.svg)

1. Turn **Protection mode off**. If Home Assistant asks you to confirm, review and confirm the change.
2. Enable **Start on boot**, then select **Start**.
3. Select **Open Web UI** and follow **Connect dashboard**.

If the app is already running with Protection mode on, select **Stop → turn Protection mode off → Start**.

The picture is an example. Change the actual switch in your Home Assistant Controls card. Once Protection mode is off, Home Assistant displays its standard permission warning; keep it off for this app.

For the complete setup, open the **Documentation** tab above or the [installation guide](https://github.com/codefendant/pi5-rtc-wake/blob/main/INSTALL.md).
