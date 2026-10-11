"""Home Assistant APIs and a bounded host preparation bridge."""

import json
import logging
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode

from state import UserError
from host_helper import error_details, safe_details, stderr_reason
from calendar_schedule import CALENDAR_ID, calendar_query_window
from datetime import datetime, timezone
from power_sources import DISCOVERY_TEMPLATE
from ha_registry import CoreRegistry, CoreCommandError

LOG = logging.getLogger("pi5_rtc_wake")


def effective_host_capabilities():
    """Report just the three capabilities required for this fixed host bridge."""
    try:
        status = Path("/proc/self/status").read_text()
        match = re.search(r"^CapEff:\s*([0-9a-fA-F]{1,16})\s*$", status, re.M)
        if not match:
            return None
        effective = int(match.group(1), 16)
        return {name: bool(effective & (1 << number)) for name, number in
                (("SYS_ADMIN", 21), ("SYS_PTRACE", 19), ("SYS_CHROOT", 18))}
    except (OSError, ValueError):
        return None  # A diagnostic read must not replace the original failure.


class HostError(UserError):
    def __init__(self, operation, details):
        self.details = {"operation": operation, **safe_details(details)}
        location = self.details["step"]
        if location == "host_entry":
            capabilities = effective_host_capabilities()
            if capabilities is not None:
                self.details["effective_capabilities"] = capabilities
        reason = self.details.get("reason")
        support = "Open Details for support below, copy the text, and send it to the app maintainer."
        access_action = ("Open Settings → Apps → Pi 5 Wake & Sleep → Info (Add-ons on older Home Assistant versions). "
                         "Select Stop, turn Protection mode off, then select Start. Reopen Setup and select Check again. "
                         "If it is already off and this still fails after Stop → Start, " + support[0].lower() + support[1:])
        if operation == "apply":
            message = "Pi preparation could not be verified."
            action = "Keep the power connected. Reboot from Settings → System, then select Check again. " + support
        elif location == "host_entry" and reason == "permission_denied":
            message = "The app was denied access to the Pi's wake settings."
            action = access_action
        elif location == "host_entry" and (self.details["error_type"] == "FileNotFoundError" or reason == "unsupported_option"):
            message = "The app's host access tool is missing or incompatible."
            action = support + " The app needs a repair; another Pi firmware update will not fix this app tool."
        elif location in ("host_entry", "helper_start"):
            message = "The app could not start its helper on Home Assistant OS."
            action = support
        elif reason == "unexpected_os":
            message = "The app cannot access this Pi's wake settings. Check Protection mode."
            action = access_action
        else:
            labels = {"running_config": "running wake settings", "boot_partition": "boot partition",
                      "firmware_image": "installed firmware image", "image_contents": "firmware image contents",
                      "image_version": "firmware image version", "running_version": "running firmware version",
                      "pending_update": "pending firmware update"}
            message = "The Pi's " + labels.get(location, "wake settings") + " could not be checked."
            action = support
        LOG.warning("Host operation failed: %s", json.dumps(self.details, sort_keys=True))
        super().__init__(message, action)


