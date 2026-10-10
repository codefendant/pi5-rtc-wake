# Validation — 10 October 2026, 0.7.0-rc.1

## New phone-message behavior

The 0.7 preview adds optional phone wake/status messages. The maintainer's successful Pi report below applies to the earlier 0.6 app. Actual Companion app delivery and an actual RTC-wake message have not been observed for 0.7.

Local verification passes **301 Python unittest cases**, including 42 new phone cases, expanded DOM interaction checks, and JavaScript syntax. Phone tests cover current/legacy action contracts, discovery and native visibility/area metadata, explicit phone/send consent, safe field selection, draft preview, schedule/UPS message semantics, actual host uptime, current-boot/restored/unavailable observations, bounded waiting, persistent claims before I/O, ambiguous delivery, failed persistence, app restart deduplication, schema-6 preservation, and a blocked phone request while the shutdown worker completes. All phone deliveries and Pi operations in these tests are simulated.

The browser smoke script now covers phone discovery, field selection, preview without sending, saving, send confirmation, simulated delivery, reload persistence, and mobile width. Hosted Chromium, arm64 build, and anonymous production-image verification are pending for this source version until recorded below.

New files are standard-library code plus documentation/tests; production dependencies, ingress authorization, RTC preflight, UPS policy, Calendar ownership, and native firmware handling are unchanged. Schema 7 retains schema-6 settings and introduces disabled phone preferences plus historical boot-attempt metadata. No future phone/schedule dates are persisted outside Calendar.

Remaining acceptance: actual phone delivery on the user's selected connection, RTC-wake notification, same-boot add-on restart without duplicates, internet/local-network outage behavior, novice setup, and the existing fresh-install/UPS output-return checks in ACCEPTANCE.md.

## Earlier 0.6.0-rc.1 validation


## Public-preview preparation

On 10 October 2026 the maintainer reported, "This release checks out on my Pi 5," and authorized public release. This report applies to 0.6.0-rc.1; it does not identify every exercised UPS failure or output-return case.

The publication package preserves every application Python file and web asset from the tested ZIP. Its manifest adds only repository/image fields. The Dockerfile additionally copies the MIT license; dependencies and startup are unchanged. Other publication changes are documentation, repository metadata, pinned CI actions, a main-branch manual publishing option behind the existing checks, and an anonymous arm64 image/import check.

Original tested ZIP SHA-256: `c32c90008d3b76d5e2a201f4e81ad2a8af8a5fc1c1b7b656828adc711ca2e95f`.

