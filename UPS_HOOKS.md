# Power hooks and UPS recovery

Version 0.6 retains UPS monitoring and an opt-in **host** shutdown policy, with separate timed RTC retries and emergency protection. Planned retries are written into the existing Home Assistant Calendar. Native Enable buttons change the selected NUT device's Home Assistant sensor availability, not UPS settings. No UPS output command or external executable is loaded. See UPS_RECOVERY.md.

## First provider: NUT through Home Assistant

NUT supplies the hardware-driver/manufacturer abstraction. A driver talks to a supported UPS over USB, serial, SNMP, Modbus, or another supported connection; the NUT server publishes normalized variables and commands. Home Assistant's NUT integration connects to that server. Its host/port are the **NUT server**, not necessarily the UPS IP; the NUT protocol normally uses port 3493.

The app uses a fixed Home Assistant template to collect entities belonging to the actual `nut` integration, grouped by device ID. It does not infer integration identity from names. It recognizes raw **Status data** (`OL`, `OB`, `LB`, etc.) with bounded uppercase auxiliary flags, including `OL TEST`; translated status and conflicting power flags do not establish power state. Battery charge requires an unambiguous percentage measurement with battery device class. Seconds units alone do not distinguish remaining runtime from shutdown/start delays, so runtime is explicitly selected.

The fixed Core WebSocket proxy lists registered NUT sensor entities, including disabled ones. Enable rechecks the entity's integration and saved device, sends only `disabled_by: null`, and validates the returned entity entry. Home Assistant manages reload/restart requirements. The app does not enable other integrations, disabled devices/config entries, or sensors during a known outage. Runtime annotations use native translation/unique metadata only as an aid; they do not authorize runtime selection or infer a UPS command.

1. Configure a NUT server for the UPS and confirm the driver detects the actual model and firmware. The NUT integration does not contain a UPS driver/server.
2. Add **Network UPS Tools** through Home Assistant's integration screens using that server's address. Do not point the integration at an APC SmartConnect/cloud port as though it were a NUT server.
3. Enable **Status data**, **Battery charge**, and wanted diagnostics on the native device page or through **UPS → Additional NUT readings you can enable** after saving the source. NUT diagnostics are often disabled by default. Wait for NUT to reload/readings to return before testing protection.
4. In Pi Wake & Sleep, choose **Find power sources**, select the UPS that actually powers this Pi, enable notices if desired, and save.
5. Verify that the monitor changes between utility and battery using the device's supported test procedure before planning automatic control. Keep critical loads in mind; the app itself sends no UPS command.

The supplied APC 990-91081C operation manual covers the SMTL1500RM3UC family and documents USB, optional NMC, and local Modbus/TCP settings, plus automatic restart after a software-requested UPS shutdown. If applicable to the installed model, this is a possible hardware recovery path, not proof that a particular NUT driver/build exposes it. The exact model, connection, supported commands, outlet group, firmware, and physical restore behavior must be verified. The current public `apc_modbus` documentation is USB-oriented; do not assume every shipped NUT build supports TCP or the same commands. An independent APC/local Modbus integration can publish the hook below as another provider.

## Version 1 hook contract

A Home Assistant integration or adapter publishes a **sensor** with a nested `rtc_wake_power` attribute. No plugin executable is loaded into this privileged app. A producer can be a native/custom Home Assistant integration or a local MQTT integration exposing these attributes. End users install the provider using its supported Home Assistant setup flow; they do not paste the developer JSON below into the app.

```json
{
  "rtc_wake_power": {
    "schema_version": 1,
    "provider": "Example local UPS adapter",
    "observed_at": "2026-10-10T00:00:00+00:00",
    "power_state": "battery",
    "battery_percent": 45,
    "runtime_seconds": 1800,
    "low_battery": false
  }
}
```

- `schema_version`: integer `1`. Unknown versions are ignored with an actionable warning.
- `provider`: readable name. The stable identity is the Home Assistant sensor entity ID.
- `observed_at`: time-zone-aware ISO timestamp of an actual device observation, not the time a cached value was re-published.
- `power_state`: `mains`, `battery`, `off`, or `unknown`.
- `battery_percent`: optional finite number from 0 to 100; unknown means absent/null, never a fabricated zero.
- `runtime_seconds`: optional finite remaining-runtime estimate; a restart/shutdown delay is not runtime.
- `low_battery`: optional boolean; true means the device reports low battery.
- `shutdown_requested`: optional boolean; true means a device/controller reports imminent shutdown. An enabled, qualified local policy treats this as a final stop signal; publishing it does not enable control.

Publish at least once a minute while connected, and mark the entity unavailable on lost communication. Both the observation time and Home Assistant's last report must be within three minutes; observations more than ten seconds in the future are rejected. NUT status follows the same freshness limit. The app's own monitor cache expires after 90 seconds without a successful refresh. Unavailable/stale/conflicting data becomes Unknown; it does not become "power restored."

The producer must not put passwords, tokens, or private control URLs in the hook. Version 1 does not accept control callbacks, arbitrary service names, executable code, or automatic-restart claims. Provider data does not verify a recovery method. The user must qualify the RTC policy against the supply/wake test; UPS output restoration remains unverified. Publishing a `shutdown_return` flag cannot grant power-control permission.

