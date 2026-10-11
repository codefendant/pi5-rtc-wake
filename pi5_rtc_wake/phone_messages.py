"""Opt-in Companion app messages, isolated from RTC and UPS operations."""

from copy import deepcopy
from datetime import datetime
import logging
import math
import queue
import re
import unicodedata
from zoneinfo import ZoneInfo

from state import UserError

LOG = logging.getLogger("pi5_rtc_wake")
DEFAULTS = {"enabled": False, "recipient": None, "fields": []}
ENTITY = re.compile(r"[a-z_]+\.[a-z0-9_]{1,150}")
RECIPIENT = re.compile(r"(?:service:mobile_app_[a-z0-9_]{1,150}|entity:notify\.[a-z0-9_]{1,150})")
DOMAINS = {"sensor", "binary_sensor", "light", "switch", "lock", "alarm_control_panel",
           "weather", "climate", "cover", "fan", "input_number", "input_boolean", "input_select"}
ATTRIBUTES = {"weather": {"temperature": "temperature_unit", "humidity": "%"},
              "climate": {"current_temperature": "temperature_unit", "current_humidity": "%"}}
MAX_FIELDS = 12
STARTUP_DELAY = 60
READING_WAIT = 180


def text(value, limit=100):
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return ""
    return " ".join("".join(c for c in str(value) if not unicodedata.category(c).startswith("C")).split())[:limit]


def field_parts(value):
    if not isinstance(value, str) or len(value) > 190:
        raise ValueError("invalid field")
    entity, separator, attribute = value.partition("@")
    if not ENTITY.fullmatch(entity) or entity.split(".")[0] not in DOMAINS:
        raise ValueError("invalid entity")
    if separator and attribute not in ATTRIBUTES.get(entity.split(".")[0], {}):
        raise ValueError("unsupported attribute")
    return entity, attribute or None


def validate_settings(value):
    try:
        if not isinstance(value, dict) or type(value.get("enabled")) is not bool:
            raise ValueError()
        recipient = value.get("recipient") or None
        if recipient is not None and (not isinstance(recipient, str) or not RECIPIENT.fullmatch(recipient)):
            raise ValueError()
        if value["enabled"] and recipient is None:
            raise ValueError()
        fields = value.get("fields", [])
        if not isinstance(fields, list) or len(fields) > MAX_FIELDS or len(set(fields)) != len(fields):
            raise ValueError()
        for field in fields:
            field_parts(field)
        return {"enabled": value["enabled"], "recipient": recipient, "fields": list(fields)}
    except (ValueError, TypeError):
        raise UserError("The phone settings could not be saved.", "Choose a discovered phone and up to twelve readings, then save again.") from None


