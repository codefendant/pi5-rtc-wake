# Phone wake and status messages

Phone messages are optional and start off. They use the Home Assistant Companion app you already connect to Home Assistant. No separate phone service, account, API token, YAML automation, or template is required.

## Set up through Home Assistant

1. Install/open the Home Assistant Companion app on your phone, connect it to this Home Assistant, and allow notifications on the phone.
2. Open the dashboard’s **Messages → Choose phone**; discovery opens its settings automatically.
3. Select one phone from the visible list. The selected row is highlighted; there is no phone dropdown. Select **Choose later** to leave messages unconfigured. Home Assistant's current **Phone entity** targets and older **Companion app action** targets are both supported. You may see both for the same phone; choose one. General notification broadcasts, TVs, and other notification integrations are excluded.
4. Optionally use **Show readings** to choose Suggested, All available readings, or a category. Search by name, entity ID, area, or type, and choose up to twelve readings. Suggestions include your selected NUT UPS, batteries, temperatures, weather, security/maintenance, and energy/power. Search scans all available supported readings. Hidden, disabled, and configuration entities are excluded. For disabled UPS sensors, use **UPS → Additional NUT readings you can enable** first.
5. Select **Preview message** to inspect the open draft without sending it. **Refresh phones and readings** refreshes discovery while keeping your unsaved phone and field choices. Select **Save phone settings**, then **Send status now** and confirm the selected phone. Check your phone to confirm delivery.
6. Enable **Send a message after this Pi starts** and save if you want automatic wake messages. The first automatic message is after the next Pi boot. Saving settings does not send a message for the current boot.

Automatic wake messages and manual status messages include **Pi uptime**, **next shutdown**, and **next wake** even if you select no extra readings. The times come from the existing Calendar/controller state. Messages explain disabled/paused scheduling, no upcoming event, conditional UPS recovery, and final shutdown without a timed wake. Planned Calendar dates are marked as planned because the app rechecks them before shutdown. All future dates remain in Home Assistant Calendar.

## What counts as a wake?

A new **Pi host boot** counts, including an RTC wake, reboot, or boot after restored input power. Restarting/updating the app on the same Pi boot does not create another automatic wake message. The app does not infer which hardware mechanism caused the boot.

The message worker waits at least one minute after app startup. It gives selected readings and the Calendar up to three additional minutes to become available. Readings are Home Assistant's reported states and units, with an observation from this host boot. Explicit restored values, older-boot observations, unknown, and unavailable values are labelled instead of reported as fresh. Older observations from the current boot show their age after an hour. A Home Assistant observation does not prove a new physical measurement; update timing depends on the source integration.

Suggestions reuse native entity metadata. They do not copy your dashboard configuration, favorites, or the exact dashboard priority order. Weather condition/temperature/humidity and climate current temperature/humidity can be selected. Other supported entities contribute their state. Arbitrary attributes and executable templates are not accepted.

**Today's energy:** the Energy dashboard calculates totals from statistics and its configured sources. This release sends a selected entity's current value and unit; it does not calculate the dashboard's daily total. Choose an existing daily energy sensor if that is the value you want. Cumulative meter totals retain their original meaning.

## Delivery and recovery

**Accepted by Home Assistant** means the notification action completed, not that the phone displayed it. Home Assistant and the Companion app manage delivery. The app records an automatic send attempt before calling Home Assistant, so an interrupted or uncertain request is not automatically repeated on the same boot. If confirmation fails, check your phone and use **Send status now** if you want another message. Discovery/readiness failures before an attempt can be retried while the Pi stays awake.

Phone work runs in a separate worker. Discovery, a slow phone request, or a failed delivery cannot hold the RTC/UPS worker's lock during network I/O or change the shutdown policy. A shutdown may finish before a message can be submitted; shutdown protection has priority.

The Companion app can use [Local Push](https://companion.home-assistant.io/docs/notifications/notification-local/) where supported and connected. Otherwise Home Assistant may use Apple/Google push. This app uses Home Assistant's existing connection and does not select the phone's delivery transport or guarantee local delivery when the phone is away. Local delivery during an internet outage needs a working local network and a connected phone.

If a phone is missing, open the Companion app and allow notifications, then find phones again. A first registration may require a Home Assistant restart. If a saved phone disappears, the app asks you to choose again; it does not broadcast to another target. A missing selected reading remains saved and is marked unavailable; remove or reselect it in Messages. Changes require **Save phone settings** before manual sending.

Phone choice, selected readings, wake preference, and the historical boot claim survive updates. Schema 6 settings migrate to schema 7 with messages off and existing Calendar/UPS settings preserved. Restoring the previous settings copy retains the phone choice but disables automatic messages for review. Rollback to an older app requires a matching Home Assistant backup.

## Validation

The automated suite uses simulated phones only. It covers both notification API forms, explicit phone selection/send consent, metadata/visibility filtering, preview, settings persistence, current-boot observations, bounded startup waiting, claim-before-send, uncertain delivery, app restarts, and a blocked phone request while Pi shutdown completes. Real Companion app delivery and an actual RTC-wake message still require confirmation on your Pi and phone.

Sources: [Companion notifications](https://companion.home-assistant.io/docs/notifications/notifications-basic/) · [Notify actions](https://www.home-assistant.io/integrations/notify/) · [Dashboard summaries](https://github.com/home-assistant/frontend/blob/dev/src/panels/lovelace/strategies/home/helpers/home-summaries.ts) · [Energy](https://www.home-assistant.io/docs/energy/)
