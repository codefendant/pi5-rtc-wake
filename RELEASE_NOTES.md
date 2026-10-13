# Pi 5 Wake & Sleep 0.10.0-rc.6 — Fill the dashboard sections

The previous release made some sections two or three columns wide while their cards still occupied one column. That left a visible empty column between Calendar/device cards and the cards on the right, and kept the Pi status summary narrow.

Generated Pi cards now use Home Assistant's Full width card option. On update, only unchanged wide starter sections are repaired; card positions, personal cards, section metadata, custom sizes/titles, Calendar dates, and saved settings are kept. Repaired cards carry an internal layout marker so a later explicit resize is respected. The summary also defaults to full section width when added through the card picker.

The browser preview now renders both native grid levels from the actual generated dashboard configuration, and checks that cards fill their two- and three-column sections. Backend and real Core checks cover the earlier layout upgrade and customized-card retention.

Update the same installed app to **0.10.0-rc.6**, Stop → Start, then open **Web UI → Maintenance and connection repair → Update / reconnect dashboard**. Restart Home Assistant when requested and refresh the browser. Do not uninstall or restore the dashboard just to apply this fix.

RTC/UPS behavior, countdown/test timing, Keep awake, schema 11, Calendar dates, valid wake evidence, and all feature settings are retained. No new wake test is required for this spacing repair. This remains a public preview; hardware and phone operations are simulated in automated checks.
