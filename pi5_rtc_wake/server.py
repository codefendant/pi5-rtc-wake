#!/usr/bin/env python3
"""Ingress UI, setup wizard, wake-test evidence and a fail-closed scheduler."""

from copy import deepcopy
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import math
from pathlib import Path
import queue
import re
import secrets
import threading
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from calendar_schedule import due_period, parse_periods
from power_sources import discover_sources, monitor_runtime, notice_for, validate_settings as validate_power_settings
from ups_recovery import Recovery
from phone_messages import PhoneMessages

from host_helper import config_values, patched_config, sha
from rtc_wake import Controller, LinuxRTC, PolicyError
from services import Host, Supervisor
from state import StateStore, UserError, atomic_json, validate_schedule
from assist import Assistant, PORT as ASSIST_PORT
from assist_http import AssistHandler
from dashboard import Dashboard

VERSION = "0.10.0-rc.6"
LOG = logging.getLogger("pi5_rtc_wake")
COUNTDOWN = 30
TEST_SECONDS = 600
WEB = Path(__file__).with_name("web")


class Application:
    def __init__(self, data, rtc, supervisor, host, *, clock=time.time, monotonic=time.monotonic):
        self.clock, self.monotonic = clock, monotonic
        self.store = StateStore(data)
        self.supervisor, self.host = supervisor, host
        self.controller = Controller(rtc, firmware_configured=False,
                                     ownership_file=Path(data) / "owned_alarm.json", clock=clock, monotonic=monotonic)
        self.lock = threading.RLock()
        self.tasks = queue.Queue()
        self.job = None
        self.pending = None  # Shutdown countdowns deliberately do not survive a process restart.
        self.shutdown_requested_at = None
        self.cancel_serial = 0
        self.checks = {"ok": False, "message": "Checking this Pi…", "action": "Keep the Pi on while setup checks finish.", "items": []}
        self.host_snapshot = None
        self.last_os_identity = None
        self.last_refresh = -math.inf
        self.message = {"text": self.store.notice or "Welcome. Start with the Pi checks below.", "action": "", "error": bool(self.store.notice)}
        self.csrf = secrets.token_urlsafe(32)
        self.stale_alarm_checked = False
        self.stop_event = threading.Event()
        self.calendar_info = {"ok": False, "calendars": [], "periods": [], "message": "Create a dedicated Local Calendar in Home Assistant, then select Check again.", "action": ""}
        self.last_calendar_refresh = -math.inf
        self.last_calendar_discovery = -math.inf
        self.reboot_notice_state = None
        self.last_notice_requirement = None
        self.last_notice_attempt = -math.inf
        self.reboot_notice_ok = True
        self.power_info = {"ok": False, "sources": [], "message": "Select Find power sources to look for NUT devices and compatible hooks in Home Assistant.", "warnings": []}
        self.last_power_refresh = -math.inf
        self.power_notice_signature = None
        self.last_power_notice_attempt = -math.inf
        self.last_power_notice_signature = None
        self.power_notice_ok = True
        self.host_shutdown_supported = False
        self.nut_sensor_info = {"ok": False, "sensors": [], "message": "Find power sources to check disabled NUT sensors."}
        self.shutdown_controller_info = {"state": "unknown", "addon_id": None, "message": "Check shutdown ownership before enabling UPS protection."}
        self.last_nut_settings_refresh = -math.inf
        self.recovery = Recovery(self)
        self.messages = PhoneMessages(self)
        self.assistant = Assistant(self, data)
        self.permissions = {"protected": None, "slug": None}
        self.dashboard = Dashboard(self, data)
        from wake_devices import WakeDevices
        self.wake_devices = WakeDevices(self, data)

    def _fingerprint(self, snapshot):
        value = snapshot["current_version"] + ":" + snapshot["config_fingerprint"]
        return hashlib.sha256(value.encode()).hexdigest()

    def refresh(self, *, force_calendar_discovery=False):
        items = []
        try:
            os_info = self.supervisor.os_info()
            os_identity = (os_info.get("board"), os_info.get("version"))
            if os_identity != self.last_os_identity:
                LOG.info("Home Assistant OS detected: board=%r version=%r", *os_identity)
                self.last_os_identity = os_identity
            # /os/info reports HAOS BOARD_ID, not SUPERVISOR_MACHINE.
            # The Pi 5's values are rpi5-64 and raspberrypi5-64 respectively.
            if os_info.get("board") != "rpi5-64":
                self.host_shutdown_supported = False
                raise UserError("This app needs the Raspberry Pi 5 running Home Assistant OS.", "Install it on your Home Assistant Pi 5.")
            items.append({"label": "Raspberry Pi 5", "detail": "Detected", "ok": True})
            version = str(os_info.get("version", ""))
            if not re.match(r"^\d+(?:\.|$)", version) or int(version.split(".")[0]) < 18:
                self.host_shutdown_supported = False
                raise UserError("Home Assistant OS 18 or newer is required.", "Open Settings → System → Updates, update Home Assistant OS, and reboot.")
            items.append({"label": "Home Assistant OS", "detail": version, "ok": True})
            self.host_shutdown_supported = True  # Independent of firmware/RTC readiness.
            info = self.supervisor.app_info()
            protected, slug = info.get("protected"), info.get("slug")
            self.permissions = {"protected": protected if type(protected) is bool else None,
                                "slug": slug if isinstance(slug, str) and re.fullmatch(r"[a-z0-9]{1,32}_pi5_rtc_wake", slug) else None}
            if protected is True:
                raise UserError("Turn off Protection mode to allow access to this Pi.",
                                "Open the app's Info page. Stop the app, turn Protection mode off, then Start the app. This page will check again automatically.")
            if protected is not False:
                raise UserError("Protection mode could not be checked.",
                                "Open the app's Info page and check that Protection mode is off. Restart the app, then select Check again.")
            items.append({"label": "Protection mode", "detail": "Off", "ok": True})
            firmware = self.supervisor.firmware_info()
            required = ("update_available", "update_pending", "update_blocked")
            if any(type(firmware.get(key)) is not bool for key in required):
                raise UserError("Firmware information is incomplete.", "Update Home Assistant and select Check again.")
            if firmware["update_blocked"]:
                raise UserError("Home Assistant's Pi updater cannot prepare this boot device.", "Keep the Pi on. Update Home Assistant OS and select Check again. If it is still blocked, contact the app maintainer for support for this boot device.")
            snapshot = self.host.inspect()
            if str(firmware.get("current_version")) != snapshot["current_version"]:
                raise UserError("Firmware information is still refreshing.", "Wait one minute, then select Check again.")
            self.controller.firmware_configured = snapshot["wake_configured"]
            rtc_status = self.controller.status()
            if rtc_status["status"] == "error":
                raise UserError("The Pi's built-in wake clock could not be read.", "Restart this app. If the check still fails, update Home Assistant OS or contact the app maintainer.")
            if not rtc_status["clock_valid"]:
                raise UserError("The Pi's wake clock and current time do not agree.", "Keep the Pi on and connected to the internet. Wait a few minutes and select Check again; reboot if the check keeps failing.")
            items.append({"label": "Built-in wake clock", "detail": "Time is correct", "ok": True})
            with self.lock:
                if not self.stale_alarm_checked:
                    # Only remove an exact alarm this app previously owned. Never
                    # remove another program's alarm, or trust a stale transaction.
                    outage = self.store.data["outage"]
                    unresolved = outage.get("submitted") and outage.get("boot_id") == self.host.boot_id()
                    if rtc_status.get("alarm_enabled") and rtc_status.get("wake_epoch") == self.controller.owned_epoch and not unresolved:
                        self.controller.rtc.clear_alarm()
                        if self.controller.rtc.read_alarm()["enabled"]:
                            raise UserError("An interrupted wake alarm could not be cleared.", "Restart the app, then select Check again.")
                    self.stale_alarm_checked = True
                prep = self.store.data.get("preparation", {})
                needs_reboot = bool(prep.get("boot_id") == self.host.boot_id() and prep.get("reboot_required"))
                if prep.get("reboot_required") and not needs_reboot and not snapshot["pending"] and not firmware["update_pending"]:
                    if prep.get("expected_config_fingerprint") != snapshot["config_fingerprint"]:
                        raise UserError("The wake preparation did not match after the Pi restarted.", "Keep the Pi on and contact the app maintainer. Your original boot settings were saved before preparation.")
                    prep["reboot_required"] = False
                    self.store.save()
                self.host_snapshot = snapshot
                fingerprint = self._fingerprint(snapshot) if snapshot["editable"] else None
                test = self.store.data.get("test", {})
                if test.get("status") == "passed" and test.get("fingerprint") != fingerprint:
                    test["status"] = "needs_retest"
                    self.store.save()
                self._reconcile_test(fingerprint)
                if not self.store.data.get("timezone_detected") and not self.store.read_only:
                    try:
                        timezone = self.supervisor.timezone()
                        ZoneInfo(timezone)
                        self.store.data["schedule"]["timezone"] = timezone
                        self.store.data["timezone_detected"] = True
                        self.store.save()
                    except (UserError, ValueError, TypeError, KeyError):
                        pass  # The UI keeps the editable time zone selector.
            firmware_detail = "Reboot required" if firmware["update_pending"] else "Update available in Home Assistant" if firmware["update_available"] else "Managed by Home Assistant"
            items.append({"label": "Pi firmware", "detail": firmware_detail, "ok": not firmware["update_pending"]})
            items.append({"label": "Wake settings", "detail": "Ready" if snapshot["wake_configured"] else "Preparation needed", "ok": snapshot["wake_configured"]})
            result = {"items": items, "firmware": {key: firmware[key] for key in required},
                      "wake_configured": snapshot["wake_configured"], "fingerprint": fingerprint,
                      "can_prepare": snapshot["editable"] and not snapshot["pending"] and not firmware["update_pending"] and not firmware["update_blocked"] and snapshot["current_version"] == snapshot["image_version"] and not snapshot["wake_configured"],
                      "needs_reboot": needs_reboot or firmware["update_pending"] or snapshot["pending"]}
            if result["needs_reboot"]:
                result.update(ok=False, message="Reboot the Pi to finish preparation or a firmware update.", action="Select Reboot Pi. Leave the power connected, then reopen this app when Home Assistant returns.")
            elif not snapshot["editable"]:
                result.update(ok=False, message="The Pi has custom boot settings this release cannot safely prepare.", action="Contact the app maintainer for support for this configuration. Keep the Pi on.")
            elif not snapshot["wake_configured"]:
                action = "Select Prepare this Pi. Your existing boot order will be kept."
                if firmware["update_blocked"]:
                    action = "Home Assistant cannot update this boot device. Contact the app maintainer; keep the Pi on."
                elif snapshot["current_version"] != snapshot["image_version"]:
                    action = "Open Settings → System → Updates and install the Pi firmware update, then reboot. If no update is offered, update Home Assistant OS or contact the app maintainer."
                result.update(ok=False, message="The Pi needs wake settings prepared once.", action=action)
            else:
                result.update(ok=True, message="This Pi is ready for a wake test.", action="Run the ten-minute wake test before enabling a schedule.")
            with self.lock:
                self.checks = result
                self.last_refresh = self.monotonic()
        except (UserError, OSError, ValueError, KeyError, TypeError, PolicyError) as error:
            self.controller.firmware_configured = False
            message = error if isinstance(error, UserError) else UserError("The Pi check could not finish.", "Keep the Pi on. Restart the app and select Check again; contact the app maintainer if this continues.")
            LOG.warning("Pi check failed: %s Next action: %s", message.message, message.action)
            with self.lock:
                known_reboot = self.checks.get("needs_reboot") or self.store.data.get("preparation", {}).get("reboot_required")
                self.checks = {"ok": False, "items": items, "message": message.message, "action": message.action}
                if known_reboot:
                    self.checks["needs_reboot"] = True
                if getattr(message, "details", None):
                    self.checks["details"] = message.details
                self.last_refresh = self.monotonic()
        self.refresh_calendar(force_discovery=force_calendar_discovery)
        self.sync_reboot_notice()
        if self.store.data["ups"]["source_id"] or force_calendar_discovery or self.monotonic() - self.last_power_refresh >= 120:
            self.refresh_power()
        return self.checks

    def refresh_nut_settings(self, *, sensors=True):
        if sensors:
            try:
                rows = self.supervisor.nut_sensors()
                self.nut_sensor_info = {"ok": True, "sensors": rows, "message": "Choose which disabled readings to enable. Home Assistant may briefly reload NUT."}
            except (UserError, OSError, ValueError, TypeError, KeyError) as error:
                self.nut_sensor_info = {"ok": False, "sensors": [], "message": error.message if isinstance(error, UserError) else "Open the NUT device page to enable disabled sensors."}
        try:
            self.shutdown_controller_info = self.supervisor.shutdown_controller()
        except (UserError, OSError, ValueError, TypeError, KeyError):
            self.shutdown_controller_info = {"state": "unknown", "addon_id": "a0d7b954_nut", "message": "NUT host-shutdown settings could not be checked. RTC retries are paused; commissioned emergency protection remains active."}
        self.last_nut_settings_refresh = self.monotonic()

    def refresh_power(self, *, settings=False):
        if settings or self.monotonic() - self.last_nut_settings_refresh >= 120:
            self.refresh_nut_settings()
        try:
            sources, warnings = discover_sources(self.supervisor.power_sources(), self.clock())
            result = {"ok": True, "sources": sources, "warnings": warnings, "message": str(len(sources)) + " power source(s) found. Choose which one powers this Pi." if sources else "No compatible sources found. Connect NUT to Home Assistant, enable its Status data sensor, or add a compatible power hook."}
        except (UserError, OSError, ValueError, TypeError, KeyError) as error:
            message = error.message if isinstance(error, UserError) else "Power sources could not be checked."
            result = {"ok": False, "sources": deepcopy(self.power_info["sources"]), "warnings": [], "message": message + " Check the NUT integration or power hook and select Find power sources."}
        with self.lock:
            identities = {source["id"] for source in result["sources"]}
            for row in self.nut_sensor_info["sensors"]:
                identity = "nut:" + row["device_id"]
                if identity not in identities:
                    identities.add(identity)
                    result["sources"].append({"id": identity, "name": row.get("device_name", "NUT UPS"), "provider": "Home Assistant NUT",
                        "manufacturer": row.get("manufacturer", ""), "model": row.get("model", ""), "ok": False, "power_state": "unknown", "battery_percent": None,
                        "runtime_seconds": None, "low_battery": False, "forced_shutdown": False, "recovery": "unverified", "readings": [], "runtime_candidates": [], "observed_epoch": None,
                        "message": "Enable Status data on this NUT device and wait for fresh readings."})
            result["sources"].sort(key=lambda source: (source["name"].lower(), source["id"]))
            if result["ok"] and result["sources"]:
                result["message"] = str(len(result["sources"])) + " power source(s) found. Choose which one powers this Pi."
            self.power_info = result
            self.last_power_refresh = self.monotonic()
        self.sync_power_notice()

    def _selected_power(self):
        if not self.power_info["ok"] or self.monotonic() - self.last_power_refresh >= 90:
            return None
        return next((source for source in self.power_info["sources"] if source["id"] == self.store.data["ups"]["source_id"]), None)

    def enable_nut_sensor(self, payload):
        with self.lock:
            identity = self.store.data["ups"]["source_id"]
            source = self._selected_power()
            if payload.get("confirmed") is not True or payload.get("expected_source_id") != identity or not identity or not identity.startswith("nut:"):
                raise UserError("Confirm a sensor from the saved NUT UPS.", "Save the selected UPS, then choose Enable beside its sensor.")
            if self.job or self.pending or self.shutdown_requested_at is not None or self.store.data["outage"] or source and source["power_state"] in ("battery", "off"):
                raise UserError("Wait for stable utility power before changing NUT sensors.", "Enabling a sensor can reload the integration. Keep its readings available during an outage or Pi operation.")
            result = self.supervisor.enable_nut_sensor(identity[4:], payload.get("entity_id"))
            for row in self.nut_sensor_info["sensors"]:
                if row["entity_id"] == payload.get("entity_id"):
                    row.update(disabled_by=None, can_enable=False)
            self.last_nut_settings_refresh = -math.inf
            self.message = {"text": "NUT sensor enabled." + (" Home Assistant must restart before it becomes available." if result["require_restart"] else " Waiting for Home Assistant to reload NUT and report fresh readings."),
                            "action": "Use Settings → System to restart Home Assistant when convenient." if result["require_restart"] else "The app will refresh its readings automatically. Select the remaining-runtime reading after it appears.", "error": False}

    def sync_power_notice(self):
        with self.lock:
            settings = deepcopy(self.store.data["ups"])
            notice = notice_for(self._selected_power(), settings, self.store.data["recovery"]["enabled"]) if settings["notifications"] else None
            signature = (settings["source_id"], notice["kind"] if notice else "disabled")
            # Initial healthy state needs no notice. A restored state clears this
            # app's warning; it does not dismiss another app's UPS notifications.
            if notice and notice["kind"] == "mains":
                notice = None
        if signature == self.power_notice_signature or (signature == self.last_power_notice_signature and self.monotonic() - self.last_power_notice_attempt < 60):
            return
        self.last_power_notice_attempt, self.last_power_notice_signature = self.monotonic(), signature
        try:
            self.supervisor.power_notice(notice)
            self.power_notice_signature, self.power_notice_ok = signature, True
        except UserError:
            self.power_notice_ok = False
            LOG.warning("The power notification could not be updated; monitor status remains available in the app.")

    def save_power_settings(self, payload):
        settings = validate_power_settings(payload)
        with self.lock:
            if self.job or self.pending:
                raise UserError("A Pi operation is in progress.", "Wait for it to finish or cancel the countdown, then save the power monitor.")
            if self.store.data["outage"] and settings["source_id"] != self.store.data["ups"]["source_id"]:
                raise UserError("Wait for stable utility power before changing the UPS.", "Changing the supply identity requires reviewing automatic protection. Keep the current source selected during this outage.")
            if settings["source_id"] and not any(source["id"] == settings["source_id"] for source in self.power_info["sources"]):
                raise UserError("This power source was not found.", "Select Find power sources and choose an available source.")
            previous = deepcopy(self.store.data)
            if settings["source_id"] != self.store.data["ups"]["source_id"]:
                self.store.data["recovery"].update(enabled=False, qualification=None)
            self.store.data["ups"] = settings
            try:
                self.store.save()
            except Exception:
                self.store.data = previous
                raise
            self.message = {"text": "Power monitor saved. Review UPS recovery below for automatic shutdown settings.", "action": "", "error": False}
        self.sync_power_notice()
        self.recovery.notice()

    def refresh_calendar(self, *, force_discovery=False):
        with self.lock:
            schedule = deepcopy(self.store.data["schedule"])
            choices = deepcopy(self.calendar_info["calendars"])
        try:
            if force_discovery or self.monotonic() - self.last_calendar_discovery >= 60:
                choices = self.supervisor.calendars()
                self.last_calendar_discovery = self.monotonic()
            result = {"ok": False, "calendars": choices, "periods": [],
                      "message": "Create a dedicated Local Calendar in Home Assistant, then select Check again." if not choices else "Choose a dedicated calendar for the Pi's off periods.", "action": ""}
            if schedule["calendar_entity_id"]:
                entity = schedule["calendar_entity_id"]
                if not any(item["entity_id"] == entity for item in choices):
                    raise UserError("The saved calendar is no longer available.", "Choose an available calendar and save.")
                periods = parse_periods(self.supervisor.calendar_events(entity, self.clock()), entity, self.clock())
                result.update(ok=True, periods=periods, message="Off periods are managed in Home Assistant's Calendar." if periods else "No off periods in the next 31 days. Add an event in Home Assistant's Calendar.")
        except (UserError, OSError, ValueError, TypeError, KeyError) as error:
            message = error if isinstance(error, UserError) else UserError("The calendar could not be checked.", "Open Calendar in Home Assistant, then select Check again.")
            result = {"ok": False, "calendars": choices, "periods": [], "message": message.message, "action": message.action}
        with self.lock:
            if self.store.data["schedule"] == schedule:
                self.calendar_info = result
                self.last_calendar_refresh = self.monotonic()

    def sync_reboot_notice(self):
        with self.lock:
            # An unreadable host is not evidence that a reboot requirement cleared.
            if "needs_reboot" not in self.checks:
                return
            required = bool(self.checks.get("needs_reboot"))
        if self.reboot_notice_state == required or (self.last_notice_requirement == required and self.monotonic() - self.last_notice_attempt < 60):
            return
        self.last_notice_attempt = self.monotonic()
        self.last_notice_requirement = required
        try:
            self.supervisor.reboot_notice(required)
            self.reboot_notice_state = required
            self.reboot_notice_ok = True
        except UserError:
            self.reboot_notice_ok = False
            LOG.warning("Home Assistant reboot reminder could not be updated; the in-app reboot status is retained.")

    def _calendar_ready(self):
        return self.calendar_info["ok"] and self.monotonic() - self.last_calendar_refresh < 60

    def _calendar_period(self, key, *, due=False):
        if not self._calendar_ready():
            raise UserError(self.calendar_info["message"], self.calendar_info["action"] or "Select Check again.")
        period = next((item for item in self.calendar_info["periods"] if item["key"] == key), None)
        if period is None or due and not 0 <= self.clock() - period["start_epoch"] < 60:
            raise UserError("The off period changed, was cancelled, or its start was missed.", "The Pi will stay on. Review the event in Home Assistant's Calendar.")
        return period

    def _reconcile_test(self, fingerprint):
        test = self.store.data.get("test", {})
        if test.get("status") != "waiting":
            return
        if test.get("boot_id") == self.host.boot_id():
            if self.clock() > test.get("wake_epoch", math.inf) + 120:
                test["status"] = "failed"
                self.store.save()
            return
        boot_epoch = self.host.boot_epoch(self.clock())
        if (test.get("fingerprint") == fingerprint and type(test.get("wake_epoch")) is int
                and test["wake_epoch"] - 5 <= boot_epoch <= test["wake_epoch"] + 120):
            test["status"] = "awaiting_confirmation"
        else:
            test["status"] = "failed"
        self.store.save()

    def _require_ready(self, require_test=False):
        self.refresh()
        if not self.checks.get("ok"):
            raise UserError(self.checks["message"], self.checks["action"])
        if self.store.read_only:
            raise UserError("Saved settings need attention.", self.store.notice)
        if require_test and not self._test_passed():
            raise UserError("A successful wake test is required.", "Run the ten-minute test and confirm that Home Assistant returned by itself.")

    def _test_passed(self):
        test = self.store.data.get("test", {})
        return test.get("status") == "passed" and test.get("fingerprint") == self.checks.get("fingerprint")

    def snapshot(self):
        with self.lock:
            state = self.store.data
            pending = deepcopy(self.pending)
            if pending:
                pending["remaining_seconds"] = max(0, math.ceil(pending["deadline"] - self.monotonic()))
                pending.pop("deadline", None)
            schedule = deepcopy(state["schedule"])
            checks = deepcopy(self.checks)
            if checks.get("ok") and self._test_passed():
                checks["message"] = "This Pi is ready for scheduled shutdown and wake."
                checks["action"] = "Choose your calendar below and review its off periods."
            elif checks.get("ok") and state.get("test", {}).get("status") == "awaiting_confirmation":
                checks["message"] = "The Pi restarted near the test's wake time."
                checks["action"] = "Confirm below whether Home Assistant returned by itself."
            next_sleep = None
            next_wake = None
            if schedule["enabled"] and not state["keep_awake"]:
                try:
                    future = next((period for period in self.calendar_info["periods"] if not period.get("power_action") and period["start_epoch"] > self.clock()), None) if self._calendar_ready() else None
                    if future:
                        next_sleep, next_wake = future["start_epoch"], future["end_epoch"]
                except PolicyError:
                    pass
            return {"version": VERSION, "csrf": self.csrf, "checks": checks, "keep_awake": state["keep_awake"],
                    "permissions": deepcopy(self.permissions), "dashboard": self.dashboard.snapshot(),
                    "uptime_seconds": max(0, int(self.clock() - self.host.boot_epoch(self.clock()))), "current_epoch": int(self.clock()),
                    "host_shutdown_supported": self.host_shutdown_supported,
                    "schedule": schedule, "schedule_active": schedule["enabled"] and not state["keep_awake"] and self.checks.get("ok", False) and self._test_passed() and not self.store.read_only and self._calendar_ready() and not self.recovery.blocks_calendar(),
                    "calendar": deepcopy(self.calendar_info), "reboot_notice_ok": self.reboot_notice_ok,
                    "ups": {**deepcopy(self.power_info), "settings": deepcopy(state["ups"]), "selected": deepcopy(self._selected_power()), "notifications_ok": self.power_notice_ok, "mode": "rtc_recovery" if state["recovery"]["enabled"] else "monitor_only",
                            "sensor_settings": deepcopy(self.nut_sensor_info), "shutdown_controller": deepcopy(self.shutdown_controller_info),
                            "runtime": monitor_runtime(self._selected_power(), state["recovery"]["runtime_entity_id"], self.nut_sensor_info["sensors"], self.clock())},
                    "recovery": self.recovery.snapshot(),
                    "messages": self.messages.snapshot(),
                    "wake_devices": self.wake_devices.snapshot(),
                    "assist": self.assistant.snapshot(),
                    "test_status": state.get("test", {}).get("status", "not_started"),
                    "next_sleep_epoch": next_sleep, "next_wake_epoch": next_wake, "pending": pending, "job": self.job,
                    "shutdown_requested": self.shutdown_requested_at is not None,
                    "recovery_check_allowed": self.shutdown_requested_at is not None and self.monotonic() - self.shutdown_requested_at >= 120,
                    "message": deepcopy(self.message), "storage_notice": self.store.notice, "migration_notice": state.get("migration_notice")}

    def save_settings(self, payload):
        schedule = validate_schedule(payload)
        periods = None
        calendar_error = None
        if schedule["calendar_entity_id"] and (schedule["enabled"] or not self.pending):
            try:
                periods = parse_periods(self.supervisor.calendar_events(schedule["calendar_entity_id"], self.clock()), schedule["calendar_entity_id"], self.clock())
            except UserError as error:
                if schedule["enabled"]:
                    raise
                calendar_error = error  # Saving OFF must still work with Core unavailable.
        with self.lock:
            if self.job or self.pending and schedule["enabled"]:
                raise UserError("A Pi operation is in progress.", "Cancel the shutdown or wait for the operation to finish, then save.")
            if schedule["enabled"] and (not self.checks.get("ok") or not self._test_passed() or self.monotonic() - self.last_refresh > 60):
                raise UserError("Complete setup before enabling the schedule.", "Select Check again, finish preparation, and confirm a successful wake test.")
            old = deepcopy(self.store.data)
            calendar_changed = schedule["calendar_entity_id"] != self.store.data["schedule"]["calendar_entity_id"]
            self.store.data["schedule"] = schedule
            if schedule["calendar_entity_id"]:
                self.store.data.pop("migration_notice", None)
            self.store.data["timezone_detected"] = True
            try:
                self.store.save()
            except Exception:
                self.store.data = old
                raise
            if not schedule["enabled"] and self.pending and self.pending["kind"] == "schedule":
                self.cancel()
            if periods is not None:
                self.calendar_info.update(ok=True, periods=periods, message="Off periods are managed in Home Assistant's Calendar.", action="")
                self.last_calendar_refresh = self.monotonic()
            else:
                self.calendar_info.update(ok=False, periods=[], message=calendar_error.message if calendar_error else "Calendar saved. Select Check again to show its off periods.", action=calendar_error.action if calendar_error else "")
                self.last_calendar_refresh = -math.inf
            self.message = {"text": "Schedule saved." if schedule["enabled"] else "Calendar saved. Scheduling is off.", "action": "RTC retries need review for this new Calendar. Emergency UPS protection is unchanged." if calendar_changed and self.store.data["recovery"]["enabled"] else "", "error": False}

    def confirm_test(self, payload):
        with self.lock:
            if payload.get("returned_automatically") is not True:
                raise UserError("The wake test was not confirmed.", "Run the test again when you can check whether Home Assistant returns by itself.")
            test = self.store.data.get("test", {})
            if (test.get("status") != "awaiting_confirmation" or test.get("boot_id") == self.host.boot_id()
                    or test.get("fingerprint") != self.checks.get("fingerprint") or not self.checks.get("ok")):
                raise UserError("This test cannot be used to enable scheduling.", "Select Check again and run a new ten-minute wake test.")
            test["status"] = "passed"
            self.store.save()
            self.message = {"text": "Wake test confirmed. Choose your calendar, review its off periods, and enable scheduling.", "action": "", "error": False}

    def begin_job(self, kind, payload):
        with self.lock:
            if self.store.data["keep_awake"] and kind in ("reboot", "test", "sleep", "schedule", "ups"):
                raise UserError("Keep awake is on. Shutdowns and reboots are suspended.", "Select Resume shutdowns when you are ready. Your saved settings are kept.")
            if self.shutdown_requested_at is not None and (kind != "check" or self.monotonic() - self.shutdown_requested_at < 120):
                raise UserError("Shutdown has already been requested.", "Leave the power connected. If the Pi stays on, wait two minutes and select Check again.")
            if self.job or self.pending:
                raise UserError("A Pi operation is already in progress.", "Wait for it to finish, or cancel the shutdown countdown.")
            if self.store.read_only and kind not in ("check", "scan-ups"):
                raise UserError("Saved settings need attention.", self.store.notice)
            if kind not in ("check", "scan-ups") and payload.get("confirmed") is not True:
                raise UserError("The Pi operation was not confirmed.", "Read the confirmation on this screen and try again.")
            self.job = {"kind": kind, "label": {"check": "Checking this Pi…", "scan-ups": "Finding power sources in Home Assistant…", "prepare": "Preparing wake settings… Keep the power connected.", "reboot": "Rebooting the Pi…", "test": "Preparing the wake test…", "sleep": "Checking the next wake time…", "schedule": "Checking the scheduled shutdown…", "ups": "Preparing a safe UPS shutdown…"}[kind]}
            self.tasks.put((kind, payload, self.cancel_serial))

    def reject_test(self):
        with self.lock:
            self.store.data["test"]["status"] = "failed"
            self.store.data["schedule"]["enabled"] = False
            self.store.save()
            self.message = {"text": "Wake test not confirmed. Scheduling will stay off.", "action": "Keep the power supply connected and run the test again when you are ready.", "error": True}

    def cancel(self, *, mains_returned=False):
        with self.lock:
            if self.shutdown_requested_at is not None:
                raise UserError("Shutdown has already been requested.", "Leave the power connected. The wake time is still set.")
            if self.pending and self.pending.get("emergency") and not mains_returned:
                raise UserError("This is an emergency low-battery shutdown.", "Cancelling a timed retry does not disable emergency protection. Review the UPS protection settings while adequate power is available.")
            self.cancel_serial += 1
            pending, self.pending = self.pending, None
            if pending:
                if pending["kind"] == "ups":
                    self.recovery.cancelled()
                if pending.get("wake_epoch") is not None:
                    self.controller.clear({"request_id": pending["request_id"]})
            self.message = {"text": "Shutdown cancelled. The Pi will stay on.", "action": "", "error": False}

    def set_keep_awake(self, payload):
        if (not isinstance(payload, dict) or set(payload) != {"active", "confirmed"}
                or type(payload["active"]) is not bool or payload["confirmed"] is not True):
            raise UserError("Keep awake was not confirmed.", "Read the Keep awake or Resume shutdowns explanation and confirm your choice.")
        with self.lock:
            if self.shutdown_requested_at is not None:
                raise UserError("A power operation has already been requested.", "It cannot be cancelled now. Leave power connected and check again after Home Assistant returns.")
            active = payload["active"]
            if self.store.data["keep_awake"] == active:
                return
            old = deepcopy(self.store.data)
            self.store.data["keep_awake"] = active
            session = self.store.data["outage"]
            if active and session.get("phase") in ("planning", "countdown"):
                session.update(phase="observing", submitted=False, message="Keep awake is on. All app shutdowns are suspended.")
            elif not active and session.get("message") == "Keep awake is on. All app shutdowns are suspended.":
                session["message"] = "Shutdowns resumed. Waiting for fresh UPS readings."
            try:
                self.store.save()
            except Exception:
                self.store.data = old
                raise
            if active:
                self.cancel_serial += 1
                pending, self.pending = self.pending, None
                if pending and pending.get("wake_epoch") is not None:
                    try:
                        self.controller.clear({"request_id": pending["request_id"]})
                    except (PolicyError, OSError, ValueError, KeyError, TypeError):
                        self.stale_alarm_checked = False
                        self.message = {"text": "Keep awake is on. All app shutdowns are suspended, but the previous wake alarm could not be cleared.", "action": "Select Check again while the Pi remains on.", "error": True}
                        return
            else:
                self.recovery.battery_since = self.recovery.mains_since = self.recovery.unknown_since = None
            self.message = {"text": "Keep awake is on. All app shutdowns are suspended, including emergency UPS shutdowns." if active else "Shutdowns resumed using your saved Calendar and UPS settings.", "action": "Monitoring and messages continue." if active else "Normal setup and fresh-reading checks still apply.", "error": False}
        self.recovery.notice()

    def prepare(self):
        self.refresh()
        if not self.checks.get("can_prepare"):
            raise UserError("Preparation is not available yet.", self.checks.get("action", "Select Check again."))
        snapshot = deepcopy(self.host_snapshot)
        firmware = self.supervisor.firmware_info()
        if firmware.get("update_pending") is not False or firmware.get("update_blocked") is not False or str(firmware.get("current_version")) != snapshot["current_version"]:
            raise UserError("A firmware update needs attention first.", "Finish the update in Settings → System → Updates and reboot, then select Check again.")
        atomic_json(self.store.path.parent / "firmware-backup.json", {"config": snapshot["config"], "version": snapshot["current_version"], "boot_id": self.host.boot_id(), "saved_at": self.clock()})
        # Save the reboot requirement BEFORE writing, so an interruption cannot
        # silently authorize another write or a shutdown on this boot.
        with self.lock:
            expected = sha(json.dumps(config_values(patched_config(snapshot["config"])), sort_keys=True))
            self.store.data["preparation"] = {"boot_id": self.host.boot_id(), "reboot_required": True, "expected_config_fingerprint": expected}
            self.store.data["test"] = {}
            self.store.save()
        result = self.host.apply(snapshot)
        with self.lock:
            self.store.data["preparation"].update(result)
            self.store.save()
            self.message = {"text": "Wake settings prepared. Reboot the Pi to finish.", "action": "Select Reboot Pi, leave the power connected, then reopen this app.", "error": False}
        self.refresh()

    def start_shutdown(self, kind, serial, calendar_key=None):
        self._require_ready(require_test=kind != "test")
        with self.lock:
            if serial != self.cancel_serial or self.store.data["keep_awake"]:
                return
            if kind == "schedule" and not self.store.data["schedule"]["enabled"]:
                return
            if kind != "test" and self.recovery.blocks_calendar():
                raise UserError("UPS recovery has paused normal shutdowns.", "Wait for stable utility power or turn UPS recovery off before running a separate wake test or calendar shutdown.")
            if kind == "test" and self.store.data["recovery"]["enabled"]:
                source = self.recovery.source()
                if not source or not source["ok"] or source["power_state"] != "mains":
                    raise UserError("Wait for utility power before this separate wake test.", "Use the active UPS recovery policy during the outage. Run a new wake test when utility power is available.")
            schedule = deepcopy(self.store.data["schedule"])
            period = None
            if kind != "test":
                if kind != "schedule":
                    raise UserError("Use the calendar to choose shutdown and wake times.", "Add or edit an off period in Home Assistant's Calendar.")
                period = self._calendar_period(calendar_key, due=True)
            request_id = "pi5-" + secrets.token_hex(12)
            payload = {"request_id": request_id, "timezone": schedule["timezone"]}
            payload.update({"mode": "relative", "seconds": TEST_SECONDS} if kind == "test" else {"mode": "at", "wake_epoch": period["end_epoch"]} if period else {})
            result = self.controller.arm(payload)
            self.pending = {"kind": kind, "request_id": request_id, "wake_epoch": result["wake_epoch"], "deadline": self.monotonic() + COUNTDOWN, "fingerprint": self.checks["fingerprint"], "serial": serial}
            if period:
                self.pending["calendar_key"] = period["key"]
                self.pending["calendar_entity_id"] = schedule["calendar_entity_id"]
            if kind == "test":
                self.store.data["schedule"]["enabled"] = False
                self.store.data["recovery"].update(enabled=False, qualification=None)
                self.store.data["test"] = {}
                self.store.save()
            self.message = {"text": "The Pi will shut down in 30 seconds.", "action": "Select Keep Pi awake to cancel. Home Assistant will be offline until the Pi wakes.", "error": False}

    def finish_shutdown(self):
        with self.lock:
            pending = deepcopy(self.pending)
        if not pending:
            return
        if pending["kind"] == "ups":
            self.recovery.finish(pending)
            return
        self._require_ready(require_test=pending["kind"] != "test")
        with self.lock:
            if self.pending != pending or pending["serial"] != self.cancel_serial or self.store.data["keep_awake"]:
                return
            if self.checks["fingerprint"] != pending["fingerprint"]:
                raise UserError("The Pi's wake settings changed during the countdown.", "Keep the Pi on and run Check again followed by a new wake test.")
            if pending["kind"] == "schedule" and not self.store.data["schedule"]["enabled"]:
                self.cancel()
                return
            if pending.get("calendar_key"):
                schedule = self.store.data["schedule"]
                if schedule.get("calendar_entity_id") != pending["calendar_entity_id"]:
                    raise UserError("The selected calendar changed during the countdown.", "The Pi will stay on. Review your saved schedule.")
                self._calendar_period(pending["calendar_key"])
            self.controller.verify({"request_id": pending["request_id"], "wake_epoch": pending["wake_epoch"]})
            if pending["kind"] == "test":
                self.store.data["test"] = {"status": "waiting", "boot_id": self.host.boot_id(), "wake_epoch": pending["wake_epoch"], "fingerprint": pending["fingerprint"], "requested_at": self.clock()}
                self.store.save()
            # The lock serializes cancellation and the actual shutdown request.
            # Supervisor handles graceful host shutdown, without forcing a DB migration.
            if pending["kind"] == "schedule":
                self.wake_devices.scheduled_shutdown(pending)
            else:
                self.wake_devices.other_power_action()
            self.pending["shutdown_requested"] = True
            self.shutdown_requested_at = self.monotonic()
            self.supervisor.shutdown()
            self.pending = None
            self.message = {"text": "Shutdown requested. Reopen this app after Home Assistant returns.", "action": "Leave the Pi's power supply connected.", "error": False}

    def _failure(self, error):
        if isinstance(error, UserError):
            message, action = error.message, error.action
        elif isinstance(error, PolicyError):
            message, action = "The wake alarm could not be verified. The Pi will stay on.", "Select Check again and retry. If the wake time falls in the spring clock change, choose a time outside the skipped hour. Another app's existing wake alarm will be left in place."
        else:
            message, action = "The operation could not finish. Scheduling is paused.", "Keep the Pi on. Restart the app and select Check again; contact the app maintainer if this continues."
        LOG.warning("Operation failed: %s", type(error).__name__)
        with self.lock:
            ups_failure = self.pending and self.pending["kind"] == "ups" or self.job and self.job["kind"] == "ups"
            submitted = bool(self.pending and self.pending.get("shutdown_requested"))
            has_wake = bool(self.pending and self.pending.get("wake_epoch") is not None)
            if self.pending:
                if self.pending.get("shutdown_requested"):
                    # A timeout may mean shutdown was accepted. Removing the
                    # alarm here could leave an already shutting-down Pi off.
                    message = "Home Assistant did not confirm the shutdown request. " + ("The wake time is still set." if self.pending.get("wake_epoch") is not None else "No timed wake is promised for this final shutdown.")
                    action = "Leave the power connected. If the Pi stays on, select Check again and retry when ready."
                else:
                    try:
                        if self.pending.get("wake_epoch") is not None:
                            self.controller.clear({"request_id": self.pending["request_id"]})
                    except (OSError, PolicyError, ValueError):
                        pass
                self.pending = None
            if ups_failure:
                try:
                    self.recovery.failed(submitted, has_wake)
                except (OSError, UserError):
                    pass  # An unsuccessful claim write never authorizes a retry.
            if not isinstance(error, (UserError, PolicyError)):
                self.checks["ok"] = False
            self.message = {"text": message, "action": action, "error": True}
            if getattr(error, "details", None):
                self.message["details"] = error.details

    def tick(self):
        with self.lock:
            if self.shutdown_requested_at is not None or self.store.data["keep_awake"]:
                return
            pending = self.pending
        if pending and self.monotonic() >= pending["deadline"]:
            try:
                self.finish_shutdown()
            except (UserError, PolicyError, OSError, ValueError, KeyError, TypeError) as error:
                self._failure(error)
            return
        if not pending and not self.job:
            try:
                with self.lock:
                    if self.recovery.poll():
                        return
            except (UserError, PolicyError, OSError, ValueError, KeyError, TypeError) as error:
                self._failure(error)
                return
        with self.lock:
            schedule = self.store.data["schedule"]
            if not schedule["enabled"] or self.pending or self.job or self.store.read_only:
                return
            if not self._calendar_ready():
                return
            period = due_period(self.calendar_info["periods"], self.clock())
            if not period or self.store.data.get("last_calendar_attempt") == period["attempt_key"]:
                return
            self.store.data["last_calendar_attempt"] = period["attempt_key"]
            try:
                self.store.save()
                self.begin_job("schedule", {"confirmed": True, "calendar_key": period["key"]})
            except (OSError, UserError) as error:
                self._failure(error)

    def process_task(self):
        try:
            kind, payload, serial = self.tasks.get_nowait()
        except queue.Empty:
            return False
        try:
            with self.lock:
                if kind in ("reboot", "test", "sleep", "schedule", "ups") and (serial != self.cancel_serial or self.store.data["keep_awake"]):
                    return True
            if kind == "check":
                self.refresh(force_calendar_discovery=True)
                with self.lock:
                    if self.checks.get("ok") and self.shutdown_requested_at is not None and self.monotonic() - self.shutdown_requested_at >= 120:
                        self.shutdown_requested_at = None
            elif kind == "scan-ups":
                self.refresh_power(settings=True)
            elif kind == "prepare":
                self.prepare()
            elif kind == "reboot":
                self.refresh()
                if (payload.get("assist_reviewed") is True or payload.get("dashboard_reviewed") is True) and not self.host_shutdown_supported:
                    raise UserError("This host could not be verified for a reboot.", "Keep the Pi on and check Setup before requesting another reboot.")
                if not self.checks.get("needs_reboot") and payload.get("assist_reviewed") is not True and payload.get("dashboard_reviewed") is not True:
                    raise UserError("A setup reboot is not needed right now.", "Select Check again and continue with the wake test.")
                with self.lock:
                    if serial != self.cancel_serial or self.store.data["keep_awake"]:
                        return True
                    self.shutdown_requested_at = self.monotonic()
                    self.wake_devices.other_power_action()
                    self.supervisor.reboot()
            elif kind == "ups":
                self.recovery.start(serial, payload["retry"], payload["reason"], payload.get("emergency", False))
            else:
                self.start_shutdown("manual" if kind == "sleep" else kind, serial, payload.get("calendar_key"))
        except (UserError, PolicyError, OSError, ValueError, KeyError, TypeError) as error:
            self._failure(error)
        finally:
            with self.lock:
                self.job = None
            self.tasks.task_done()
        return True

    def run(self):
        # Phone/Core requests must not occupy the RTC/UPS control worker.
        threading.Thread(target=self.messages.run, name="phone-messages", daemon=True).start()
        threading.Thread(target=self.assistant.run, name="assist-discovery", daemon=True).start()
        threading.Thread(target=self.wake_devices.run, name="wake-devices", daemon=True).start()
        while not self.stop_event.is_set():
            self.process_task()
            self.tick()
            if not self.pending and not self.job:
                if self.store.data["outage"] and self.recovery.protection_eligible():
                    # Outage protection must not wait for a slow firmware/RTC
                    # inspection. Retry preflight still verifies wake settings.
                    if self.monotonic() - self.last_power_refresh >= 10:
                        self.refresh_power()
                elif self.monotonic() - self.last_refresh >= 30:
                    self.refresh()
            self.stop_event.wait(0.5)


