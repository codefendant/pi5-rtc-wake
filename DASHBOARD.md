# Pi Wake & Sleep dashboard

The 0.9 preview adds a native Home Assistant dashboard. Move, resize, remove, and add cards with **Edit dashboard**, including ordinary pictures, history graphs, weather, and other Home Assistant cards. The app continues to run the RTC, Calendar, UPS, phone, and Assist functions.

## Connect once

1. Update the existing app, then **Stop → Start**. Open **Pi Wake & Sleep settings** or its **Open Web UI** button.
2. Select **Connect dashboard** and confirm. This installs or updates the bundled companion; it keeps your settings and does not turn on AI access.
3. Restart **Home Assistant** from Settings if requested. This is a Home Assistant restart, not the Pi reboot used during wake preparation.
4. In **Settings → Devices & services**, add the discovered **Pi Wake & Sleep** integration. An existing Assist companion is reused and its dashboard should appear after restarting Home Assistant.
5. Open **Pi Wake & Sleep** in the sidebar. Refresh your browser once if cards still show loading after companion setup finishes.

No terminal, YAML, personal API token, or extra card download is needed. AI access remains a separate choice. This uses Home Assistant's normal storage dashboard/resource mode; it does not change YAML-managed dashboards or resources.

## Guided Pi setup

The setup card begins with **Permissions → Pi checks → Wake test**. It checks Protection mode and links to the app's own Info page. The illustration highlights the switch: **Stop the app → turn Protection mode off → Start the app**. Checks continue automatically while the app is running.

Turning Protection mode off grants access; the Pi is marked ready only after the wake settings, clock, and successful wake test have been checked. Prepare wake settings only if requested, reboot the Pi if requested, then run and confirm the ten-minute test. An existing valid wake test is retained when firmware and wake settings have not changed.

Completed setup collapses into **Pi ready · Wake test passed**. **Review setup** opens the details again; **Back to dashboard** closes them. Leaving unfinished setup keeps a **Pi setup needs attention** strip and does not enable power operations. A new readiness problem brings the needed guidance back. Power operations show confirmations and require a Home Assistant administrator; other users can view status.

## Calendar

**Create Pi Sleep calendar** creates and selects a native Home Assistant Local Calendar named **Pi Sleep**. An existing Local Calendar with that original name is reused, including its dates. The actual entity ID is resolved rather than guessed. An already selected calendar is not replaced and scheduling is not silently enabled.

Alternatively, use **Choose existing calendar**. Changing calendars leaves scheduling off until reviewed. Use **Open Calendar** to enter dates and recurring events in Home Assistant: **event start = shutdown; event end = wake**. Turn **All day** off. Overnight events end on the following date. Periods must last ten minutes to seven days and must not overlap or touch.

Calendar remains the only store of scheduled dates. After reviewing events and passing the wake test, select **Enable scheduling** and confirm. Cards show local times and a countdown such as “in 2 h.” Paused or stale data is explained rather than shown as an active shutdown.

## Optional cards

- **UPS power:** Find and select the UPS supplying the Pi. Monitoring starts separately from automatic protection. Disabled NUT readings can be enabled from the card. **Set up protection** opens the existing detailed commissioning screen for shutdown ownership, runtime selection, and retry/emergency thresholds.
- **Messages:** Choose a discovered Companion app phone and up to twelve existing readings. Save and send a confirmed test message. Automatic wake messages are separately enabled. Each message includes uptime and the next shutdown/wake times.
- **Assist:** Enable status access, then select **Assist** in the existing AI agent's **Control Home Assistant** setting. Change requests are separately enabled and wait for approval in the card or app. Turning AI access off keeps the dashboard available.
- **Controls:** With no shutdown countdown, **Pause calendar** turns Calendar shutdowns off while retaining every date. **Resume calendar** asks you to review and confirm before enabling them again. During an ordinary countdown, **Keep awake** cancels that shutdown only; future dates are retained. These actions do not change emergency UPS protection. Emergency low-battery shutdowns cannot be cancelled here. **Reboot Pi** has a red background and requires confirmation.
- **Recent activity:** Collapsed by default; shows recent dashboard setup and action entries in plain language.

## Personalize and update

Select **Edit dashboard → Add card**. Pi cards have visual editors for their title and connected Pi. Nine read-only entities provide uptime, next shutdown/wake, UPS battery/runtime/power, wake readiness, Calendar scheduling, and emergency protection. Use them in standard graphs, tiles, and entity cards. Existing NUT entities remain available for their history cards.

Updates register the current card resource but never regenerate the saved layout. Calendar choices, wake-test evidence, UPS settings, phones, AI choices, and personal cards are kept. **Recent activity → Restore default Pi cards** replaces the Pi cards while keeping other cards and dashboard metadata. It does not erase dates or reset settings.

This remains a preview. Automated checks use simulated Pi/UPS/phone services and real Home Assistant APIs. Observe the revised interface on the actual Pi and with a first-time user before claiming the beginner-release requirement complete.
