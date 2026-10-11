# Set up UPS shutdown and RTC recovery

Version 0.6 provides separate opt-in timed RTC retries and emergency low-battery protection for the **Pi running Home Assistant OS**. It requests graceful host shutdown. Verified timed wakes use the Pi 5 RTC and Home Assistant Calendar. It does not switch UPS outlets or send NUT shutdown/output commands.

Since 0.9.0-rc.3, the dashboard's **Keep awake** switch suspends **all** shutdowns from this app, including emergency UPS shutdowns. It survives restarts until **Resume shutdowns** restores the saved policy. It does not stop NUT or other apps from issuing independent shutdowns. This global switch is different from the existing **Pause timed retries** or Assist's current-countdown cancellation, which leave emergency protection active. See [DASHBOARD.md](DASHBOARD.md#keep-awake).

## Update first

Follow UPDATE.md to update the same app to 0.10.0-rc.1 and update its dashboard companion. Your Calendar, NUT selection, notifications, settings, and wake evidence are preserved. New control starts **off**. An enabled older policy is paused until shutdown ownership is reviewed and saved in the UPS section. Update and review while utility power is available.

## Home Assistant setup

1. Open the dashboard’s **UPS power** card. Confirm the saved power source is the UPS supplying this Pi and that fresh utility/battery readings appear.
2. Expand **Enable additional NUT readings** on the card. Enable **Battery runtime** if disabled, accept the confirmation, wait for readings to return, and select **Refresh UPS readings**. Home Assistant may reload NUT; follow the message if it requires a Home Assistant restart instead. The linked UPS device page is available as a fallback. Sensor changes are blocked during a known outage.
3. Select **Set up protection** or **Protection settings** on the same card. Select the remaining **Battery runtime** reading. Low battery runtime, Minimum runtime to start, and startup/shutdown delays are different readings. A compatible hook supplies typed runtime automatically.
4. Review **Who shuts down this Pi?** and any other controllers. For timed retries, turn off the community NUT app's **Host shutdown** option and restart NUT. Confirm that review on this screen. See the ownership limits below.
5. For timed retries, select a dedicated writable Local Calendar in **Calendar**, retain **Allow timed RTC retries during an outage**, and confirm a wake test on this exact continuous UPS supply path. Normal Calendar scheduling can be off while UPS protection is enabled.
6. Review the runtime requirement table. Early shutdown is optional under **Advanced recovery settings**. Keep emergency protection enabled if you want a graceful low-battery stop even when timed retries are paused. For emergency protection only, uncheck timed retries; RTC and Calendar readiness are then unnecessary.
7. Confirm the final-stop limit, enable **Automatic UPS protection**, select **Save UPS protection**, and accept the enable confirmation while utility power is available.

Emergency protection is qualified against the saved UPS/device identity and reviewed shutdown ownership. RTC retries also require the selected Calendar and current confirmed Pi wake settings. Changing Calendar or losing RTC readiness pauses retries while commissioned emergency protection remains active for the same UPS. Changing UPS turns control off and requires new qualification; source changes are blocked during a known outage. A separate ten-minute test turns normal scheduling and UPS control off; review and re-enable afterward.

## Shutdown ownership

The app reads the community NUT app's `shutdown_host` setting and running state without changing them. A conflict, stopped NUT app, unreadable setting, or stale ownership check blocks timed retries. Other NUT installations/controllers require manual review; absence of the community app is not proof that no other controller exists. Confirm that NUT was restarted after an option change because it chooses its shutdown command at startup.

NUT's Host shutdown on permits an independent host stop; off stops the NUT app at its own shutdown condition. Neither is a complete RTC preparation handoff. This release does not intercept every external shutdown, acknowledge NUT events, or perform the UPS's late output-cut/return sequence. A previously commissioned emergency stop remains available if an ownership check later fails, but that cannot eliminate a competing controller or guarantee timing. Keep long-outage use supervised until the full path has been tested.

## Default policy

| Setting | Default | Meaning |
|---|---:|---|
| Shutdown runtime threshold | 30 minutes | Keep HA on until estimated remaining runtime reaches this threshold |
| Early battery-saving shutdown | Off | Optional: also stop after an outage lasts 5 minutes |
| First RTC retry | 15 minutes | Planned off-period length; shutdown normally has an additional 30-second countdown |
| Increasing intervals | 15, 30, 60 minutes | Double after each retry, capped at the selected maximum of 120 minutes |
| Maximum RTC retries | 3 per outage | Attempts survive app/host restarts; cancellation and failed planning consume a retry |
| Runtime reserve after retry | 5 minutes | Retry must cover the wait, 3-minute boot/readings allowance, this reserve, and one additional minute |
| Low-battery charge threshold | 20% | At/below this or a device low-battery/forced-shutdown signal, enabled emergency protection uses a final stop |
| Emergency runtime reserve | 5 minutes | Enabled emergency protection stops at/below this even if RTC retries are paused |
| Boot/readings allowance | 3 minutes | Budget for boot; also the maximum wait for missing readings in a known outage |
| Stable utility power | 2 minutes | Fresh, uninterrupted utility readings are required before resetting the outage and resuming Calendar scheduling |

These are adjustable policy durations and thresholds, not a second store of dates. A UPS runtime estimate depends on load and is not a guarantee; allow for this Pi's actual shutdown/boot duration and the other loads on the UPS. Increase the allowances if measured startup/shutdown takes longer.

| Conditional attempt | Off interval | Minimum estimated runtime at that decision |
|---|---:|---:|
| First | 15 minutes | 24 minutes |
| Second | 30 minutes | 39 minutes |
| Third | 60 minutes | 69 minutes |

Requirements include the off interval + 3-minute boot allowance + 5-minute reserve + one minute. They are not a promise to complete all three attempts. Starting at 30 minutes normally supports only the first at unchanged load; later attempts depend on the fresh estimate after wake. The screen recalculates this table as settings change.

## What happens

On battery, normal Calendar shutdowns pause. At the threshold—or optional early delay—the app evaluates reserve. If another retry is safe, it saves a timed **UPS RTC retry: Pi off** event in your selected Calendar, reads it back, arms that event's end time, and begins the countdown. It checks Calendar and UPS reserve again before graceful shutdown.

After wake, it waits for UPS observations from this boot. Fresh stable utility power keeps the Pi running and resumes regular scheduling. If still on battery with enough reserve, the next Calendar-backed retry is longer. A returned-power reading during countdown cancels the shutdown.

No retry is scheduled if reserve is insufficient, retries are exhausted, or low battery is signaled. Separately enabled emergency protection remains available with paused retries or failed RTC/Calendar checks. A fresh low-battery or forced-shutdown signal does not wait for a missing runtime sensor. In a known outage, lost readings cause an emergency stop after the allowance, or sooner if the last observed reserve is nearly exhausted. Unknown readings before any known outage do not invent an outage or authorize a stop.

A **final graceful shutdown has no verified timed wake**. If the UPS keeps supplying the halted Pi, utility power returning alone does not restart it. Recovery needs a tested output-off/return path that boots the Pi, an external controller, a power cycle, or the Pi's power button. This release does not configure or verify UPS shutdown-and-return. An unrelated existing alarm is preserved, but is not this policy's verified recovery mechanism.

Final stops are recorded as short Calendar records when time and Calendar permit; their end is **not** a wake time. Critical reserve below two minutes or a forced-shutdown signal skips optional Calendar/notification calls and the countdown. An aging runtime observation is discounted by its age; the last observed reserve and observation time survive app restarts. These are past telemetry/operational records, not future wake dates. An emergency stop may be unrecorded if recording would delay it. Future wake dates stay exclusively in Calendar.

## Cancellation and errors

**Cancel this retry** cancels an ordinary UPS countdown and pauses timed retries for that outage. **Pause RTC retries for this outage** does the same before a countdown. Separately enabled emergency low-battery protection stays active, including if reserve later becomes low. A current emergency countdown cannot be cancelled; fresh utility power can still cancel it before the host request. Fresh stable utility power clears an outage pause.

Disabling emergency protection or the whole active policy requires a separate confirmation. Disabling timed retries alone does not disable emergency protection. Ordinary Calendar/test countdowns retain **Keep Pi awake**, which cancels that occurrence/test.

A retry that cannot be verified in Calendar leaves the Pi on; the creation request is never blindly repeated. Critical reserve still permits a final stop. Calendar-created UPS events are not replayed by the ordinary scheduler, including cancelled/interrupted attempts.

An uncertain host shutdown response preserves the verified wake alarm and prevents automatic repetition on the same boot. If the Pi stays on, use Check again after two minutes to review it; the outage attempt remains paused. Unavailable readings never mean power restored.

Recovery notices use this app's own Home Assistant notification. They explain active/paused/final states and clear when there is no remaining warning, protection is disabled, or fresh utility power is stable.

## Physical acceptance still required

The earlier wake test and 0.4 NUT screenshot do not prove the new registry controls or a full UPS outage/retry cycle. Verify native sensor activation/reload, Calendar event creation, shutdown ownership, measured shutdown/boot time, fresh readings after boot, and wake on this actual UPS while on battery. Test cancelled retries followed by low battery, RTC failure followed by emergency shutdown, and final-stop restoration with a controlled load and a recovery method available. Recheck after changing supply hardware, UPS firmware/connection, or output-control software.

The RTC battery only maintains the clock. RTC wake needs main input power. If the UPS output disappears or its battery exhausts, the alarm cannot boot the Pi. The computer running NUT on this same Pi is also off; immediate power-return monitoring requires a controller that stays powered.

Sources: [NUT app configuration](https://github.com/hassio-addons/app-nut/blob/main/nut/DOCS.md), [NUT startup command selection](https://github.com/hassio-addons/app-nut/blob/main/nut/rootfs/etc/cont-init.d/nut.sh), [Pi RTC](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#real-time-clock-rtc).