class IngressHandler(BaseHTTPRequestHandler):
    application: Application
    allowed_peers = frozenset({"172.30.32.2"})

    def log_message(self, *args):
        pass  # Do not log ingress session paths or authentication headers.

    def _send(self, status, body, content_type="application/json"):
        if isinstance(body, dict):
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'self'; object-src 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _allowed(self):
        if self.client_address[0] not in self.allowed_peers:
            self._send(403, {"message": "Open this app through Home Assistant."})
            return False
        return True

    def do_GET(self):
        if not self._allowed():
            return
        path = urlsplit(self.path).path
        if path == "/api/status":
            self._send(200, self.application.snapshot())
        elif path == "/api/message-options":
            with self.application.lock:
                options = deepcopy(self.application.messages.options)
            self._send(200, options)
        elif path in ("/", "/index.html", "/app.js", "/style.css"):
            filename = "index.html" if path == "/" else path[1:]
            types = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8", "style.css": "text/css; charset=utf-8"}
            self._send(200, (WEB / filename).read_bytes(), types[filename])
        else:
            self._send(404, {"message": "That page was not found."})

    def do_POST(self):
        if not self._allowed():
            return
        if not hmac.compare_digest(self.headers.get("X-Pi5-CSRF", "").encode(), self.application.csrf.encode()):
            self._send(403, {"message": "Reopen this app from Home Assistant and try again.", "action": "Refresh this screen."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= 4096 or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError()
            self.connection.settimeout(5)
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError()
        except (OSError, ValueError):
            self._send(400, {"message": "The request could not be read.", "action": "Refresh this screen and try again."})
            return
        path = urlsplit(self.path).path
        try:
            if path == "/api/settings":
                self.application.save_settings(payload)
            elif path == "/api/connect-dashboard":
                self.application.dashboard.connect(payload)
            elif path == "/api/create-calendar":
                self.application.dashboard.create_calendar(payload)
            elif path == "/api/power-settings":
                self.application.save_power_settings(payload)
            elif path == "/api/recovery-settings":
                self.application.recovery.save_settings(payload)
            elif path == "/api/message-settings":
                self.application.messages.save_settings(payload)
            elif path == "/api/connect-assist":
                self.application.assistant.connect(payload)
            elif path == "/api/assist-settings":
                self.application.assistant.save_settings(payload)
            elif path == "/api/assist-review":
                self.application.assistant.review(payload)
            elif path in ("/api/scan-messages", "/api/preview-message", "/api/send-message"):
                self.application.messages.begin({"/api/scan-messages": "scan", "/api/preview-message": "preview", "/api/send-message": "send"}[path], payload)
            elif path == "/api/enable-nut-sensor":
                self.application.enable_nut_sensor(payload)
            elif path == "/api/pause-rtc-retries":
                self.application.recovery.pause_retries()
            elif path == "/api/confirm-test":
                self.application.confirm_test(payload)
            elif path == "/api/reject-test":
                self.application.reject_test()
            elif path == "/api/cancel":
                self.application.cancel()
            elif path == "/api/keep-awake":
                self.application.set_keep_awake(payload)
            elif path in ("/api/check", "/api/scan-ups", "/api/prepare", "/api/reboot", "/api/test"):
                self.application.begin_job(path.rsplit("/", 1)[1], payload)
            else:
                self._send(404, {"message": "That action was not found."})
                return
            self._send(200, {"ok": True})
        except UserError as error:
            self._send(409, {"message": error.message, "action": error.action})
        except (OSError, PolicyError, ValueError, TypeError, KeyError):
            self._send(503, {"message": "The action could not finish.", "action": "Keep the Pi on. Refresh this screen and try again; contact the app maintainer if this continues."})


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app = Application("/data", LinuxRTC(), Supervisor(), Host())
    IngressHandler.application = app
    AssistHandler.assistant = app.assistant
    worker = threading.Thread(target=app.run, daemon=True)
    worker.start()
    LOG.info("Pi 5 Wake/Sleep %s: open the app in Home Assistant to finish setup.", VERSION)
    server = ThreadingHTTPServer(("0.0.0.0", 8099), IngressHandler)
    companion = ThreadingHTTPServer(("0.0.0.0", ASSIST_PORT), AssistHandler)
    threading.Thread(target=companion.serve_forever, name="assist-api", daemon=True).start()
    try:
        server.serve_forever()
    finally:
        app.stop_event.set()
        server.server_close()
        companion.shutdown()
        companion.server_close()


if __name__ == "__main__":
    main()