Notifications are disabled by default. The user explicitly selects a source and enables notices. The app uses only `pi5_rtc_wake_power_status`; it does not dismiss another integration's warnings. On-battery warnings are deduplicated, low charge escalates the notice, unavailable readings show a connection warning, and utility power clears this app's warning. The local notification threshold does not change the UPS's hardware low-battery setting.

## Implemented RTC control and remaining UPS-output phase

Safe host shutdown and reliable recovery are distinct operations. Calendar schedule validation alone is insufficient for an outage policy.

| Power behavior after host shutdown | Recovery mechanism | Required evidence |
|---|---|---|
| UPS keeps supplying the Pi's input power | Arm RTC before graceful shutdown; wake later to check power | Physical RTC wake with this supply path and adequate battery reserve |
| UPS turns its output off | Verified UPS shutdown-and-return sequence; Pi boots when output is restored | Exact supported driver command, correct outlet/group, shutdown delay, and actual output-off/return test |
| Output is already absent or battery is exhausted | Wait for restored UPS output or an independent controller | RTC battery cannot start the Pi; software on the powered-off Pi cannot observe restoration |
| Recovery must react immediately while HA is off | NUT/controller on independently powered hardware | Controller remains available and can safely restore the Pi's specific supply |

The preferred long-outage path is the UPS's tested shutdown-and-return capability, often expressed by NUT as `shutdown.return`. This command is **not universal**. NUT explicitly requires shutdown/restart testing, and some devices can restart while utility remains absent. A NUT process on this same Pi also stops during host shutdown; it cannot serve as an always-running restore watcher. HAOS add-on shutdown is not proof that the ordinary Linux `upsmon` late-shutdown power-cut sequence executes.

A timed RTC retry is a fallback when power stays connected. The implemented safeguards and further UPS-output requirements are:

1. Explicit user confirmation that the selected source and controlled outlet supply this Pi, with an accepted recovery method and a physical test result bound to the device/firmware/connection.
2. Fresh input status and a shutdown reserve based on measured HAOS shutdown/boot time. Low reserve disables battery-consuming retries; a runtime estimate is advisory and must be validated for the actual load.
3. Graceful host shutdown through Supervisor. A UPS output-off delay must exceed the complete measured host shutdown time. No hard power-cut command should be guessed from a manufacturer or sensor name.
4. Bounded retry count and backoff persisted across boots, not an unlimited wake/shutdown loop. Reset the outage session only after stable, fresh utility power is observed.
5. After RTC wake, require a fresh observation before resuming normal scheduling. If still on battery, evaluate reserve and the retry limit; unavailable data never authorizes a power-restored assumption.
6. Claim each control attempt before acting; ambiguous shutdown/UPS responses must not be blindly repeated. Keep a verified wake alarm after an ambiguous host shutdown request.
7. When a retry is planned, record its off period in the same Home Assistant Calendar before arming it, so future wake dates remain visible there. Attempt counts and acknowledgements are operational metadata, not a second user schedule store. Emergency graceful shutdown must still work if Calendar is unavailable; in that case, no unrecorded RTC retry should be promised.
8. Notifications and a clear recovery status explaining whether restart comes from RTC, UPS output restoration, or requires manual action. A provider's capability claim alone is not a passing test.

Version 0.6 implements the RTC path through a fixed host-shutdown executor, with source/Calendar binding, Pi wake-test fingerprint, remaining-runtime selection, supply/final-stop acknowledgements, stable-power verification, persisted bounded attempts, and Calendar readback before arming. Each retry is conditional on its fresh reserve requirement. Cancelling RTC retries, failed RTC checks, and Calendar changes preserve separately enabled commissioned emergency protection for the same UPS. Fresh low-battery/forced-shutdown signals do not depend on runtime or RTC availability. Lost data in a known outage uses a bounded allowance and discounted last reserve. Emergency stops promise no verified timed restart and do not clear unrelated alarms.

The community NUT app's running state and `shutdown_host` setting are checked read-only; users must review other controllers and restart NUT after option changes. This is an ownership guard, not an explicit NUT shutdown handoff. NUT with Host shutdown off can stop its own app at its shutdown condition, removing readings. Full coordination, late output-cut/return, and driver/outlet testing remain outstanding. No vendor control callback is accepted. A monitoring driver or capability flag alone never guarantees recovery after a final stop.

Sources: [NUT project](https://networkupstools.org/), [Home Assistant NUT](https://www.home-assistant.io/integrations/nut/), [NUT usbhid-ups shutdown/restart](https://networkupstools.org/docs/man/usbhid-ups.html), [NUT configuration notes](https://networkupstools.org/docs/user-manual.chunked/ar01s06.html), [APC Modbus driver](https://networkupstools.org/docs/man/apc_modbus.html), [NUT app options](https://github.com/hassio-addons/app-nut/blob/main/nut/DOCS.md), [Core registry API](https://github.com/home-assistant/core/blob/dev/homeassistant/components/config/entity_registry.py), [Core proxy authentication](https://developers.home-assistant.io/docs/apps/communication/), [Pi RTC](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#real-time-clock-rtc).
