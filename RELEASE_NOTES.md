# Pi 5 Wake & Sleep 0.10.0-rc.5 — Compact dashboard

Pi status now brings the introduction page's Raspberry Pi artwork, green **Awake** indicator, and board name into the application. One compact summary holds uptime, the next active shutdown and wake times, **Keep awake / Resume shutdowns**, and **Settings**. A connection failure changes the status to Unavailable; old readings are not presented as live status.

Successful initial setup uses a small Ready badge. First-run guidance and new setup problems still appear when needed. **Settings** opens Review setup, Setup & maintenance, and the red confirmed Reboot Pi control; Back to dashboard closes it. Keep awake remains available during a countdown and retains the existing confirmation and administrator checks. Optional cards have shorter introductions, and saving phone settings closes the phone editor back to its summary.

On update, the five untouched starter header sections are combined into the summary. Personal cards, other views, feature cards, and dashboard metadata are kept. A renamed, resized, mixed, duplicated, incomplete, or other-Pi header is left as saved. Customized dashboards can add **Pi status** (the summary card) through Edit dashboard → Add card, or explicitly choose Settings → Dashboard options → Restore default Pi cards after adding the summary. The earlier individual cards remain supported.

Dashboard resource URLs now use the installed companion version so refreshed browsers load the new card code. Update the same app to **0.10.0-rc.5**, Stop → Start, then select **Web UI → Maintenance and connection repair → Update / reconnect dashboard**. Restart Home Assistant if requested and refresh the browser. Do not uninstall.

The RTC/UPS policy, thirty-second countdown, ten-minute test, Calendar dates, schema 11, valid wake evidence, saved phone/readings, Assist permissions, and device wake settings are retained. No additional physical wake test is required just for this layout update. This remains a public preview; automated checks simulate Pi/UPS/phone operations.
