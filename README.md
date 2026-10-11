# Pi 5 Wake & Sleep

Schedule shutdown and automatic wake for the Raspberry Pi 5 running Home Assistant OS. Configure it through Home Assistant screens, and keep every date and repeat in Home Assistant Calendar.

**0.8.0-rc.2 · Public preview · MIT license**

[**Add to Home Assistant**](https://my.home-assistant.io/redirect/supervisor_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fcodefendant%2Fpi5-rtc-wake) · [Installation guide](INSTALL.md) · [Updates](UPDATE.md) · [Release notes](RELEASE_NOTES.md)

This preview fixes Connect Assist failing to find Home Assistant's configuration folder. Update the same app, Stop and Start it, and select Connect Assist again. See [ASSIST.md](ASSIST.md) for screen-only setup and supported requests, [VALIDATION.md](VALIDATION.md) for observed results, and [PUBLICATION.md](PUBLICATION.md) for the publishing process. Publication of the 0.8.0-rc.2 image is pending verification.

## Install and set up

1. Open **Add to Home Assistant**, add the repository, and install **Pi 5 Wake & Sleep** from the app store.
2. Turn off **Protection mode**, enable **Start on boot** and **Show in sidebar**, and start the app.
3. Open its Web UI and follow **Setup**. Prepare the Pi if requested, reboot, run the ten-minute wake test, and confirm the automatic return.
4. Choose a dedicated **Local Calendar** in **Calendar**. Open Home Assistant Calendar to add dates and repeats: **event start = shutdown; event end = wake**.
5. Review the upcoming list and enable scheduling.

No end-user terminal, API token, YAML automation, or extra dashboard card is needed. [INSTALL.md](INSTALL.md) gives the screen-by-screen path and help for blocked steps.

## Everyday use

| Section | What you do |
|---|---|
| Overview | Check readiness, UPS state, and the next scheduled off periods. |
| Calendar | Select the calendar, review dates, and open native Calendar editing. |
| UPS | Choose the power source, enable available NUT readings, and configure optional notices or shutdown protection. |
| Messages | Choose a Companion app phone and readings, preview/send status, and enable optional messages after Pi boot. |
| Assist | Connect your existing AI agent, ask status questions, and review requested Calendar changes or Pi operations. |
| Setup | Review Pi checks, preparation, reboot, and wake-test evidence when needed. |

After a confirmed wake test, Overview opens by default. Setup returns when a problem needs attention. Details stay collapsed until needed.

## Calendar scheduling

Home Assistant Calendar is the only schedule store. Use timed events, with **All day** off. For an overnight period, choose the next day as the event end. Off periods must last ten minutes to seven days and must not overlap or touch. The app shows the next ten occurrences within 31 days and refreshes about every 30 seconds.

Before shutdown, the app rechecks the event and verifies an RTC alarm for its exact end. Changed, deleted, unavailable, or stale Calendar data keeps the Pi on. **Keep Pi awake** cancels that occurrence. An interrupted countdown is not retried after restart, and firmware or wake-setting changes require a new test.

## UPS monitoring and optional protection

A NUT server communicates with the UPS; Home Assistant's **Network UPS Tools** integration supplies its readings. In **UPS**, select **Find power sources**, choose the source supplying this Pi, and save. Power notices and automatic shutdown protection are opt-in.

**Additional NUT readings you can enable** activates actual disabled sensors on the selected NUT device. The app explains any reload or Home Assistant restart needed. Device-level disablement is handled on the linked native device page. Auxiliary status such as `OL TEST` is accepted; conflicting status remains Unknown.

Optional protection uses an explicitly selected runtime sensor and reviewed shutdown ownership. Conditional RTC retries are separate from emergency low-battery protection: cancelling a retry or failing an RTC check preserves commissioned emergency protection for the same UPS. Default 15/30/60-minute retries require at least **24/39/69 minutes** of estimated remaining runtime at each decision; a 30-minute threshold normally funds only the first retry at unchanged load.

See [UPS_RECOVERY.md](UPS_RECOVERY.md) for the policy and setup. Developers can publish compatible Home Assistant sensor data using [UPS_HOOKS.md](UPS_HOOKS.md); external executable hooks are not loaded into this privileged app.

## Phone messages

In **Messages**, select **Find phones and readings**, choose your Home Assistant Companion app phone, and optionally choose up to twelve existing readings. Every message includes Pi uptime and the next shutdown/wake times, or explains why no time is planned. Preview a draft without sending, save, and use **Send status now** to check your phone. Enable **Send a message after this Pi starts** for the next host boot; app restarts do not duplicate a wake message.

Suggestions use native entity types, device classes, areas, visibility, and the selected NUT UPS. They do not copy the exact dashboard summary order. For today's energy, select an existing daily sensor. Delivery uses the Companion app's existing connection and may use local or Apple/Google push; acceptance by Home Assistant is not a delivery receipt. Phone work is separate from the RTC/UPS worker. See [PHONE_MESSAGES.md](PHONE_MESSAGES.md).

## AI and voice interaction

Requires Core **2026.10 or newer** for the optional native tool platform. Select **Assist → Connect Assist**, restart Home Assistant if requested, and add the discovered companion integration. Choose **Assist** under **Control Home Assistant** in your existing AI integration, such as local Ollama. No end-user token, YAML, terminal, or new AI account is needed.

Start with Pi uptime, next shutdown/wake dates, and selected UPS status. Change requests start off. When enabled, dates, scheduling changes, wake tests, and reboots wait for approval in the app. Approved dates go only into Home Assistant Calendar. Cancelling an ordinary current countdown preserves future events and emergency UPS protection. Other household readings use your normal Assist exposed entities. See [ASSIST.md](ASSIST.md).

## Power and firmware

While this Pi is off, Home Assistant and its automations are unavailable. RTC wake needs continuous main input power. An RTC battery keeps time; it cannot boot the Pi. If the UPS switches output off, restart depends on restored output or an independently powered controller.

This app does not switch UPS outputs or implement a complete NUT shutdown handoff. A final emergency stop has no verified timed wake, and utility power returning does not restart a halted Pi whose input stayed powered. Test the actual UPS output-return path before relying on unattended long-outage recovery.

Keep this app's **Protection mode off** during use so it can check the host wake settings and access the built-in RTC. An updated firmware version does not verify or configure low-power wake settings. Home Assistant's Raspberry Pi integration handles board firmware version updates. This app separately checks/prepares `POWER_OFF_ON_HALT=1` and `WAKE_ON_GPIO=0`, preserving boot order and backing up the current settings. Pending updates or unsupported preparation produce an action message. A required reboot appears in Home Assistant Notifications and in Setup.

## Validation and development

The maintainer tested **0.6.0-rc.1** on their Pi 5 and confirmed that disabling Protection mode resolved the **0.7.0-rc.1** installation error. **326 simulated backend tests**, DOM/JavaScript/RTC ABI checks, actual Home Assistant 2026.10.1 companion/tool checks, Chromium, arm64 build, anonymous image download, and production imports pass. [Publishing run 38075883994](https://github.com/codefendant/pi5-rtc-wake/actions/runs/38075883994) records the results. Live companion setup and an AI/voice conversation, actual phone delivery, novice setup, and the remaining UPS hardware checks still need observation.

[VALIDATION.md](VALIDATION.md) separates observed results from remaining checks. [ACCEPTANCE.md](ACCEPTANCE.md) records novice installation/update and physical checks required before removing the preview label. [PUBLICATION.md](PUBLICATION.md) describes the public-release process.

```sh
python3 -m unittest discover -s tests -q
node tests/ui_logic.cjs
```

`python3 tools/preview.py` starts a loopback-only simulated UI and performs no real power operation. Production excludes that preview and the tests.

## License and sources

Distributed under the [MIT License](LICENSE).

[Home Assistant Calendar](https://www.home-assistant.io/integrations/local_calendar/) · [NUT integration](https://www.home-assistant.io/integrations/nut/) · [NUT project](https://networkupstools.org/) · [Pi RTC](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#real-time-clock-rtc) · [Raspberry Pi integration](https://www.home-assistant.io/integrations/raspberry_pi/)