def validate_record(value):
    if not isinstance(value, dict):
        raise ValueError("invalid phone message record")
    if not value:
        return {}
    if (not isinstance(value.get("boot_id"), str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", value["boot_id"])
            or value.get("state") not in ("configured", "submitted", "accepted", "unconfirmed")
            or type(value.get("at")) not in (float, int) or not math.isfinite(value["at"]) or value["at"] <= 0):
        raise ValueError("invalid phone message record")
    return {key: value[key] for key in ("boot_id", "state", "at")}


def states_by_id(rows):
    if not isinstance(rows, list) or len(rows) > 50000:
        raise UserError("Home Assistant's readings could not be listed.", "Wait for Home Assistant to finish starting, then select Find phones and readings.")
    return {row["entity_id"]: row for row in rows if isinstance(row, dict)
            and isinstance(row.get("entity_id"), str) and ENTITY.fullmatch(row["entity_id"])
            and isinstance(row.get("attributes"), dict) and isinstance(row.get("state"), str)}


def discover_recipients(services, metadata, states):
    if not isinstance(services, list) or len(services) > 1000:
        raise UserError("Phone notification actions could not be read.", "Open the Home Assistant Companion app on your phone, then find phones again.")
    notify = next((row.get("services") for row in services if isinstance(row, dict) and row.get("domain") == "notify"), {})
    if not isinstance(notify, dict):
        raise UserError("Phone notification actions could not be read.", "Update Home Assistant and try again.")
    choices = []
    if "send_message" in notify:
        for entity, row in metadata.items():
            if (entity.startswith("notify.") and row.get("platform") == "mobile_app"
                    and not row.get("disabled") and entity in states):
                attrs = states[entity]["attributes"]
                choices.append({"id": "entity:" + entity,
                    "name": text(attrs.get("friendly_name") or row.get("name") or entity), "kind": "Phone entity"})
    for service, details in notify.items():
        if isinstance(service, str) and re.fullmatch(r"mobile_app_[a-z0-9_]{1,150}", service):
            name = details.get("name") if isinstance(details, dict) else None
            choices.append({"id": "service:" + service, "name": text(name or service.removeprefix("mobile_app_").replace("_", " ")), "kind": "Companion app action"})
    if len(choices) > 200:
        raise UserError("Too many phone notification targets were found.", "Review the Mobile App integration in Home Assistant, then find phones again.")
    return sorted(choices, key=lambda row: (row["kind"] != "Phone entity", row["name"].casefold(), row["id"]))


def category(entity, attributes, metadata, selected_ups):
    domain = entity.split(".")[0]
    device_class = attributes.get("device_class")
    if selected_ups and selected_ups.startswith("nut:") and metadata.get("device_id") == selected_ups[4:]:
        return "UPS", True
    if device_class == "battery":
        return "Battery", True
    if device_class == "temperature" or domain == "climate":
        return "Temperature", True
    if domain == "weather":
        return "Weather", True
    if domain in ("alarm_control_panel", "lock") or device_class in ("door", "window", "smoke", "gas", "safety", "problem", "tamper", "moisture"):
        return "Security & maintenance", True
    if device_class in ("energy", "power"):
        return "Energy & power", True
    if domain == "light":
        return "Lights", False
    return "Other readings", False


def discover_fields(states, metadata, selected_ups, temperature_unit=""):
    choices = []
    for entity, row in states.items():
        if entity.split(".")[0] not in DOMAINS:
            continue
        meta = metadata.get(entity, {})
        if meta.get("disabled") or meta.get("hidden") or meta.get("entity_category") == "config":
            continue
        attrs = row["attributes"]
        name = text(attrs.get("friendly_name") or meta.get("name") or entity)
        group, suggested = category(entity, attrs, meta, selected_ups)
        choices.append({"id": entity, "name": name, "area": meta.get("area", ""), "category": group,
                        "suggested": suggested, "unit": text(attrs.get("unit_of_measurement"), 20)})
        for attribute, unit in ATTRIBUTES.get(entity.split(".")[0], {}).items():
            if attribute in attrs:
                choices.append({"id": entity + "@" + attribute,
                    "name": name + " · " + attribute.removeprefix("current_").replace("_", " "),
                    "area": meta.get("area", ""), "category": group, "suggested": True,
                    "unit": text(attrs.get(unit) or temperature_unit, 20) if unit != "%" else "%"})
    if len(choices) > 8000:
        raise UserError("There are too many readings to show in this picker.", "Contact the app maintainer for help with this Home Assistant installation.")
    priority = {name: n for n, name in enumerate(("UPS", "Battery", "Temperature", "Weather", "Security & maintenance", "Energy & power", "Lights", "Other readings"))}
    return sorted(choices, key=lambda row: (priority[row["category"]], row["name"].casefold(), row["id"]))


def observed_epoch(row):
    try:
        value = row.get("last_reported") or row.get("last_updated")
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return stamp.timestamp() if stamp.tzinfo is not None else None
    except (TypeError, ValueError, AttributeError, OverflowError):
        return None


def reading_line(field, states, choices, boot_epoch, now):
    entity, attribute = field_parts(field)
    choice = choices.get(field, {"name": entity, "unit": ""})
    row = states.get(entity)
    name = text(choice["name"], 100)
    if field not in choices or row is None or row["state"] in ("unknown", "unavailable"):
        return name + ": Not available", False
    observed = observed_epoch(row)
    if (row["attributes"].get("restored") is True or observed is None or observed < boot_epoch
            or observed > now + 60):
        return name + ": Waiting for a reading from this boot", False
    value = row["attributes"].get(attribute) if attribute else row["state"]
    value = text(value, 80)
    if not value:
        return name + ": Not available", False
    age = max(0, now - observed)
    suffix = " (reported " + str(int(age // 3600)) + "h ago)" if age >= 3600 else ""
    return name + ": " + value + (" " + choice["unit"] if choice["unit"] else "") + suffix, True


def date_text(epoch, zone):
    return datetime.fromtimestamp(epoch, ZoneInfo(zone)).strftime("%a %d %b %Y, %H:%M %Z (UTC%z)")


def build_message(status, fields, states, choices, now, boot_epoch, *, wake=False):
    zone = status["schedule"]["timezone"]
    seconds = max(0, int(now - boot_epoch))
    days, hours, minutes = seconds // 86400, seconds // 3600 % 24, seconds // 60 % 60
    uptime = (str(days) + "d " if days else "") + str(hours) + "h " + str(minutes) + "m"
    lines = ["Pi 5 is awake." if wake else "Pi 5 status.", "Uptime: " + uptime]
    pending = status.get("pending")
    if status.get("keep_awake"):
        lines.extend(["Next shutdown: Keep awake is on; all app shutdowns are suspended, including UPS protection.",
                      "Next wake: No app shutdown or wake is planned until you resume."])
    elif pending:
        lines.extend(["Next shutdown: " + date_text(now + pending["remaining_seconds"], zone),
                      "Next wake: " + (date_text(pending["wake_epoch"], zone) if pending.get("wake_epoch") else "No timed wake; final UPS shutdown.")])
    elif status.get("recovery", {}).get("calendar_paused"):
        lines.extend(["Next shutdown: UPS protection controls shutdown; timing depends on fresh UPS readings.",
                      "Next wake: Conditional UPS retry; no confirmed wake time yet."])
    elif not status["schedule"]["enabled"]:
        lines.extend(["Next shutdown: Calendar scheduling is off.", "Next wake: No Calendar wake is armed."])
    elif not status.get("schedule_active"):
        lines.extend(["Next shutdown: Calendar scheduling is paused; check Setup and Calendar.", "Next wake: No confirmed Calendar wake time."])
    elif status.get("next_sleep_epoch"):
        lines.extend(["Next shutdown: " + date_text(status["next_sleep_epoch"], zone),
                      "Next wake: " + date_text(status["next_wake_epoch"], zone) + " (planned; rechecked before shutdown)"])
    else:
        lines.extend(["Next shutdown: No off period in the next 31 days.", "Next wake: Waiting for the next Calendar off period."])
    current = True
    for field in fields:
        line, available = reading_line(field, states, choices, boot_epoch, now)
        lines.append(line)
        current = current and available
    message = "\n".join(lines)
    if len(message.encode("utf-8")) > 3900:
        raise UserError("The phone message is too long.", "Select fewer readings or use shorter entity names in Home Assistant.")
    return {"title": "Pi 5 is awake" if wake else "Pi 5 status", "message": message}, current


class PhoneMessages:
    def __init__(self, app):
        self.app = app
        self.tasks = queue.Queue(maxsize=1)
        self.busy = None
        self.options = {"recipients": [], "fields": []}
        self.options_revision = 0
        self.discovered = False
        self.preview = None
        self.result = {"message": "Wake messages are enabled. Waiting for a new Pi boot." if app.store.data["messages"]["enabled"] else "Automatic wake messages are off. Find your phone, choose any extra readings, and save.", "error": False}
        if app.store.data["message_boot"].get("state") in ("submitted", "unconfirmed"):
            self.result = {"message": "The last wake message was submitted, but delivery was not confirmed. Check your phone before sending another status.", "error": True}
        self.started = app.monotonic()
        self.last_poll = -math.inf

    def snapshot(self):
        return {"settings": deepcopy(self.app.store.data["messages"]), "busy": self.busy,
                "options_revision": self.options_revision, "discovered": self.discovered,
                "preview": deepcopy(self.preview), "result": deepcopy(self.result),
                "wake_record": deepcopy(self.app.store.data["message_boot"])}

    def _read(self):
        # Network requests happen only in this worker, without the app lock.
        states = states_by_id(self.app.supervisor.message_states())
        metadata = self.app.supervisor.message_metadata()
        if not isinstance(metadata, dict) or len(metadata) > 50000:
            raise UserError("Home Assistant's entity settings could not be read.", "Try Find phones and readings again after Home Assistant has started.")
        services = self.app.supervisor.message_services()
        temperature_unit = self.app.supervisor.message_temperature_unit() if any(entity.startswith("climate.") for entity in states) else ""
        with self.app.lock:
            source = self.app.store.data["ups"]["source_id"]
        options = {"recipients": discover_recipients(services, metadata, states),
                   "fields": discover_fields(states, metadata, source, temperature_unit)}
        with self.app.lock:
            if self.options != options or not self.discovered:
                self.options_revision += 1
            self.options, self.discovered = options, True
        return states, {row["id"]: row for row in options["fields"]}, options["recipients"]

    def save_settings(self, value):
        settings = validate_settings(value)
        with self.app.lock:
            if self.busy:
                raise UserError("A phone message action is in progress.", "Wait for it to finish, then save.")
            old = deepcopy(self.app.store.data)
            if settings["enabled"] and (not self.discovered or settings["recipient"] not in {row["id"] for row in self.options["recipients"]}):
                raise UserError("Choose a phone that Home Assistant can notify.", "Find phones and readings, select your phone, and save again.")
            # Saving/enabling is not a Pi boot and must not send a surprise push.
            self.app.store.data["messages"] = settings
            try:
                self.app.store.data["message_boot"] = {"boot_id": self.app.host.boot_id(), "state": "configured", "at": self.app.clock()}
                self.app.store.save()
            except Exception:
                self.app.store.data = old
                raise
            self.preview = None
            self.result = {"message": "Phone settings saved. The next Pi boot will send a wake message." if settings["enabled"] else "Phone settings saved. Automatic wake messages are off; Send status now is still available.", "error": False}

    def begin(self, kind, payload):
        if kind not in ("scan", "preview", "send"):
            raise ValueError("unsupported phone action")
        with self.app.lock:
            if self.busy:
                raise UserError("A phone message action is already in progress.", "Wait for it to finish.")
            settings = validate_settings(payload.get("settings", self.app.store.data["messages"])) if kind == "preview" else deepcopy(self.app.store.data["messages"])
            if kind == "send":
                if (payload.get("confirmed") is not True or payload.get("expected_settings") != settings or not settings["recipient"]):
                    raise UserError("Confirm the phone and saved message settings before sending.", "Save your settings, preview the message, then choose Send status now.")
                if self.app.store.read_only:
                    raise UserError("Saved settings need attention.", self.app.store.notice)
            self.busy = {"scan": "Finding phones and readings…", "preview": "Preparing a preview…", "send": "Sending status to Home Assistant…"}[kind]
            self.tasks.put_nowait((kind, settings))

    def _message(self, settings, states, choices, wake=False):
        now = self.app.clock()
        boot_epoch = self.app.host.boot_epoch(now)
        if not math.isfinite(boot_epoch) or boot_epoch > now + 60 or boot_epoch <= 0:
            raise UserError("The Pi's uptime could not be read.", "Restart this app and try Preview message again.")
        return build_message(self.app.snapshot(), settings["fields"], states, choices, now, boot_epoch, wake=wake)

    def _send(self, settings, message, recipients, *, wake=False, boot_id=None):
        if settings["recipient"] not in {row["id"] for row in recipients}:
            raise UserError("The saved phone is no longer available.", "Open the Companion app on your phone, find phones again, and save the phone you want to use.")
        with self.app.lock:
            if settings != self.app.store.data["messages"] or self.app.shutdown_requested_at is not None:
                raise UserError("The phone settings changed or the Pi is shutting down.", "Preview the saved settings again when the Pi is available.")
            if wake:
                if self.app.host.boot_id() != boot_id or self.app.store.data["message_boot"].get("boot_id") == boot_id:
                    return
                old = deepcopy(self.app.store.data)
                self.app.store.data["message_boot"] = {"boot_id": boot_id, "state": "submitted", "at": self.app.clock()}
                try:
                    self.app.store.save()  # Persist before I/O; never repeat an uncertain push on restart.
                except Exception:
                    self.app.store.data = old
                    raise
        try:
            self.app.supervisor.send_phone_message(settings["recipient"], message)
        except Exception:
            if wake:
                self._record_result(boot_id, "unconfirmed")
            raise UserError("Home Assistant did not confirm the phone message.", "It may already have been delivered. Check your phone; use Send status now if you want another message. Pi shutdown protection continues normally.") from None
        if wake:
            self._record_result(boot_id, "accepted")
        with self.app.lock:
            self.result = {"message": "Message accepted by Home Assistant. Check your phone to confirm delivery.", "error": False}

    def _record_result(self, boot_id, state):
        with self.app.lock:
            record = self.app.store.data["message_boot"]
            if record.get("boot_id") == boot_id and record.get("state") == "submitted":
                record["state"] = state
                try:
                    self.app.store.save()
                except (OSError, UserError):
                    # The original persisted claim still prevents a duplicate.
                    LOG.warning("Phone message delivery result could not be saved; its boot claim remains in place.")

    def _error(self, error):
        with self.app.lock:
            self.result = {"message": error.message if isinstance(error, UserError) else "Phone messages could not be prepared.",
                           "action": error.action if isinstance(error, UserError) else "Try Find phones and readings again. Pi shutdown protection continues normally.", "error": True}

    def process_task(self):
        try:
            kind, settings = self.tasks.get_nowait()
        except queue.Empty:
            return False
        try:
            states, choices, recipients = self._read()
            if kind == "scan":
                with self.app.lock:
                    self.result = {"message": "Choose a phone and any readings you want to include." if recipients else "No phone found. Install/open the Home Assistant Companion app, allow notifications, then find phones again.", "error": not bool(recipients)}
            else:
                message, _ = self._message(settings, states, choices)
                with self.app.lock:
                    self.preview = message
                if kind == "send":
                    self._send(settings, message, recipients)
                else:
                    with self.app.lock:
                        self.result = {"message": "Preview ready. Nothing was sent to your phone.", "error": False}
        except Exception as error:
            self._error(error)
        finally:
            with self.app.lock:
                self.busy = None
            self.tasks.task_done()
        return True

    def poll_wake(self):
        app = self.app
        with app.lock:
            settings = deepcopy(app.store.data["messages"])
            if (not settings["enabled"] or app.store.read_only or self.busy or app.shutdown_requested_at is not None
                    or app.monotonic() - self.started < STARTUP_DELAY or app.monotonic() - self.last_poll < 15):
                return
            self.last_poll = app.monotonic()
        try:
            boot_id = app.host.boot_id()
            with app.lock:
                if (self.busy or settings != app.store.data["messages"]
                        or app.store.data["message_boot"].get("boot_id") == boot_id):
                    return
                self.busy = "Preparing the Pi's wake message…"
            states, choices, recipients = self._read()
            message, current = self._message(settings, states, choices, wake=True)
            with app.lock:
                waiting_calendar = settings["enabled"] and app.store.data["schedule"]["enabled"] and not app.calendar_info["ok"]
            if (not current or waiting_calendar) and app.monotonic() - self.started < STARTUP_DELAY + READING_WAIT:
                with app.lock:
                    self.result = {"message": "Waiting for selected readings from this Pi boot before sending the wake message…", "error": False}
                return
            self._send(settings, message, recipients, wake=True, boot_id=boot_id)
        except Exception as error:
            self._error(error)
        finally:
            with app.lock:
                if self.busy == "Preparing the Pi's wake message…":
                    self.busy = None

    def run(self):
        while not self.app.stop_event.is_set():
            self.process_task()
            self.poll_wake()
            self.app.stop_event.wait(0.5)
