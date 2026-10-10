# Pi 5 Wake & Sleep 0.8.0-rc.1 — native Home Assistant AI tools

Use your existing AI conversation agent, including local Ollama, to ask about Pi uptime, next shutdown/wake dates, readiness, and selected UPS battery/runtime. The bundled companion adds tools to Home Assistant's native Assist API alongside ordinary home controls.

[Install](https://my.home-assistant.io/redirect/supervisor_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fcodefendant%2Fpi5-rtc-wake) · [Update guide](https://github.com/codefendant/pi5-rtc-wake/blob/main/UPDATE.md) · [Connect Assist](https://github.com/codefendant/pi5-rtc-wake/blob/main/ASSIST.md)

## Connect through screens

Requires **Home Assistant Core 2026.10 or newer** for this optional feature. Update the same installed app, open **Assist → Connect Assist**, restart Home Assistant if requested, and add the discovered **Pi Wake & Sleep** integration in Devices & services. Choose **Assist** under **Control Home Assistant** in your existing AI integration. No terminal, YAML, address, user API token, or new AI account is required.

Status access starts on when connected. Change requests start off. Enable them separately if you want AI controls. A tool-capable model and an AI conversation agent are required; this does not add tools to the built-in sentence-based agent or AI Task automations.

## Controlled changes and one Calendar

AI can request single off periods, scheduling on/off, wake tests, and reboots. Review exact dates or the operation in **Assist → Requests to review**, then approve it in the app. Approved dates are saved/read back only in Home Assistant Calendar. Recurrences and existing events stay in the native Calendar editor. Saving an event does not enable scheduling.

Ordinary current countdowns can be cancelled immediately when change access is enabled. Emergency low-battery protection and future Calendar events remain active. AI cannot approve its own request, confirm physical wake evidence, change firmware, disable emergency protection, or run arbitrary commands.

Companion installation updates only fixed owned files and preserves unrelated Home Assistant configuration. The authenticated private API publishes no host port and has no approval endpoint. Connection credentials are excluded from UI and tool responses. Turning Assist off revokes new access immediately.

## Update and verification

Existing Calendar, UPS, wake-test evidence, outage state, and phone settings migrate to schema 8 and are retained. AI access starts off on upgrade. Earlier Core versions can continue using the existing app functions. Future companion updates use Connect Assist and a Home Assistant restart.

326 simulated backend tests and local DOM/syntax checks pass. Publication is gated on the real Home Assistant 2026.10.1 native-interface check, Chromium, RTC ABI, arm64 build, anonymous image pull, and production imports. A real HAOS companion installation and actual AI/voice conversation remain to be observed. No automated check performs a real host power action or phone delivery.

The existing continuous-power requirement and UPS recovery limits remain. See [VALIDATION.md](https://github.com/codefendant/pi5-rtc-wake/blob/main/VALIDATION.md) for observed evidence and remaining checks.
