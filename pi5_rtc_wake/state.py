"""Versioned, atomic settings stored in the app's persistent /data directory."""

from copy import deepcopy
import json
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCHEMA_VERSION = 10


class UserError(Exception):
    def __init__(self, message, action):
        super().__init__(message)
        self.message = message
        self.action = action


def validate_schedule(value):
    if not isinstance(value, dict) or type(value.get("enabled")) is not bool:
        raise UserError("The schedule could not be saved.", "Choose whether scheduling is on, then try Save again.")
    if value.get("source", "calendar") != "calendar" or ("source" not in value and ("sleep_time" in value or "wake_time" in value)):
        raise UserError("All scheduled times now belong in Home Assistant's Calendar.", "Refresh this page, choose a calendar, and save. Add dates and repeats in Calendar.")
    timezone = value.get("timezone")
    try:
        if not isinstance(timezone, str) or len(timezone) > 100:
            raise ValueError()
        ZoneInfo(timezone)
    except (ValueError, ZoneInfoNotFoundError):
        raise UserError("The time zone is not recognized.", "Choose a time zone such as America/Chicago, then select Save.") from None
    entity = value.get("calendar_entity_id")
    if entity in (None, "") and not value["enabled"]:
        entity = None
    elif not isinstance(entity, str) or not re.fullmatch(r"calendar\.[a-z0-9_]{1,150}", entity):
        raise UserError("Choose a Home Assistant calendar.", "Create a dedicated Local Calendar, select it here, and save.")
    return {"source": "calendar", "calendar_entity_id": entity, "timezone": timezone, "enabled": value["enabled"]}


def migrate_schedule(loaded, version):
    value = loaded["schedule"]
    if version >= 4:
        return validate_schedule(value), None
    if not isinstance(value, dict) or type(value.get("enabled")) is not bool:
        raise ValueError("invalid legacy schedule")
    if value.get("source") == "calendar":
        return validate_schedule({key: value.get(key) for key in ("source", "calendar_entity_id", "timezone", "enabled")}), None
    for key in ("sleep_time", "wake_time"):
        if not isinstance(value.get(key), str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value[key]):
            raise ValueError("invalid legacy time")
    schedule = validate_schedule({"enabled": False, "timezone": value.get("timezone")})
    return schedule, ("The old daily schedule is paused. Create an off period in Home Assistant's Calendar from "
                      + value["sleep_time"] + " to " + value["wake_time"] + " (next day if overnight), choose its repeats, then select the calendar and enable scheduling.")



def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w") as stream:
        os.chmod(temp, 0o600)
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class StateStore:
    def __init__(self, directory):
        self.path = Path(directory) / "settings.json"
        self.backup = self.path.with_name("settings.previous.json")
        self.read_only = False
        self.notice = None
        default = {"schema_version": SCHEMA_VERSION, "keep_awake": False,
                   "schedule": {"source": "calendar", "calendar_entity_id": None, "timezone": "UTC", "enabled": False},
                   "timezone_detected": False, "test": {}, "preparation": {}, "ups": {"source_id": None, "notifications": False, "low_battery_percent": 25}}
        self.data = deepcopy(default)
        from ups_recovery import DEFAULTS, validate_policy, validate_session
        self.data.update(recovery=deepcopy(DEFAULTS), outage={})
        from phone_messages import DEFAULTS as MESSAGE_DEFAULTS, validate_settings as validate_messages, validate_record
        self.data.update(messages=deepcopy(MESSAGE_DEFAULTS), message_boot={})
        from assist import DEFAULTS as ASSIST_DEFAULTS, validate_settings as validate_assist
        self.data["assist"] = deepcopy(ASSIST_DEFAULTS)
        self.data["dashboard"] = {"connected": False}
        if not self.path.exists() and not self.backup.exists():
            return
        for path in (self.path, self.backup):
            try:
                loaded = json.loads(path.read_text())
                version = loaded.get("schema_version", 1)
                if type(version) is not int or version < 1:
                    raise ValueError("invalid schema")
                if version > SCHEMA_VERSION:
                    self.read_only = True
                    self.notice = "These settings were saved by a newer app. Update this app before changing them."
                    return
                schedule, migration_notice = migrate_schedule(loaded, version)
                for key in ("test", "preparation"):
                    if not isinstance(loaded.get(key, {}), dict):
                        raise ValueError("invalid state")
                self.data.update(loaded)
                if "ups" in loaded:
                    from power_sources import validate_settings
                    self.data["ups"] = validate_settings(loaded["ups"])
                self.data["schema_version"] = SCHEMA_VERSION
                keep_awake = loaded.get("keep_awake", False)
                if type(keep_awake) is not bool:
                    raise ValueError("invalid Keep awake setting")
                self.data["keep_awake"] = keep_awake
                self.data["schedule"] = schedule
                self.data["recovery"] = validate_policy(loaded.get("recovery", DEFAULTS))
                if version < 6 and self.data["recovery"]["enabled"]:
                    self.data["recovery"]["owner_confirmed"] = False
                    self.data["migration_notice"] = "Review UPS shutdown ownership before automatic protection resumes. Your Calendar, timings, UPS selection, and wake-test result were kept."
                self.data["outage"] = validate_session(loaded.get("outage", {}))
                self.data["messages"] = validate_messages(loaded.get("messages", MESSAGE_DEFAULTS))
                self.data["message_boot"] = validate_record(loaded.get("message_boot", {}))
                self.data["assist"] = validate_assist(loaded.get("assist", ASSIST_DEFAULTS))
                dashboard = loaded.get("dashboard", {"connected": False})
                if not isinstance(dashboard, dict) or set(dashboard) != {"connected"} or type(dashboard["connected"]) is not bool:
                    raise ValueError("invalid dashboard settings")
                self.data["dashboard"] = dashboard
                self.data.pop("last_attempt_date", None)
                if migration_notice:
                    self.data["migration_notice"] = migration_notice
                self.data["timezone_detected"] = loaded.get("timezone_detected", True)
                if path == self.backup:
                    self.data["schedule"]["enabled"] = False
                    self.data["recovery"]["enabled"] = False
                    self.data["recovery"]["qualification"] = None
                    self.data["messages"]["enabled"] = False
                    self.data["assist"]["enabled"] = False
                    self.data["assist"]["allow_requests"] = False
                    self.notice = "The last saved settings were restored. Review your times and enable the schedule again."
                return
            except (OSError, ValueError, KeyError, TypeError, UserError):
                continue
        self.read_only = True
        self.notice = "The saved settings could not be read. Restore this app from a Home Assistant backup, or contact the app maintainer."

    def save(self):
        if self.read_only:
            raise UserError("Settings are protected from being overwritten.", self.notice)
        # A corrupt primary is never copied over a known good recovery copy.
        try:
            old = json.loads(self.path.read_text())
            if type(old.get("schema_version")) is int and 1 <= old["schema_version"] <= SCHEMA_VERSION:
                migrate_schedule(old, old["schema_version"])
                atomic_json(self.backup, old)
        except (OSError, ValueError, KeyError, TypeError, UserError):
            pass
        atomic_json(self.path, self.data)
