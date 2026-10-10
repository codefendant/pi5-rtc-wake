# Connect Home Assistant AI to Pi Wake & Sleep

Use your existing Home Assistant AI conversation agent, including local Ollama, to ask about this Pi and request changes. The bundled companion is a custom integration that contributes tools to Home Assistant's built-in **Assist** interface, alongside your normal home controls. No new AI account or API key is needed.

Requires **Home Assistant Core 2026.10 or newer** and a model that supports tool calls. Calendar, UPS, setup, and phone functions remain available on earlier Core versions; Connect Assist explains the needed Core update. This feature adds conversation tools. Home Assistant's built-in sentence-based agent and AI Task automations are not connected by this feature.

## Connect through Home Assistant screens

1. Update the **same installed Pi 5 Wake & Sleep app** to **0.8.0-rc.1** and reload its Web UI.
2. Open **Assist → Connect Assist** and accept the explanation. It installs the companion and offers a connection through Home Assistant's authenticated Supervisor discovery. No address or token needs to be copied.
3. If prompted, restart **Home Assistant** from **Settings → System** to load the companion. A Pi reboot is not required.
4. Open **Settings → Devices & services**, find the discovered **Pi Wake & Sleep** integration, and select **Add/Configure**. Confirm the connection.
5. Open your existing AI integration's settings, such as **Ollama**, and select **Assist** under **Control Home Assistant**. Use that agent in your existing voice assistant or Assist chat.
6. Ask: **“When will the Home Assistant Pi next shut down and wake?”** Compare the answer with Overview.

Connecting starts with **status only**. To use controls, enable **Allow Assist change requests and countdown cancellation** in the app and save. These settings are consent for the app's tools; keep using Home Assistant's exposed-entities settings for household temperatures, lights, and other readings.

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

AI cannot approve its own request, confirm a physical wake test, change firmware, select a different UPS, disable emergency protection, run arbitrary commands, or call arbitrary services through these tools. Existing RTC/UPS checks still apply. Keep-awake cannot cancel an emergency low-battery shutdown.

## Updates and access

Updates retain Assist consent, the connection, Calendar selection, wake evidence, UPS policy, and phone settings. If the companion changes, select **Connect Assist** again and restart Home Assistant when requested. Customized or unfamiliar companion files are kept and produce an action message.

To revoke access, turn off **Allow Assist to read Pi, Calendar, and selected UPS status** and save. The private API immediately stops returning status details and refuses new changes; the tool list refreshes within about 30 seconds. Already approved Calendar events remain. Remove the companion integration in Devices & services if you no longer want it loaded.

The app mounts Home Assistant's configuration folder for installation of its fixed files under `custom_components/pi5_rtc_wake`. It does not edit `configuration.yaml`, automations, scripts, or other integrations. Credentials stay in private app data and the Home Assistant integration entry, excluded from UI and AI responses. The authenticated API uses the private app network, with no published host port. Discovery runs separately from RTC/UPS control.

## Connection help

- **Core update needed:** use Settings → System → Updates, then try Connect Assist again.
- **Configuration folder unavailable after updating:** Stop and then Start the app, reopen Assist, and try again.
- **No discovered integration:** restart Home Assistant after installing the companion, keep the app running, wait for its discovery retry, and reopen Devices & services.
- **AI answers without a tool call:** choose Assist in the AI integration's Control Home Assistant setting, confirm its model supports tools, and confirm your voice assistant uses that agent. Assist's debug/trace view shows tool calls.
- **Change request refused:** enable and save change requests in the app, then review the requested action there.
- **Calendar or UPS data unavailable:** check the source integration and the app's Calendar/UPS section. Missing data does not establish a healthy battery or a scheduled wake.

Automated native-interface checks run actual Home Assistant 2026.10.1 with simulated Pi/UPS services. A real HAOS companion installation and an actual AI/voice conversation still need observation.

[Home Assistant LLM tools](https://developers.home-assistant.io/docs/core/llm/) · [Ollama integration](https://www.home-assistant.io/integrations/ollama/)
