# Pi 5 Wake & Sleep 0.7.0-rc.2 — clearer setup guidance

If a new installation starts with Protection mode on, Setup now explains the next action instead of only saying it did not reach Home Assistant OS:

**Open Settings → Apps → Pi 5 Wake & Sleep → Info. Select Stop, turn Protection mode off, then select Start. Reopen Setup and select Check again.**

Older Home Assistant versions call Apps Add-ons. If Protection mode is already off and this sequence still fails, Details for support remain available. Access-denied errors use the same sequence.

[Install in Home Assistant](https://my.home-assistant.io/redirect/supervisor_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fcodefendant%2Fpi5-rtc-wake) · [Update guide](https://github.com/codefendant/pi5-rtc-wake/blob/main/UPDATE.md)

## Firmware and permissions

Home Assistant handles Pi firmware version updates. The app separately checks low-power wake settings and verifies the RTC alarm before a scheduled shutdown. An updated firmware version does not replace those checks. With the current architecture, Protection mode must stay off for host checks and RTC hardware access during operation. This repair changes guidance only; it does not reduce permissions or skip checks.

## Update

Update the same installed app and reload its Web UI. Calendar, UPS, phone preferences, and confirmed wake evidence are preserved. This guidance repair does not require another wake test unless firmware or wake settings changed.

The optional phone features from 0.7.0-rc.1 remain available in Messages. Use Send status now to check actual phone delivery; automatic wake messages start off.

## Verification

The local suite passes 303 simulated backend tests, including the reported container-OS error and recovery through Setup, plus DOM interaction and JavaScript syntax checks. Hosted browser, arm64 build, anonymous image download, and production-import checks gate publication. The maintainer confirmed that disabling Protection mode resolved the 0.7.0-rc.1 public-installation error; actual phone delivery and a new RTC-wake message remain unobserved.

Home Assistant is unavailable while the Pi is off. RTC wake needs continuous main power; the RTC battery keeps time but cannot boot the Pi. UPS output-return control and a complete NUT shutdown handoff remain unimplemented. See [VALIDATION.md](https://github.com/codefendant/pi5-rtc-wake/blob/main/VALIDATION.md) for the observed checks and limits.
