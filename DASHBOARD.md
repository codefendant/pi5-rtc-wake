# Pi Wake & Sleep dashboard

The dashboard preview adds a native Home Assistant dashboard. Move, resize, remove, and add cards with **Edit dashboard**, including ordinary pictures, history graphs, weather, and other Home Assistant cards. The app continues to run the RTC, Calendar, UPS, phone, and Assist functions.

## Connect once

1. Update the existing app, then **Stop → Start**. Open **Setup & maintenance** or its **Open Web UI** button.
2. Select **Connect dashboard** and confirm on first installation. For an update, open **Maintenance and connection repair → Update / reconnect dashboard** and confirm. This installs or updates the bundled companion; it keeps your settings and does not turn on AI access.
3. Restart **Home Assistant** from Settings if requested. This is a Home Assistant restart, not the Pi reboot used during wake preparation.
4. In **Settings → Devices & services**, add the discovered **Pi Wake & Sleep** integration. An existing Assist companion is reused and its dashboard should appear after restarting Home Assistant.
5. Open **Pi Wake & Sleep** in the sidebar. Refresh your browser once if cards still show loading after companion setup finishes.

No terminal, YAML, personal API token, or extra card download is needed. AI access remains a separate choice. This uses Home Assistant's normal storage dashboard/resource mode; it does not change YAML-managed dashboards or resources.

## One place to manage features

The **Pi Wake & Sleep** dashboard holds Pi status, everyday power controls, Calendar settings, UPS monitoring/protection, Messages, Wake other devices, and Assist. Each feature opens its settings on its card. The add-on Web UI is **Setup & maintenance** and holds connection, companion update/reconnection, and support diagnostics only. An active connection hides initial installation instructions.

The optional app sidebar entry is named **Pi setup & maintenance**. Turn off **Show in sidebar** on its Info page if you want just the dashboard entry. That preference is kept; this update does not alter your sidebar choices. Open Web UI and the dashboard setup area still open maintenance.

## Guided Pi setup

The setup card begins with **Permissions → Pi checks → Wake test**. It checks Protection mode and links to the app's own Info page. The illustration highlights the switch: **Stop the app → turn Protection mode off → Start the app**. Checks continue automatically while the app is running.

Turning Protection mode off grants access; the Pi is marked ready only after the wake settings, clock, and successful wake test have been checked. Prepare wake settings only if requested, reboot the Pi if requested, then run and confirm the ten-minute test. An existing valid wake test is retained when firmware and wake settings have not changed.

Completed setup collapses into **Pi ready · Wake test passed**. **Review setup** opens the details again, and **Setup & maintenance** opens connection repair; **Back to dashboard** closes them. Leaving unfinished setup keeps a **Pi setup needs attention** strip and does not enable power operations. A new readiness problem brings the needed guidance back. Power operations show confirmations and require a Home Assistant administrator; other users can view status.

## Calendar

**Create Pi Sleep calendar** creates and selects a native Home Assistant Local Calendar named **Pi Sleep**. An existing Local Calendar with that original name is reused, including its dates. The actual entity ID is resolved rather than guessed. An already selected calendar is not replaced and scheduling is not silently enabled.

Alternatively, use **Choose existing calendar**. Changing calendars leaves scheduling off until reviewed. Use **Open Calendar** to enter dates and recurring events in Home Assistant: **event start = shutdown; event end = wake**. Turn **All day** off. Overnight events end on the following date. Periods must last ten minutes to seven days and must not overlap or touch.

Calendar remains the only store of scheduled dates. After reviewing events and passing the wake test, select **Enable scheduling** and confirm. Cards show local times and a countdown such as “in 2 h.” Paused or stale data is explained rather than shown as an active shutdown.

Select a listed off period to open Home Assistant's native Calendar card at that day and, when available, its event details. Select **Edit** there. Home Assistant handles recurring-event choices and permissions; this app does not create another date store. **Back to Pi dashboard** closes the Calendar view. **Open Calendar** remains available if the event shortcut cannot load.

## Keep awake

**Keep awake** suspends every shutdown and reboot issued by this app, including future Calendar shutdowns, timed UPS retries, emergency low-battery shutdowns, wake tests, and reviewed AI power operations. It cancels a countdown that has not yet been submitted. This choice survives app restarts and updates until you select **Resume shutdowns**. The power icon in **Pi status** toggles the same choice with confirmation.

Calendar dates, enabled/disabled feature choices, wake-test evidence, and other settings are kept. **Resume shutdowns** restores the saved choices; it does not enable previously disabled features or bypass normal readiness/fresh-reading checks. Low UPS reserve can trigger shutdown as soon as protection resumes. An amber state shows when all app shutdowns, including UPS protection, are suspended. Monitoring, phone messages, and status access continue.

Keep awake controls this app's power operations. It cannot retract a shutdown already submitted to Home Assistant or prevent NUT, Home Assistant, or another controller from issuing its own shutdown.

## Optional cards

- **UPS power:** Find and select the UPS supplying the Pi. Monitoring starts separately from automatic protection. Runtime is displayed in monitoring mode when the saved reading is available or the NUT registry identifies one enabled Battery runtime measurement for this UPS. A duration setting or another UPS's sensor is never guessed. Missing, disabled, unavailable, and stale readings have different explanations. Disabled NUT readings can be enabled from the card. **Set up protection** opens detailed settings on the card for shutdown ownership, runtime selection, every retry/emergency threshold, and supply/final-stop acknowledgements. The conditional retry table updates as you edit. Disabling emergency protection and enabling a new policy keep their existing confirmations. **Protection status** shows outage attempts and the separately confirmed pause-timed-retries control. Active readings, refresh, and the native UPS device link remain available.
- **Messages:** Select **Choose phone**; discovery automatically opens the settings. Choose a Companion app phone and up to twelve existing readings using suggestions, all readings, categories, or search. **Find phones and readings** refreshes discovery while retaining the draft. **Preview message** previews the draft without sending. Save and send a confirmed test message. Automatic wake messages are separately enabled. Each message includes uptime and the next shutdown/wake times.
- **Assist:** Enable status access, then select **Assist** in the existing AI agent's **Control Home Assistant** setting. Change requests are separately enabled and wait for approval in the card or app. Turning AI access off keeps the dashboard available.
- **Controls:** **Keep awake / Resume shutdowns** suspends or resumes all app power operations as described above. Calendar-only changes still use the Calendar card's scheduling control. **Reboot Pi** has a red background, requires confirmation, and is unavailable while Keep awake is on.
- **Recent activity:** Collapsed by default; shows recent dashboard setup and action entries in plain language. Open dropdowns, including activity, message previews, Pi checks, NUT readings, and agent setup, remain open during status refreshes until you close them.

## Personalize and update

Select **Edit dashboard → Add card**. Pi cards have visual editors for their title and connected Pi. Nine read-only entities provide uptime, next shutdown/wake, UPS battery/runtime/power, wake readiness, Calendar scheduling, and emergency protection. Use them in standard graphs, tiles, and entity cards. Existing NUT entities remain available for their history cards.

Updates register the current card resource but never regenerate the saved layout. Calendar choices, wake-test evidence, UPS settings, phones, AI choices, and personal cards are kept. **Recent activity → Restore default Pi cards** replaces the Pi cards while keeping other cards and dashboard metadata. It does not erase dates or reset settings.

This remains a preview. Automated checks use simulated Pi/UPS/phone services and real Home Assistant APIs. The maintainer reports the rc.3 dashboard working on their Pi 5. Observe this cleanup on the actual Pi and with a first-time user before claiming the beginner-release requirement complete.
