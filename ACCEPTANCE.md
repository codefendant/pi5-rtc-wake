# Preview and stable-release acceptance

**A person with no technical background can install, test, and enable this app entirely through Home Assistant screens. Updates preserve their settings. Every error explains the next action in plain language.**

## 0.10.0 Public Preview

On **13 October 2026**, the maintainer reports several successful clean-install tests on their Pi 5 after deleting both the app and dashboard, reinstalling, and completing setup. Earlier reports include a successful physical ten-minute wake test, functioning Calendar/UPS/phone/Assist features, and the working native dashboard. The duplicate app-store listing was resolved on the test system. These are maintainer reports; no exact cycle count, timing measurement, or independent observation is claimed.

The formal preview preserves the tested 0.10.0-rc.6 behavior. It remains **experimental** in Home Assistant and **pre-release** on GitHub. User-reported results and automated/simulated results are recorded separately in [VALIDATION.md](VALIDATION.md).

| Public preview check | Evidence |
|---|---|
| Fresh installation and dashboard recreation through Home Assistant screens | Maintainer reports repeated successful clean reinstalls. Automated native Core checks create the dashboard and exercise discovery and reconnection. |
| Permissions and first-cycle guidance | Info-page Protection mode illustration, actionable host-access errors, ten-minute outage explanation, and return confirmation are implemented. |
| Everyday dashboard usability | Maintainer reports the improved interface works. Chromium desktop/mobile/narrow/dark checks cover cards, details, forms, and section widths. |
| Automatic RTC wake | Maintainer previously confirmed the ten-minute physical test returned automatically. New version metadata does not change RTC behavior. |
| Settings and personal-card preservation | Backend and real Core checks exercise persistence, migrations, reconnection, legacy layout upgrades, and customized-card retention. A physical same-app update is not established by fresh reinstall testing. |
| Public installation package | The publication pipeline must verify the arm64 image through an anonymous pull and production imports before creating the preview release. |
| Public docs and feedback | Current install/update instructions, sample dashboard, approved use-case artwork, bug-report form, and suggestion form. |

## Before a stable beginner release

A successful maintainer installation and automated tests alone do not establish the beginner-release requirement. These checks remain separate from preview publication:

| Check | Required observation |
|---|---|
| Independent novice session | A person unfamiliar with the project completes installation, Protection mode, dashboard discovery, wake test, feature activation, cancellation, and an ordinary update using only the public instructions. Record confusing screens and fix them. |
| Physical in-place update | Update the same published app in HAOS; compare Calendar selection/dates, valid wake evidence, UPS, phone/readings, Assist and device-waking settings, Keep awake, and personal cards. |
| Firmware preparation across supported boot media | Compare actual EEPROM readback and boot order on SD, USB SSD, and NVMe; test pending/mismatched updates without interrupting a firmware write. Audit coordination with the stock updater. |
| Repeated overnight RTC cycles | Observe shutdown, automatic boot, Calendar recurrence/edits/cancellation, and time-zone/DST behavior with the actual connected power accessories. |
| Real phone delivery | Confirm manual status, RTC-wake delivery, selected values/units, app-restart deduplication, and behavior during network or power outages. |
| Real Assist operation | Observe fresh connection, local Ollama/voice status and reviewed changes, approval/cancellation, revocation, and companion update/restart. |
| Live restart reminders | Confirm first-install notification and later Settings repair reminder, including correct clearance after matching companion readiness. |
| Live UPS commissioning | Confirm the actual supplying UPS, enabled readings, freshness, auxiliary status flags, shutdown ownership, thresholds, conditional retries, low battery, unavailable data, and preservation of emergency protection when retries alone are cancelled. Explicit Keep awake intentionally suspends app emergency shutdowns too. |
| Third-party power data hooks | Have an independent provider publish a compatible sensor and complete selection/setup through Home Assistant screens. |
| Accessibility and actionable errors | Observe mobile/desktop use and test permission, unsupported host, missing RTC, clock, pending update, unavailable Calendar, and storage failures. |

A novice session should use the public install link and a fresh supported Pi. Give only the installation guide; do not supply a terminal, YAML, or developer coaching. Record completion time, mistakes, and any screen that required explanation. Repeat after fixes before removing the preview label.

## UPS recovery boundary

UPS output-off/return control and an explicit NUT shutdown handoff are **not implemented**. RTC retries require continuous main input power and sufficient reserve. A final stop has no verified timed wake; utility power returning cannot boot a continuously supplied halted Pi by itself.

Test the actual UPS output-return/boot path before promising unattended long-outage recovery. Future output-control support requires an exact supported command, late-cut delay, physical output-off/return, and Pi boot verification. [UPS_RECOVERY.md](UPS_RECOVERY.md) describes the current policy.

Hardware tests must use stable connected power. Firmware preparation must never be tested by interrupting EEPROM writes; simulate failures at the service boundary instead and retain a recovery path during maintainer trials.
