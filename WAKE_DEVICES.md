# Wake other devices

The optional **Wake other devices** card uses the **Wake on LAN buttons you already have in Home Assistant**. It can send a request when you select **Wake selected**, or automatically after the Pi starts. Automatic waking starts **off**.

The Pi wakes through its RTC first. Home Assistant must be running to send requests to other devices. Wake on LAN support on the target computer, its network adapter, and the network is required. The card does not turn off other devices or control PoE ports.

## Choose and test a device

1. Open **Pi Wake & Sleep → Wake other devices → Choose devices**.
2. Select **Add Wake on LAN device** if you have not configured it already. Home Assistant asks for the computer's MAC address and any optional network settings. Enable Wake on LAN in that computer's firmware and network adapter settings too.
3. Return to the card and select **Find devices**. Select the devices you want, up to twelve.
4. Optionally select **Add Ping online check** in Home Assistant, enter the target's address there, then **Find devices** again. Choose that computer's Ping sensor beside its wake button. The association is your choice; the app cannot infer reliably that two entities refer to the same computer.
5. **Only wake on utility power** uses the UPS already selected on the UPS card. It waits for a fresh reading from this Pi boot showing utility power. Choose a UPS, or turn this option off if you do not use one.
6. Select **Save device settings**. Saving sends no wake request. With the target asleep, select **Wake selected** and confirm.

Use **Cancel** to return without saving. Settings and expanded Timing details stay open through normal dashboard refreshes. **Find devices** preserves your draft. Administrators choose devices and send requests; other Home Assistant users can view results.

## Understand the result

| Card result | Meaning |
| --- | --- |
| Requested | Home Assistant accepted the button press. No online check was selected. |
| Checking… | A request was accepted; waiting for the selected Ping sensor. |
| Reachable | A fresh Ping reading after the request says the target is reachable. |
| Not confirmed | The service response was uncertain, a check was interrupted, or no fresh online confirmation arrived before the timeout. Check the target before retrying. |
| Needs attention | The button or Ping sensor changed, was disabled, or is unavailable. Find devices and review the selection. |

A button press does not prove a successful boot. Ping confirms network reachability at the recorded time, including for a device that was already awake; it does not prove a particular application is ready. Results are from the last run, not continuous device monitoring. Restored or stale Ping readings never confirm reachability. An unchanged `on` state can confirm a later request only when Home Assistant reports a fresh observation.

## Enable automatic waking

After testing, open this card's **Settings**:

- **Enable automatic waking:** Starts with the next qualifying Pi boot, never the current boot when you save.
- **After a scheduled Calendar wake:** Uses the recorded, verified Calendar shutdown's RTC wake time. A host boot must fall from 30 seconds before to five minutes after that time. App restarts, ordinary manual Pi boots, the ten-minute wake test, and UPS recovery retries do not qualify for this choice.
- **After every Pi boot:** Also includes manual restarts and UPS recovery boots. Use the utility-power condition to avoid waking extra loads on UPS battery.
- **Only wake on utility power:** Applies to automatic and manual requests. Unknown, stale, on-battery, or prior-boot UPS readings block waking.
- **Timing:** Startup delay defaults to 60 seconds (30–600 allowed). Ping confirmation wait defaults to 120 seconds (15–300 allowed).

Home Assistant and required utility-power readings have up to fifteen minutes from app startup to become ready. If they do not, the automatic run is skipped for that host boot. Use **Wake selected** later. No new dates or recurring schedules are created outside Home Assistant Calendar. A small historical shutdown receipt identifies the completed Calendar action.

There is one automatic attempt per host boot. Requests are claimed on disk before sending, and uncertain responses are never retried automatically. App restarts do not resend an already claimed run. A fresh device-registry check verifies that a saved entity still represents the selected native Wake on LAN button. Missing selections are never silently substituted.

Device requests and Ping checks run separately from Pi/UPS power control. A pending Pi shutdown or reboot stops new requests and online checks. An already submitted request cannot be recalled. **Keep awake** continues to suspend the Pi's shutdowns; it does not turn off monitoring or prevent manual device waking.

## Updating an existing dashboard

Update the same installed app to **0.10.0-rc.1**, **Stop → Start**, then **Open Web UI → Maintenance and connection repair → Update / reconnect dashboard**. Restart Home Assistant if requested and refresh the browser.

The new card is added once without replacing your pictures, graphs, other cards, or settings. If you remove it later, normal reconnection does not add it again. Restore it individually with **Edit dashboard → Add card → Pi Wake & Sleep · Wake other devices**. Automatic waking remains off until you explicitly enable it. Your existing Pi wake test remains valid when firmware and wake settings have not changed.

This is a preview. Test actual target waking and reachability on your network before relying on an automatic sequence. See Home Assistant's [Wake on LAN](https://www.home-assistant.io/integrations/wake_on_lan/) and [Ping](https://www.home-assistant.io/integrations/ping/) setup guides.
