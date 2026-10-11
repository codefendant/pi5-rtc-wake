# Pi 5 Wake & Sleep 0.8.0-rc.2 — Connect Assist repair

Connect Assist in rc.1 could stop with "Home Assistant's configuration folder is not available" and return to "Not connected." The app expected `/homeassistant_config`, but Supervisor's default mount was `/homeassistant`. This preview explicitly maps the configuration folder to the installer's path and displays failed setup guidance beside the connection button.

[Install](https://my.home-assistant.io/redirect/supervisor_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fcodefendant%2Fpi5-rtc-wake) · [Update guide](https://github.com/codefendant/pi5-rtc-wake/blob/main/UPDATE.md) · [Connect Assist](https://github.com/codefendant/pi5-rtc-wake/blob/main/ASSIST.md)

## Update and connect

1. Update the **same installed Pi 5 Wake & Sleep app** to **0.8.0-rc.2**. If Update is missing, use the app store's **⋮ → Check for updates** and refresh.
2. **Stop** and then **Start** the app. Reopen/reload Web UI and confirm its footer shows rc.2.
3. Open **Assist → Connect Assist** and confirm. Restart **Home Assistant** from Settings → System if requested.
4. Open **Settings → Devices & services** and add the discovered **Pi Wake & Sleep** integration.
5. In the AI integration's **Control Home Assistant** option, select **Assist** alongside any existing custom APIs. Start a new chat using that AI agent and ask for the Pi's next shutdown and wake.

Requires Core **2026.10 or newer** and a model with tool support, such as a suitable local Ollama model. Status access starts on when connected; change requests start off. Approved dates remain in Home Assistant Calendar. Settings, Calendar selection, wake evidence, UPS policy, phone preferences, and existing Assist consent remain in schema 8. This repair does not require a new physical wake test.

## Verification scope

[Publishing run 38100690381](https://github.com/codefendant/pi5-rtc-wake/actions/runs/38100690381) passed all 327 simulated backend tests, Chromium interactions, the published YAML mount contract, actual Home Assistant 2026.10.1 discovery/platform/tool loading, the arm64 build, and a fresh anonymous image pull with production imports and version verification. A real HAOS Connect Assist installation and AI/voice response still need confirmation on the user's Pi after updating. No automated check reboots or shuts down real hardware or sends a phone notification.

Existing UPS long-outage recovery limits remain documented in [VALIDATION.md](https://github.com/codefendant/pi5-rtc-wake/blob/main/VALIDATION.md).