class Supervisor:
    def __init__(self):
        self.token = os.environ.get("SUPERVISOR_TOKEN", "")

    def request(self, path, payload=None):
        if not self.token:
            raise UserError("Home Assistant could not be reached.", "Open this app from Home Assistant and select Check again.")
        request = urllib.request.Request(
            "http://supervisor" + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                result = json.loads(response.read((16 if path == "/core/api/states" else 2) * 1024 * 1024))
            if path.startswith("/core/api/"):
                return result
            if result.get("result") != "ok":
                raise ValueError("API failure")
            return result.get("data", {})
        except (OSError, ValueError, urllib.error.URLError, TypeError, AttributeError):
            raise UserError("Home Assistant did not complete the request.", "Keep the Pi on. Check Settings → System for updates or repairs, then select Check again.") from None

    def os_info(self):
        return self.request("/os/info")

    def app_info(self):
        value = self.request("/addons/self/info")
        if not isinstance(value, dict):
            raise UserError("The app's permissions could not be checked.", "Open its Info page and check Protection mode.")
        return value

    def ensure_sleep_calendar(self):
        """Create a native Local Calendar once, then resolve its actual entity ID."""
        def existing(entry_id=None):
            with CoreRegistry(self.token) as core:
                rows = core.command("config/entity_registry/list")
            if not isinstance(rows, list):
                raise UserError("The calendar list could not be checked.", "Open Calendar in Home Assistant and try again.")
            matches = [row for row in rows if isinstance(row, dict) and row.get("platform") == "local_calendar"
                       and CALENDAR_ID.fullmatch(str(row.get("entity_id", "")))
                       and (row.get("config_entry_id") == entry_id if entry_id else row.get("original_name") == "Pi Sleep")]
            if len(matches) > 1:
                raise UserError("More than one Pi Sleep calendar was found.", "Use Choose existing calendar to select the one you want.")
            if matches:
                if matches[0].get("disabled_by") is not None:
                    raise UserError("Pi Sleep already exists but is disabled.", "Enable its calendar entity in Devices & services, then try again.")
                return matches[0]["entity_id"]
            return None

        entity = existing()
        if entity:
            self.calendar_writable(entity)
            return entity
        flow = self.request("/core/api/config/config_entries/flow", {"handler": "local_calendar", "show_advanced_options": False})
        if not isinstance(flow, dict) or flow.get("type") != "form" or flow.get("step_id") != "user" or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", str(flow.get("flow_id", ""))):
            raise UserError("Home Assistant could not start calendar setup.", "Use Settings → Devices & services → Add integration → Local Calendar and name it Pi Sleep.")
        result = self.request("/core/api/config/config_entries/flow/" + flow["flow_id"],
                              {"calendar_name": "Pi Sleep", "import": "create_empty"})
        entry_id = result.get("result", {}).get("entry_id") if isinstance(result, dict) and isinstance(result.get("result"), dict) else None
        if not isinstance(result, dict) or result.get("type") not in ("create_entry", "abort"):
            raise UserError("Home Assistant did not confirm calendar creation.", "Open Calendar and check for Pi Sleep before trying again.")
        # Core may still be setting up its entity after confirming the entry.
        for _ in range(12):
            entity = existing(entry_id)
            if entity:
                self.calendar_writable(entity)
                return entity
            time.sleep(0.5)
        raise UserError("Pi Sleep is still getting ready in Home Assistant.", "Wait a moment, then select Create Pi Sleep calendar again. An existing calendar will be reused.")

    def ensure_dashboard(self, entry_id):
        """Register our cards and create an editable dashboard without replacing one."""
        from dashboard import PATH, RESOURCE, starter_config
        resource_url = RESOURCE + "?v=0.9.0-rc.4"
        try:
            with CoreRegistry(self.token) as core:
                rows = core.command("lovelace/resources/list")
                ours = [row for row in rows if isinstance(row, dict) and str(row.get("url", "")).split("?")[0] == RESOURCE]
                if not ours:
                    core.command("lovelace/resources/create", res_type="module", url=resource_url)
                else:
                    for row in ours:
                        if row.get("url") != resource_url or row.get("type") != "module":
                            core.command("lovelace/resources/update", resource_id=row["id"], res_type="module", url=resource_url)
                dashboards = core.command("lovelace/dashboards/list")
                if any(row.get("url_path") == PATH for row in dashboards if isinstance(row, dict)):
                    try:
                        core.command("lovelace/config", url_path=PATH)
                    except CoreCommandError as error:
                        if error.code != "config_not_found":
                            raise
                        # An interrupted first install can leave an empty dashboard.
                        # Only a confirmed absence of saved layout allows initialization.
                    else:
                        return {"created": False, "path": "/" + PATH, "message": "Your existing dashboard and personal cards were kept."}
                else:
                    core.command("lovelace/dashboards/create", url_path=PATH, title="Pi Wake & Sleep",
                                 icon="mdi:power-sleep", show_in_sidebar=True, require_admin=False)
                core.command("lovelace/config/save", url_path=PATH, config=starter_config(entry_id))
            return {"created": True, "path": "/" + PATH}
        except UserError:
            raise UserError("The native dashboard could not finish setup.",
                            "Keep the app running. Use storage-mode dashboard resources, then reconnect the integration in Devices & services. Your existing dashboards are kept.") from None

    def restore_dashboard(self, entry_id):
        from dashboard import PATH, restore_cards
        with CoreRegistry(self.token) as core:
            config = core.command("lovelace/config", url_path=PATH)
            core.command("lovelace/config/save", url_path=PATH, config=restore_cards(config, entry_id))
        return {"ok": True}

    def firmware_info(self):
        return self.request("/os/boards/raspberrypi/firmware")

    def timezone(self):
        return self.request("/core/api/config").get("time_zone")

    def core_version(self):
        value = self.request("/core/info")
        version = value.get("version") if isinstance(value, dict) else None
        if not isinstance(version, str):
            raise UserError("Home Assistant's version could not be checked.", "Keep the Pi on and try Connect Assist again when Home Assistant is running.")
        return version

    def assist_discovery(self, port, token):
        info = self.request("/addons/self/info")
        slug = info.get("slug") if isinstance(info, dict) else None
        if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9]{1,32}_pi5_rtc_wake", slug):
            raise UserError("This app's Assist connection could not be identified.", "Restart the app and select Connect Assist again.")
        return self.request("/discovery", {"service": "pi5_rtc_wake", "config": {
            "host": slug.replace("_", "-"), "port": port, "protocol": 1, "token": token}})

    def create_assist_event(self, entity_id, start, end, title, marker):
        if (not isinstance(entity_id, str) or not CALENDAR_ID.fullmatch(entity_id)
                or type(start) is not int or type(end) is not int or not 0 < start < end <= 0xFFFFFFFF
                or not isinstance(title, str) or not 1 <= len(title) <= 100
                or not isinstance(marker, str) or not re.fullmatch(r"Pi Wake & Sleep Assist v1:[a-f0-9]{32}", marker)):
            raise UserError("The approved off period could not be saved.", "Review the Assist request and Calendar selection.")
        return self.request("/core/api/services/calendar/create_event", {"entity_id": entity_id,
            "summary": title, "description": marker,
            "start_date_time": datetime.fromtimestamp(start, timezone.utc).isoformat(),
            "end_date_time": datetime.fromtimestamp(end, timezone.utc).isoformat()})

    def calendars(self):
        result = self.request("/core/api/calendars")
        if not isinstance(result, list) or len(result) > 200:
            raise UserError("Home Assistant's calendar list could not be read.", "Open Calendar in Home Assistant, then select Check again.")
        for item in result:
            if (not isinstance(item, dict) or not isinstance(item.get("entity_id"), str)
                    or not CALENDAR_ID.fullmatch(item["entity_id"]) or not isinstance(item.get("name"), str)):
                raise UserError("Home Assistant's calendar list could not be read.", "Open Calendar in Home Assistant, then select Check again.")
        return [{"entity_id": item["entity_id"], "name": item["name"][:200]} for item in result]

    def power_sources(self):
        return self.request("/core/api/template", {"template": DISCOVERY_TEMPLATE})

    def message_states(self):
        return self.request("/core/api/states")

    def message_services(self):
        return self.request("/core/api/services")

    def message_temperature_unit(self):
        return self.request("/core/api/config").get("unit_system", {}).get("temperature", "")

    def message_metadata(self):
        try:
            with CoreRegistry(self.token) as registry:
                return registry.message_metadata()
        except UserError:
            raise UserError("Home Assistant's phone and reading settings could not be reached.", "Wait for Home Assistant to finish starting, then select Find phones and readings. Your Pi's shutdown protection continues normally.") from None

    def send_phone_message(self, recipient, message):
        from phone_messages import RECIPIENT
        if (not isinstance(recipient, str) or not RECIPIENT.fullmatch(recipient)
                or not isinstance(message, dict) or set(message) != {"title", "message"} or message.get("title") not in ("Pi 5 is awake", "Pi 5 status")
                or not isinstance(message.get("message"), str)
                or not message["message"].startswith(("Pi 5 is awake.\n", "Pi 5 status.\n"))
                or len(message["message"].encode("utf-8")) > 3900):
            raise UserError("The phone message is not valid.", "Preview your saved message settings and try again.")
        if recipient.startswith("entity:"):
            return self.request("/core/api/services/notify/send_message", {**message, "entity_id": recipient[7:]})
        return self.request("/core/api/services/notify/" + recipient[8:], message)

    def nut_sensors(self):
        with CoreRegistry(self.token) as registry:
            return registry.nut_sensors()

    def enable_nut_sensor(self, device_id, entity_id):
        with CoreRegistry(self.token) as registry:
            return registry.enable_nut_sensor(device_id, entity_id)

    def shutdown_controller(self):
        """Read the known Community NUT app; never expose options/credentials."""
        value = self.request("/addons")
        apps = value.get("addons") if isinstance(value, dict) else None
        if not isinstance(apps, list):
            raise UserError("NUT shutdown ownership could not be checked.", "Check the NUT app's settings and restart it after changes, then Check again.")
        if not any(isinstance(app, dict) and app.get("slug") == "a0d7b954_nut" for app in apps):
            return {"state": "not_found", "addon_id": None, "message": "No supported local NUT app was found. Review other controllers before enabling RTC retries."}
        info = self.request("/addons/a0d7b954_nut/info")
        options = info.get("options", {}) if isinstance(info, dict) else {}
        setting = options.get("shutdown_host")
        host_shutdown = setting if type(setting) is bool else {"true": True, "false": False}.get(setting) if isinstance(setting, str) else None
        state = "conflict" if host_shutdown is True else "review" if host_shutdown is None or info.get("state") != "started" else "ready"
        return {"state": state, "addon_id": "a0d7b954_nut", "message": "NUT is also configured to shut down this Pi. RTC retries are blocked; choose one host-shutdown controller." if state == "conflict" else
                "Check NUT settings, start/restart it, and confirm shutdown ownership." if state == "review" else
                "NUT's saved host-shutdown option is off. Confirm NUT was restarted after any change and no other controller shuts down this Pi."}

    def power_notice(self, notice=None):
        identity = "pi5_rtc_wake_power_status"
        if notice is None:
            return self.request("/core/api/services/persistent_notification/dismiss", {"notification_id": identity})
        return self.request("/core/api/services/persistent_notification/create", {
            "notification_id": identity, "title": "Pi Wake & Sleep: power status", "message": notice["message"]})

    def recovery_notice(self, notice=None):
        identity = "pi5_rtc_wake_ups_recovery"
        if notice is None:
            return self.request("/core/api/services/persistent_notification/dismiss", {"notification_id": identity})
        return self.request("/core/api/services/persistent_notification/create", {
            "notification_id": identity, "title": "Pi Wake & Sleep: UPS recovery", "message": notice["message"]})

    def calendar_writable(self, entity_id):
        if not isinstance(entity_id, str) or not CALENDAR_ID.fullmatch(entity_id):
            raise UserError("Choose a writable calendar.", "Select a dedicated Local Calendar and save it.")
        value = self.request("/core/api/states/" + entity_id)
        features = value.get("attributes", {}).get("supported_features") if isinstance(value, dict) else None
        if type(features) is not int or not features & 1 or value.get("state") in ("unknown", "unavailable"):
            raise UserError("This calendar cannot accept recovery events.", "Use a dedicated Local Calendar that allows event creation, then save recovery again.")
        return True

    def create_power_event(self, entity_id, start, end, kind, token):
        if (not isinstance(entity_id, str) or not CALENDAR_ID.fullmatch(entity_id) or kind not in ("retry", "stop")
                or not isinstance(token, str) or not re.fullmatch(r"[a-f0-9]{32}", token)
                or type(start) is not int or type(end) is not int or not 0 < start < end <= 0xFFFFFFFF):
            raise UserError("The recovery date could not be saved.", "Check Calendar and the recovery settings.")
        return self.request("/core/api/services/calendar/create_event", {
            "entity_id": entity_id, "summary": "UPS RTC retry: Pi off" if kind == "retry" else "UPS final shutdown: manual/power restart may be needed",
            "description": "Pi Wake & Sleep UPS v1:" + kind + ":" + token,
            "start_date_time": datetime.fromtimestamp(start, timezone.utc).isoformat(),
            "end_date_time": datetime.fromtimestamp(end, timezone.utc).isoformat()})

    def calendar_events(self, entity_id, now):
        if not isinstance(entity_id, str) or not CALENDAR_ID.fullmatch(entity_id):
            raise UserError("Choose a Home Assistant calendar.", "Select a calendar and save.")
        start, end = calendar_query_window(now)
        return self.request("/core/api/calendars/" + entity_id + "?" + urlencode({"start": start, "end": end}))

    def reboot_notice(self, required):
        identity = "pi5_rtc_wake_reboot_required"
        if required:
            return self.request("/core/api/services/persistent_notification/create", {
                "notification_id": identity, "title": "Pi Wake & Sleep: reboot needed",
                "message": "Reboot the Pi to finish wake preparation or a pending firmware update. Open **Pi Wake & Sleep** and select **Reboot Pi**, or use **Settings → System** to reboot the system. Leave the power supply connected. This reminder clears after the Pi reboots and the checks succeed."})
        return self.request("/core/api/services/persistent_notification/dismiss", {"notification_id": identity})

    def shutdown(self):
        return self.request("/host/shutdown", {"force": False})

    def reboot(self):
        return self.request("/host/reboot", {"force": False})


