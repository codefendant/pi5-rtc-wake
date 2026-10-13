# Pi 5 Wake & Sleep 0.10.0-rc.4 — Restart reminders and visible phone choices

Installing or updating the dashboard companion now immediately creates a Home Assistant notification titled **Pi Wake & Sleep: restart Home Assistant to finish setup**. Pending restart information survives an app restart and clears when the matching loaded companion successfully connects the dashboard. Failed notification updates retry separately from the RTC/UPS worker and retain the setup reminder in the app.

After this new companion has loaded, subsequent companion updates can also show a native **Settings → Repairs** reminder. The first installation uses a notification: the new integration is not running inside Home Assistant yet and cannot create a repair before it loads. Restart **Home Assistant** through **Settings → ⋮ → Restart Home Assistant**; dashboard installation does not require a full Pi reboot.

Messages now lists the discovered phones visibly, with a selection beside each name and a highlighted selected row. Choose one phone, then choose readings. **Refresh phones and readings** refreshes discovery and keeps draft selections. An unavailable saved phone remains labeled and selected instead of being replaced. Preview and saving do not send a message; delivery still requires the existing explicit test-send confirmation or previously enabled boot-message policy.

The power policy, ten-minute test, countdown, cancellation, wake evidence, schema 11, Calendar dates, saved phone choices/readings, Assist permissions, UPS settings, and personal cards are retained. No new physical wake test is required just for this update.

Update the same app to 0.10.0-rc.4, Stop → Start, then use **Web UI → Maintenance and connection repair → Update / reconnect dashboard**. Restart Home Assistant if requested and refresh the browser. Do not uninstall an existing app to update it.

This remains a public preview. Automated checks simulate Pi/UPS/phone operations; the reminder and phone interface improvements are not new physical wake or phone-delivery tests.
