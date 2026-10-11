# Connect Home Assistant AI to Pi Wake & Sleep

Use your existing Home Assistant AI conversation agent, including local Ollama, to ask about this Pi and request changes. The bundled companion is a custom integration that contributes tools to Home Assistant's built-in **Assist** interface, alongside your normal home controls. No new AI account or API key is needed.

Requires **Home Assistant Core 2026.10 or newer** and a model that supports tool calls. The dashboard works with AI access off. Home Assistant's sentence-based agent and AI Task automations are not connected by these conversation tools.

## Connect through Home Assistant screens

1. Install/update the same app and connect its dashboard following [INSTALL.md](INSTALL.md) or [UPDATE.md](UPDATE.md). The included companion is shared by the dashboard and Assist.
2. On the dashboard's Assist card, select **Connect Assist** and confirm status access. AI change requests remain off.
3. In your existing AI integration, such as local Ollama, choose **Assist** under **Control Home Assistant**. Keep your existing conversation agent and voice devices.
4. Ask “When will the Home Assistant Pi next shut down and wake?”
5. If wanted, open **Assist settings**, enable change requests, and save. Requests wait for review/approval on the card.

Turning AI access off keeps the dashboard available. Companion updates/reconnection use **Open Web UI → Maintenance and connection repair**, followed by a Home Assistant restart only if requested.

## What you can ask

| Example | Result |
|---|---|
| “How long has the Home Assistant Pi been awake?” | Current host uptime. |
| “When are the next shutdown and wake?” | Saved Calendar dates, or an explanation that scheduling is off/paused or no current event is available. |
| “What is the UPS battery level and remaining runtime?” | The selected UPS's fresh available readings; missing values stay unknown. |
| “Schedule the Pi off tonight from 11 PM until 7 AM tomorrow.” | A draft with exact shutdown/wake dates and time-zone offsets, awaiting approval in the app. |
| “Turn Pi Calendar scheduling off.” | A request awaiting approval. Calendar events and UPS protection are kept. |
| “Run a wake test” or “Reboot the Home Assistant Pi.” | A request awaiting approval. |
| “Cancel the Pi's current shutdown countdown.” | Immediate cancellation of an ordinary countdown when change access is enabled. Future events and emergency UPS protection remain active. |

The app supplies its display time zone and current time. AI should clarify ambiguous dates/times. Requests require exact offset-bearing dates, a shutdown at least two minutes ahead and within 30 days, and a wake ten minutes to seven days later. Calendar is checked again at approval.

## Review a change

Open **Assist → Requests to review**, read the exact dates or operation, then select **Approve request** and confirm. **Dismiss** discards a draft. Unapproved drafts expire after ten minutes or an app restart.

Approved dates are saved and read back in **Home Assistant Calendar**. Saving an event does not enable scheduling. Drafts cannot execute themselves and there is no second schedule store. This first AI tool set creates single off periods; edit repeats, existing events, and cancellations in the native Calendar editor.

If a Calendar save response is uncertain, the same request is never submitted twice. Use **Check saved event** and inspect Calendar. An approved write awaiting confirmation stays reviewable rather than expiring as an unapproved draft. Dismissing it does not remove a possibly saved event.

AI cannot approve its own request, confirm a physical wake test, change firmware, select a different UPS, disable emergency protection, run arbitrary commands, or call arbitrary services through these tools. Existing RTC/UPS checks still apply. Assist’s current-countdown cancellation cannot cancel emergency low-battery shutdowns. The dashboard’s confirmed global Keep awake switch suspends all app shutdowns until resumed.

## Updates and access

Updates retain Assist consent, the connection, Calendar selection, wake evidence, UPS policy, and phone settings. If the companion changes, select **Connect Assist** again and restart Home Assistant when requested. Customized or unfamiliar companion files are kept and produce an action message.

To revoke access, turn off **Allow Assist to read Pi, Calendar, and selected UPS status** and save. The private API immediately stops returning status details and refuses new changes; the tool list refreshes within about 30 seconds. Already approved Calendar events remain. Remove the companion integration in Devices & services if you no longer want it loaded.

The app mounts Home Assistant's configuration folder for installation of its fixed files under `custom_components/pi5_rtc_wake`. It does not edit `configuration.yaml`, automations, scripts, or other integrations. Credentials stay in private app data and the Home Assistant integration entry, excluded from UI and AI responses. The authenticated API uses the private app network, with no published host port. Discovery runs separately from RTC/UPS control.

## Connection help

- **Core update needed:** use Settings → System → Updates, then try Connect Assist again.
- **Configuration folder unavailable on 0.8.0-rc.1:** update the same app to **0.8.0-rc.2**. This fixes an app folder-mapping error. Stop and then Start the app, reopen Assist, and select Connect Assist. Reinstalling the app or editing Home Assistant files is not required.
- **Configuration folder still unavailable on 0.8.0-rc.2:** Stop and then Start the app to apply its updated mapping. Confirm the Web UI footer shows rc.2; if the error persists, contact the maintainer with the app version and displayed error.
- **No discovered integration:** restart Home Assistant after installing the companion, keep the app running, wait for its discovery retry, and reopen Devices & services.
- **AI answers without a tool call:** choose Assist in the AI integration's Control Home Assistant setting, confirm its model supports tools, and confirm your voice assistant uses that agent. Assist's debug/trace view shows tool calls.
- **Change request refused:** enable and save change requests in the app, then review the requested action there.
- **Calendar or UPS data unavailable:** check the source integration and the app's Calendar/UPS section. Missing data does not establish a healthy battery or a scheduled wake.

Automated native-interface checks run actual Home Assistant 2026.10.1 with simulated Pi/UPS services. A real HAOS companion installation and an actual AI/voice conversation still need observation.

[Home Assistant LLM tools](https://developers.home-assistant.io/docs/core/llm/) · [Ollama integration](https://www.home-assistant.io/integrations/ollama/)