class Host:
    def __init__(self):
        self.source = Path(__file__).with_name("host_helper.py").read_text()

    def command(self, operation, payload=None):
        if operation not in ("inspect", "apply"):
            raise ValueError("unknown host operation")
        # Catch import/startup errors too: they previously never reached main().
        program = ("import json\ntry:\n    exec(" + repr(self.source) + ")\n"
                   "except Exception as error:\n"
                   "    print(json.dumps({'ok': False, 'error': {'step': 'helper_start', "
                   "'error_type': type(error).__name__, 'errno': getattr(error, 'errno', None), "
                   "'module': getattr(error, 'name', None)}}))\n"
                   "    raise SystemExit(1)\n"
                   "main(" + repr(operation) + ", json.loads(" + repr(json.dumps(payload or {})) + "))\n")
        # Enter only the host mount namespace and root. Host PID access is
        # granted by Supervisor when the user disables Protection mode.
        # SYS_PTRACE is also required to read a more privileged host process's
        # /proc/1/ns/mnt and /proc/1/root; SYS_ADMIN alone does not allow that.
        # --wdns chooses / AFTER entering and changing root, rather than keeping
        # a directory descriptor to the app container as --wd=/ did.
        arguments = ["/usr/bin/nsenter", "--target", "1", "--mount", "--root", "--wdns=/",
                     "--", "/usr/bin/python3", "-I", "-c", "import sys; exec(sys.stdin.read())"]
        try:
            result = subprocess.run(arguments, input=program, text=True, capture_output=True,
                                    env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
                                    timeout=240 if operation == "apply" else 65)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise HostError(operation, error_details("host_entry", error)) from None
        try:
            parsed = json.loads(result.stdout)
        except (ValueError, TypeError):
            parsed = None
        if isinstance(parsed, dict) and parsed.get("ok") is False and isinstance(parsed.get("error"), dict):
            details = safe_details(parsed["error"])
            details["helper_exit_code"] = result.returncode
            raise HostError(operation, details)
        if result.returncode or not isinstance(parsed, dict) or parsed.get("ok") is not True or not isinstance(parsed.get("data"), dict):
            reason = stderr_reason(getattr(result, "stderr", None))
            raise HostError(operation, {"step": "host_entry" if result.returncode else "helper_result",
                                        "error_type": "RuntimeError" if result.returncode else "ValueError",
                                        "exit_code": result.returncode, "reason": reason or "invalid_result"})
        return parsed["data"]

    def inspect(self):
        return self.command("inspect")

    def apply(self, snapshot):
        return self.command("apply", snapshot)

    def boot_id(self):
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()

    def boot_epoch(self, now=None):
        uptime = float(Path("/proc/uptime").read_text().split()[0])
        return (time.time() if now is None else now) - uptime
