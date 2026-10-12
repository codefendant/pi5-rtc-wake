# Pi 5 Wake & Sleep 0.10.0-rc.2 — Dashboard connection repair

A fresh installation could show **Open Pi Wake & Sleep** after installing its companion, before Home Assistant had created the dashboard. Opening that link returned **404: Not Found**. The setup page now highlights the next required step and waits for successful creation before showing the link.

- Highlight Home Assistant restart and **Finish in Devices & services**. Under Discovered, add Pi Wake & Sleep, then Submit and Finish.
- Show dashboard setup failures in the app, support details, and logs instead of reporting contact as completed setup.
- Check the loaded companion version before registering cards; update/restart guidance prevents new cards loading against older companion code.
- Recheck the dashboard after an app restart without replacing your layout or personal cards.
- Log OS detection when the board/version changes instead of every routine check.

Update the same app, **Stop → Start**, then open **Web UI → Maintenance and connection repair → Update / reconnect dashboard**. Restart Home Assistant when requested and refresh the browser. For a first connection, finish adding the discovered integration in Devices & services. Open the dashboard when **Your dashboard is connected** appears.

Schema 11, saved feature choices, Calendar dates, valid wake evidence, and personal cards are kept. RTC/UPS power behavior, Messages, Assist permissions, and Wake other devices are unchanged. This remains a public preview. Automated checks exercise real Home Assistant APIs with simulated Pi/UPS/phone/device services; physical wake and UPS recovery still require testing on the actual installation.

[Install](https://github.com/codefendant/pi5-rtc-wake/blob/main/INSTALL.md) · [Update](https://github.com/codefendant/pi5-rtc-wake/blob/main/UPDATE.md) · [Validation](https://github.com/codefendant/pi5-rtc-wake/blob/main/VALIDATION.md)