The source is now committed to the public repository. The first hosted run, [38030570751](https://github.com/codefendant/pi5-rtc-wake/actions/runs/38030570751), passed all 259 backend tests, DOM interactions, JavaScript syntax, and the compiled ABI check. Chromium installed successfully; the browser script then failed on an exact label selector for a wrapping dropdown containing option text. That test now matches the stable label prefix for Calendar and UPS selectors without changing app code. The public-image workflow also needed its temporary Docker configuration path moved out of an unsupported job-level runner expression.

The updated publishing workflow supports an explicit main-commit release marker, an anonymous image gate, and automatic preview/tag creation only after that gate succeeds. Local syntax checks, ten publish-condition cases, and six simulated release API cases pass, including duplicate prevention, refusing a mismatched tag, and failing on authorization errors.

## Verified public publication

- [Publishing workflow 38031186599](https://github.com/codefendant/pi5-rtc-wake/actions/runs/38031186599) completed successfully on 10 October 2026 at 06:32 UTC. Backend tests, DOM checks, JavaScript syntax, RTC ABI, real Chromium smoke test, arm64 build/push, anonymous image verification, and preview creation all passed.
- Release/tag: [v0.6.0-rc.1](https://github.com/codefendant/pi5-rtc-wake/releases/tag/v0.6.0-rc.1), published as a non-draft pre-release, targeting commit `890427491b8311616e74df8f6058e0251357c337`. The tag's commit was read back and matches that verified publishing commit.
- Image: `ghcr.io/codefendant/pi5-rtc-wake-pi5-rtc-wake-aarch64:0.6.0-rc.1`. Pushed and anonymously pulled digest: `sha256:9b38d105188464d24dea50a50350296ccc7cb74206814e342ae7f0b65992a739`.
- The separate anonymous job used a fresh Docker configuration without registry login. It pulled the release image, checked arm64 architecture, imported `server` and `websocket`, and verified `server.VERSION == 0.6.0-rc.1`. No real Pi/UPS operation was executed in CI.
- All 45 files in the publishing commit's tree match the prepared local content. App Python files and web assets remain byte-for-byte identical to the Pi-tested ZIP; source and test/documentation changes do not substitute for additional physical acceptance.
- A fresh Home Assistant app-store installation/update, novice completion, and the full long-outage UPS restart path remain unobserved here. The earlier maintainer report is the available physical Pi evidence.

The publication working copy passes the 259 backend tests, DOM checks, JavaScript syntax, and compiled RTC ABI check. Byte comparison confirms unchanged application Python/web assets. Manifest equality apart from URL/image, workflow YAML and embedded shell/Python syntax, full-commit action pins, documentation links, and seven publish-condition cases pass. Ordinary main pushes, pull requests, and dispatches without the publish option do not publish; a main dispatch and matching release tag do, while a non-main publish request or mismatched tag is rejected. Docker and hosted browser/public-image checks remain pending.

## Passed in this workspace

- **259 Python unittest cases**, using simulated RTC, host, and Supervisor services, fake Core WebSockets, and real loopback HTTP handlers. They include Calendar/DST calculations, ingress/CSRF guards, invalid requests, native sensor ownership/activation, fresh RTC readback, alarm ownership, cancellation, host boot evidence, update persistence/migration, emergency protection without RTC, firmware guards, and ambiguous shutdown failures. Expected failure diagnostics printed during the suite are simulated test cases. The app has no daily schedule executor or user time fields.
- The Calendar cases cover expanded occurrences, explicit DST offsets, all-day/invalid/overlapping events, exact absolute RTC end times, rechecks before arming and shutdown, event deletion/edit/outage during countdown, cancellation/restart claims, subsequent recurrence, no late catch-up, empty-calendar waiting, previews, Core API responses, and notification lifecycle. Schema-1/2 daily schedules migrate paused; schema-3 Calendar selection and confirmed test survive while old time fields are removed. Old daily POST requests cannot create a second schedule.
- The 29 additional cases cover NUT entity/device discovery, renamed raw status, translated/missing/conflicting/duplicate status, stale readings, unambiguous battery measurements, refusal to infer runtime from seconds units, typed versioned hooks, unsupported versions, invalid/future/naive timestamps, unavailable entities, invalid/overflowing numeric values, duplicate identities, explicit source selection, settings bounds/persistence/write rollback, scoped notice escalation/deduplication/restoration, cache expiry, service failures, and no automatic RTC/host action. Loopback HTTP tests cover source discovery, opt-in selection persistence, CSRF and invalid input for the new routes, and removal of manual shutdown. The 0.4 screenshot confirms actual discovery on the user's installation; new 0.5 duration-candidate mapping and Calendar-write behavior still need live validation.
- The three rc.4 cases verify detection of a missing effective `SYS_PTRACE` even with `SYS_ADMIN`/`SYS_CHROOT` present, continued refusal when a command fails despite all three effective capabilities being present, and preservation of the original failure if capability metadata is malformed or unavailable. Raw process metadata is excluded.
- The 18 additional rc.3 cases cover denied namespace entry, missing/incompatible tools, timeouts, failed exits despite success-looking JSON, malformed/hostile diagnostic data, firmware step and exit-code propagation, secret/output exclusion, minimal host environment, and failed/recovered checks through the actual loopback HTTP handler. A real local Python subprocess executes the bootstrap with an intentionally missing import. None of these tests enter the HAOS host or write real firmware.
- The rc.2 regression test reproduces the greyed-out preparation with the actual HAOS `rpi5-64` board ID before the fix and passes afterward. Unsupported and unknown boards are rejected before host access. The board fixture was corrected from the machine ID after checking HAOS's board metadata, generated CPE, Supervisor OS manager, and `/os/info` implementation. These are source-contract checks, not a captured live API response from the user's Pi.
- JavaScript syntax checks for the UI and the browser smoke script.
- `node tests/ui_logic.cjs` passes using the actual app script in a DOM fixture. It covers completed/failed setup navigation, retained drafts, dynamic reserve requirements, sensor-enable confirmation and source binding, outage blocking, emergency status, and explicit disable confirmation. This verifies interactions, not browser layout/rendering.
- Python AST parsing for the project files; YAML parsing for app configuration, repository metadata, and the image workflow. This is syntax/structure validation, not a complete Supervisor schema or runtime check.
- A compiled C check of the Linux RTC ABI, built with `-Wall -Wextra -Werror`: `rtc_time=36`, `rtc_wkalrm=40`, ioctl values `80247009`, `80287010`, `4028700f`, `7002`. This compile was on x86_64; the hardware target remains aarch64.
- Repository preparation exercised in a temporary directory: correct image/repository/install-link generation, safe Git URL handling, and invalid URL refusal. Nothing was published.
- A loopback-only simulated UI server starts successfully. It calls no real host or Home Assistant service.

Command used for the Python suite:

```sh
python3 -m unittest discover -s tests -q
```

## User-reported physical result

The user reports that the ten-minute test worked with rc.4 and that dates entered in Home Assistant Calendar appeared in the 0.3 summary. The supplied 0.3 screenshot shows Pi 5, HAOS 18.3, wake settings Ready, and wake test Confirmed. This is evidence of a successful automatic shutdown/wake cycle and Calendar reading on that user's setup. This workspace did not capture a hardware trace or independently repeat the cycle. The new supplied 0.4 screenshot shows live APC discovery, utility power, 100% charge, and an enabled power-notice preference. This validates that the earlier discovery template works on this installation. It does not establish 0.5 Calendar creation, power-notification transitions, RTC outage retries, final-stop recovery, overnight reliability, or the 0.5 upgrade flow.

## Not verified here

- Local browser execution and Docker remain unavailable in this workspace. The hosted Chromium smoke test and real arm64 image build/import now pass, as recorded above. That smoke test uses simulated loopback services; it does not verify real Home Assistant ingress, every accessibility interaction, or every device's layout.
- The complete fresh-install/update flow, authentication security through actual Home Assistant ingress, or a full Supervisor manifest/runtime check. Earlier rc.2/rc.3 logs showed failed host inspection and access denied before helper startup; rc.4 repaired the missing `SYS_PTRACE` declaration. The later successful test report supersedes that failure as the latest user result, although effective-capability metadata was not captured here.
- Host namespace entry on Home Assistant OS, host Python/tool paths, EEPROM staging/flashrom, boot-order preservation on actual firmware, or interference with a separately initiated native firmware update.
- Independently observed power-off/RTC wake, multiple overnight cycles, accessory-specific reliability, or migration through an actual published-app update. One successful ten-minute cycle is user-reported above.
- Independently captured Calendar recurrence/write/readback responses, real countdown edits, the 0.6 update on HAOS, or live notification creation/clearing. The earlier Calendar-summary report is noted above.
- Independently captured NUT registry list/update over the live Core WebSocket proxy, sensor reload/restart timing, actual disabled-device/permission failures, the community NUT app's settings/startup state, or runtime selection after activation on HAOS. Registry/ownership source contracts were checked; wire tests use fake sockets.
- This user's UPS driver/firmware/connection, shutdown ownership ordering, and long-outage output-off/return behavior. The app sends no UPS output command; enabled protection requests graceful host shutdown. Emergency shutdown, RTC retries, ownership review, and final recovery have not passed physical acceptance. Explicit NUT handoff and UPS output control remain unimplemented.
- Independent Jinja parsing/rendering of the discovery template. The Jinja dependency is absent here. Home Assistant's current template state wrapper exposes `last_reported`, and its integration/device helpers were checked in primary source; the 0.4 user screenshot is now evidence of template execution on this installation. New 0.5 fields are not independently observed here.
- A fresh Home Assistant app-store installation through the Add to Home Assistant link. The public repository, published preview/tag, anonymous image download, target architecture, and production imports are verified above.

The production image excludes the developer preview and tests. Production ingress allows only the Supervisor proxy at `172.30.32.2`. The developer preview is explicitly simulated and binds only to loopback.

See [ACCEPTANCE.md](ACCEPTANCE.md) for the required real-device and novice-user validation. This archive is a reviewable release candidate, not evidence that the beginner-release acceptance requirement has passed.

## Pi identification sources checked for rc.2

- [HAOS Pi 5 metadata](https://github.com/home-assistant/operating-system/blob/dev/buildroot-external/board/raspberrypi/rpi5-64/meta): `BOARD_ID=rpi5-64`, `SUPERVISOR_MACHINE=raspberrypi5-64`.
- [HAOS os-release generation](https://github.com/home-assistant/operating-system/blob/dev/buildroot-external/scripts/post-build.sh): CPE target hardware comes from `BOARD_ID`.
- [Supervisor OS manager](https://github.com/home-assistant/supervisor/blob/main/supervisor/os/manager.py): board is read from the CPE target hardware.
- [Supervisor OS API](https://github.com/home-assistant/supervisor/blob/main/supervisor/api/os.py): `/os/info` returns the OS manager's board value.

No EEPROM, RTC alarm, shutdown, or other real Pi operation was performed while building this fix.

## New 0.6 simulated coverage and source contracts

39 new backend regression cases pass, bringing the total from 220 to 259. They cover `OL TEST` and auxiliary flags/conflicts, 24/39/69-minute reserve requirements, fixed Core WebSocket authentication/registry commands, exact NUT device/platform binding, missing/invalid device identity, native sensor activation/readback/reload guidance, disabled-device refusals, sanitized ownership settings, stopped/conflicting NUT controllers, CSRF/outage activation guards, emergency shutdown after retry cancellation/RTC failure/Calendar failure, fresh low-battery/FSD without runtime, separate disable consent, emergency-only Calendar behavior, discounted aging reserve, lost-readings reserve across restart, source identity changes, and schema-5 preservation with ownership review. No real host/UPS operation occurs.

Primary contracts checked for 0.6:

- [HA Core entity-registry WebSocket API](https://github.com/home-assistant/core/blob/dev/homeassistant/components/config/entity_registry.py): list/get/update, `disabled_by`, device-disable refusal, admin checks, and `require_restart`/`reload_delay` response.
- [HA Core registry metadata](https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/entity_registry.py) and [NUT sensor metadata](https://github.com/home-assistant/core/blob/dev/homeassistant/components/nut/sensor.py): real integration/device ownership and default-disabled runtime metadata.
- [Supervisor Core proxy](https://github.com/home-assistant/supervisor/blob/main/supervisor/api/proxy.py) and [app communication](https://developers.home-assistant.io/docs/apps/communication/): fixed `ws://supervisor/core/websocket` authentication with the app's existing Supervisor token.
- [Alpine aarch64 websocket-client package](https://pkgs.alpinelinux.org/package/v3.23/community/aarch64/py3-websocket-client): production dependency availability checked. The local tests inject sockets and do not exercise an installed production package or image.
- [NUT app options](https://github.com/hassio-addons/app-nut/blob/main/nut/DOCS.md), [startup command selection](https://github.com/hassio-addons/app-nut/blob/main/nut/rootfs/etc/cont-init.d/nut.sh), and [host-shutdown script](https://github.com/hassio-addons/app-nut/blob/main/nut/rootfs/usr/bin/shutdownhost): Host shutdown behavior and restart requirement. These are not a captured running NUT configuration or a complete handoff.
- [NUT variable/status reference](https://networkupstools.org/docs/developer-guide.chunked/apas02.html): raw status may contain multiple auxiliary flags. Recognizing flags is not evidence of supported output control.

Future wake dates still have one owner: Home Assistant Calendar. Schema 6 adds past runtime observation metadata and protection/ownership preferences; it does not add a second schedule-date system. An enabled 0.5 policy is preserved but waits for ownership review before any automatic protection resumes.

## Host bridge sources checked for rc.3

- [Upstream nsenter documentation](https://man7.org/linux/man-pages/man1/nsenter.1.html): `--wd` opens its directory before entering namespaces/chroot; `--wdns` opens it afterward. This candidate uses `--wdns=/`.
- [Alpine 3.23 util-linux package](https://github.com/alpinelinux/aports/blob/3.23-stable/main/util-linux/APKBUILD): misc binaries are split into `util-linux-misc`. The image explicitly installs that package and checks the required option, rather than assuming the meta-package/PATH selected the intended tool.
- [HAOS 18.3 Pi 5 configuration](https://github.com/home-assistant/operating-system/blob/18.3/buildroot-external/configs/rpi5_64_defconfig) and [EEPROM package dependencies](https://github.com/home-assistant/operating-system/blob/18.3/buildroot-external/package/rpi-eeprom/Config.in): Pi 5 firmware support selects host Python 3. Missing Python is a diagnostic possibility, not an established explanation for the user's log.
- [HAOS 18.3 EEPROM package](https://github.com/home-assistant/operating-system/blob/18.3/buildroot-external/package/rpi-eeprom/rpi-eeprom.mk) and its [pinned Raspberry Pi source](https://github.com/raspberrypi/rpi-eeprom/tree/e25fc5dcb8eb072eafb745cd546c3d9f73d102b5): firmware tools and Pi 5 firmware paths were checked. The rc.3 log shows access denied before these commands can run, so it supplies no live confirmation of their results.

## Permission repair sources checked for rc.4

- [Linux namespace access](https://man7.org/linux/man-pages/man7/namespaces.7.html) and [host root access](https://man7.org/linux/man-pages/man5/proc_pid_root.5.html): dereferencing `/proc/pid/ns/*` and `/proc/pid/root` uses `PTRACE_MODE_READ_FSCREDS`.
- [Kernel capability access check](https://github.com/torvalds/linux/blob/v6.12/security/commoncap.c): `cap_ptrace_access_check` requires the target's permitted capabilities to be a subset of the caller's effective capabilities in the same user namespace, or `CAP_SYS_PTRACE` in the target's user namespace. `SYS_ADMIN` alone does not satisfy this check.
- [Mount namespace entry](https://man7.org/linux/man-pages/man2/setns.2.html): entering a mount namespace also requires `CAP_SYS_ADMIN` and `CAP_SYS_CHROOT`. These are separate from permission to open the namespace handle.
- [Docker default capabilities](https://docs.docker.com/engine/containers/run/#runtime-privilege-and-linux-capabilities): `SYS_CHROOT` is present by default; `SYS_PTRACE` and `SYS_ADMIN` must be requested separately.
- [Home Assistant app configuration](https://developers.home-assistant.io/docs/apps/configuration/): `SYS_PTRACE` is an allowed explicit capability; host PID access requires Protection mode off.
- [Supervisor app container creation](https://github.com/home-assistant/supervisor/blob/main/supervisor/docker/app.py): `cap_add` comes from the app's requested capabilities. `full_access` supplies device-cgroup access rather than granting every capability. The old declaration requested `SYS_ADMIN`/`SYS_RAWIO` and omitted `SYS_PTRACE`.

These source contracts explain a concrete missing permission consistent with the live error. They do not prove the exact denied syscall on the user's Pi, since rc.3 discarded that part of stderr. No host namespace was entered and no real Pi firmware or RTC was changed in this workspace.

## Home Assistant sources checked for 0.3

- [Local Calendar documentation](https://www.home-assistant.io/integrations/local_calendar/) and [its entity implementation](https://github.com/home-assistant/core/blob/dev/homeassistant/components/local_calendar/calendar.py): native event editing and recurrence expansion remain owned by Home Assistant.
- [REST API documentation](https://developers.home-assistant.io/docs/api/rest/) and [Calendar REST views](https://github.com/home-assistant/core/blob/dev/homeassistant/components/calendar/__init__.py): calendar list and event-window responses, including timed start/end values.
- [Supervisor endpoints](https://developers.home-assistant.io/docs/api/supervisor/endpoints/), [resolution API](https://github.com/home-assistant/supervisor/blob/main/supervisor/api/resolution.py), and [HA Supervisor repairs bridge](https://github.com/home-assistant/core/blob/dev/homeassistant/components/hassio/repairs.py): native firmware updates raise their own reboot issue, but apps have no generic supported create-issue endpoint.
- [Persistent Notification](https://www.home-assistant.io/integrations/persistent_notification/): the app uses only its own scoped notification ID through Core services.

## Home Assistant/NUT sources checked for 0.4

- [HA NUT documentation](https://www.home-assistant.io/integrations/nut/) and [sensor implementation](https://github.com/home-assistant/core/blob/dev/homeassistant/components/nut/sensor.py): NUT server prerequisite, raw status flags, battery measurement versus diagnostic charge settings, and runtime versus delay readings.
- [HA template reference](https://www.home-assistant.io/template-functions/), [template state wrapper](https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/template/states.py), and [REST API](https://developers.home-assistant.io/docs/api/rest/): integration/device helpers, `last_reported`, and template access through Core.
- [NUT usbhid-ups](https://networkupstools.org/docs/man/usbhid-ups.html), [configuration notes](https://networkupstools.org/docs/user-manual.chunked/ar01s06.html), and [apc_modbus](https://networkupstools.org/docs/man/apc_modbus.html): supported-driver recovery varies and requires physical testing. USB-oriented documentation is not proof of TCP support in a particular build.
- The user's supplied APC 990-91081C operation manual: possible local USB/Modbus and return-after-shutdown paths for SMTL1500RM3UC. No actual connection or command was exercised.

The included browser smoke test exercises the sole Calendar source, native-calendar link, saved selection/list, reload, setup gates, countdown cancellation, simulated UPS discovery/selection, and mobile width. It could not launch in this workspace because Chromium's executable is missing. JavaScript and markup checks do not substitute for that browser run or live Home Assistant testing.

## New 0.5 simulated control coverage

53 additional cases pass: defaults/typed bounds/consent, explicitly selected same-device NUT runtime, doubling/capping retry intervals, low-charge/runtime/forced-shutdown reserve guards, Calendar-native retry/final records, exclusion of managed events from ordinary scheduling, runtime-threshold/optional early delay, readback before arm, fresh observations after reboot, stable/flickering/unknown power, runtime drop during countdown, final/critical stop, cancellation with/without alarm, persisted limits, lost data in a known versus unknown outage, read-only/missing Calendar/runtime refusal, browser target binding, provider qualification refusal, lost create response, failed creation without repetition, emergency Calendar failure, edit/deletion during countdown, ambiguous host response and same-boot alarm retention, ambiguous final-stop response without an alarm claim, interrupted countdown, storage failure, final-stop reboot pause, update/backup protection, firmware retest gates, notification clearing/retry throttling, fixed Core service contracts, and actual loopback HTTP authorization/off-default behavior. These simulations perform no real host/UPS operation.

The 0.5 browser smoke script also checks the recovery section remains off without a passed test. Browser rendering/launch remains unverified because Chromium is unavailable. Docker/image/public installer and the full real-device/novice acceptance gates remain outstanding.
