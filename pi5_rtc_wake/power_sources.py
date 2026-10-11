"""Read-only power adapters. Discovery never authorizes a host or UPS command."""

from datetime import datetime
import math
import re

from state import UserError

MAX_AGE = 180
ENTITY_ID = re.compile(r"sensor\.[a-z0-9_]{1,150}")
SOURCE_ID = re.compile(r"(?:nut:[a-zA-Z0-9_-]{1,100}|hook:sensor\.[a-z0-9_]{1,150})")
NUT_FLAGS = frozenset("OL OB LB RB CHRG DISCHRG BYPASS CAL OFF OVER TRIM BOOST FSD ALARM TEST WAIT ECO ESS".split())

# Constant server-side template: no user input or executable plugin code is inserted.
# Filtering on the integration avoids mistaking similarly named non-NUT sensors.
DISCOVERY_TEMPLATE = """{% set ns = namespace(rows=[]) %}
{% for e in integration_entities('nut') %}
  {% set s = states[e] %}
  {% if s is not none and e.startswith('sensor.') %}
    {% set ns.rows = ns.rows + [dict(kind='nut', entity_id=e, device_id=device_id(e), name=device_attr(e,'name_by_user') or device_attr(e,'name') or e, manufacturer=device_attr(e,'manufacturer'), model=device_attr(e,'model'), state=s.state, attributes=dict(s.attributes), reported_at=s.last_reported.isoformat())] %}
  {% endif %}
{% endfor %}
{% for s in states.sensor if s.attributes.get('rtc_wake_power') is mapping %}
  {% set ns.rows = ns.rows + [dict(kind='hook', entity_id=s.entity_id, name=s.name, state=s.state, attributes=dict(s.attributes), reported_at=s.last_reported.isoformat())] %}
{% endfor %}
{{ dict(rows=ns.rows) | to_json }}"""


def number(value, maximum):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        result = float(value)
    except (ValueError, OverflowError):
        return None
    return result if math.isfinite(result) and 0 <= result <= maximum else None


def fresh(text, now):
    try:
        if not isinstance(text, str) or len(text) > 60:
            return False
        instant = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return instant.tzinfo is not None and -10 <= now - instant.timestamp() <= MAX_AGE
    except (ValueError, OverflowError, OSError):
        return False


def label(value, fallback):
    return value[:200] if isinstance(value, str) and value else fallback


def observed_epoch(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


def runtime_candidates(rows):
    result = []
    for row in rows:
        attributes = row["attributes"]
        unit = attributes.get("unit_of_measurement")
        scale = {"s": 1, "min": 60, "h": 3600}.get(unit) if isinstance(unit, str) else None
        if attributes.get("device_class") != "duration" or scale is None:
            continue
        value = number(row.get("state"), 31 * 86400 / scale)
        try:
            epoch = observed_epoch(row["reported_at"])
        except (ValueError, KeyError, TypeError, OverflowError, OSError):
            epoch = None
        result.append({"entity_id": row["entity_id"], "name": label(attributes.get("friendly_name"), row["entity_id"]),
                       "seconds": value * scale if value is not None else None, "reported_at": row.get("reported_at"), "observed_epoch": epoch})
    return result


def monitor_runtime(source, selected_entity, registry, now):
    """Display a typed reading without commissioning automatic shutdowns."""
    result = {"seconds": None, "entity_id": None, "state": "unavailable", "observed_epoch": None,
              "message": "UPS readings are unavailable. Check the UPS connection."}
    if not source:
        return result
    if source["id"].startswith("hook:"):
        value, epoch = source.get("runtime_seconds"), source.get("observed_epoch")
        if value is not None and epoch is not None and source.get("ok"):
            result.update(seconds=value, state="fresh", observed_epoch=epoch, message="Reported by the selected power hook.")
        else:
            result.update(state="missing", message="This power hook is not reporting fresh remaining runtime.")
        return result
    device_id = source["id"][4:]
    measurements = [row for row in registry if row.get("device_id") == device_id and row.get("runtime_measurement")]
    candidates = source.get("runtime_candidates", [])
    identity = selected_entity
    if not identity:
        enabled = [row for row in measurements if row.get("disabled_by") is None]
        if len(enabled) == 1:
            identity = enabled[0]["entity_id"]
        elif measurements and all(row.get("disabled_by") is not None for row in measurements):
            result.update(state="disabled", message="Battery runtime is disabled. Open Additional NUT readings below and enable it.")
            return result
        else:
            result.update(state="choose" if candidates else "missing", message="Choose the remaining-runtime sensor in Protection settings; protection can stay off." if candidates else "No remaining-runtime sensor is reporting. Check Battery runtime on the NUT device page.")
            return result
    result["entity_id"] = identity
    candidate = next((row for row in candidates if row["entity_id"] == identity), None)
    if candidate is None:
        disabled = any(row["entity_id"] == identity and row.get("disabled_by") is not None for row in measurements)
        result.update(state="disabled" if disabled else "unavailable", message="Battery runtime is disabled. Open Additional NUT readings below and enable it." if disabled else "The selected runtime sensor is unavailable. Check it on the NUT device page.")
    elif candidate["seconds"] is None:
        result.update(message="The runtime sensor has no usable reading. Check it on the NUT device page.")
    elif not fresh(candidate["reported_at"], now) or candidate["observed_epoch"] is None:
        result.update(state="stale", message="The runtime reading is more than three minutes old. Check the NUT connection.")
    else:
        seconds = candidate["seconds"]
        if source["power_state"] in ("battery", "off"):
            seconds = max(0, seconds - max(0, now - candidate["observed_epoch"]))
        result.update(seconds=seconds, state="fresh", observed_epoch=candidate["observed_epoch"], message="Live remaining runtime from " + candidate["name"] + ".")
    return result


def nut_flags(value):
    if not isinstance(value, str) or len(value) > 120:
        return None
    flags = set(value.split())
    # Vendors can add auxiliary flags. A recognized power token plus bounded
    # uppercase flags is sufficient; an unfamiliar auxiliary token must not
    # make a previously discovered UPS disappear. Conflicts remain Unknown.
    return flags if flags & {"OL", "OB", "OFF", "WAIT", "FSD"} and all(re.fullmatch(r"[A-Z][A-Z0-9_]{0,23}", flag) for flag in flags) else None


def discover_sources(value, now):
    if not isinstance(value, dict) or not isinstance(value.get("rows"), list) or len(value["rows"]) > 2000:
        raise UserError("Power sources could not be read.", "Check the NUT integration or power hook in Home Assistant, then select Find power sources.")
    devices, sources, warnings = {}, [], []
    for row in value["rows"]:
        if not isinstance(row, dict) or not ENTITY_ID.fullmatch(str(row.get("entity_id", ""))) or not isinstance(row.get("attributes"), dict):
            warnings.append("An unreadable power reading was ignored.")
            continue
        if row.get("kind") == "nut":
            device = row.get("device_id")
            if isinstance(device, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", device):
                devices.setdefault(device, []).append(row)
        elif row.get("kind") == "hook":
            hook = row["attributes"].get("rtc_wake_power")
            if not isinstance(hook, dict) or type(hook.get("schema_version")) is not int or hook["schema_version"] != 1:
                warnings.append("A power hook uses an unsupported version. Ask its developer to update it.")
                continue
            state = hook.get("power_state")
            if state not in ("mains", "battery", "off", "unknown") or not isinstance(hook.get("provider"), str):
                warnings.append("A power hook has an unreadable status. Check its integration.")
                continue
            current = row.get("state") not in ("unavailable", "unknown") and fresh(hook.get("observed_at"), now) and fresh(row.get("reported_at"), now)
            sources.append({"id": "hook:" + row["entity_id"], "name": label(row.get("name"), row["entity_id"]), "provider": label(hook["provider"], "Power hook"),
                            "ok": current and state != "unknown", "power_state": state if current else "unknown", "battery_percent": number(hook.get("battery_percent"), 100) if current else None,
                            "runtime_seconds": number(hook.get("runtime_seconds"), 31 * 86400) if current else None, "low_battery": hook.get("low_battery") is True if current else False,
                            "recovery": "unverified", "readings": [], "runtime_candidates": [], "forced_shutdown": hook.get("shutdown_requested") is True if current else False,
                            "observed_epoch": observed_epoch(hook["observed_at"]) if current else None,
                            "message": "Reported by a power hook." if current else "The power hook is unavailable or its reading is more than three minutes old."})
    for device, rows in devices.items():
        statuses = [(row, nut_flags(row.get("state"))) for row in rows]
        statuses = [(row, flags) for row, flags in statuses if flags is not None]
        if len(statuses) != 1:
            warnings.append("A NUT device needs one enabled Status data sensor. Enable it on the device's Home Assistant page.")
            continue
        row, flags = statuses[0]
        if flags - NUT_FLAGS:
            warnings.append("NUT reports additional status flags: " + ", ".join(sorted(flags - NUT_FLAGS)) + ". Power is determined only from its explicit OL/OB/OFF flags.")
        current = fresh(row.get("reported_at"), now)
        state = "unknown"
        if current and ("OL" in flags) != ("OB" in flags):
            state = "mains" if "OL" in flags else "battery"
        if current and "OFF" in flags:
            state = "off"
        batteries = [item for item in rows if item["attributes"].get("device_class") == "battery" and item["attributes"].get("unit_of_measurement") == "%" and fresh(item.get("reported_at"), now)]
        battery = number(batteries[0].get("state"), 100) if len(batteries) == 1 else None
        # Do not guess runtime from entity names: renamed sensors and manufacturer
        # settings can also have seconds units. The hook can publish a typed runtime.
        readings = [{"name": label(item["attributes"].get("friendly_name"), item["entity_id"]), "value": label(item.get("state"), "Unknown"), "unit": label(item["attributes"].get("unit_of_measurement"), "")} for item in rows[:80]]
        sources.append({"id": "nut:" + device, "name": label(row.get("name"), "NUT UPS"), "provider": "Home Assistant NUT", "manufacturer": label(row.get("manufacturer"), ""), "model": label(row.get("model"), ""),
                        "ok": current and state != "unknown", "power_state": state, "battery_percent": battery, "runtime_seconds": None, "low_battery": "LB" in flags if current else False,
                        "recovery": "unverified", "readings": readings, "runtime_candidates": runtime_candidates(rows), "forced_shutdown": "FSD" in flags if current else False,
                        "observed_epoch": observed_epoch(row["reported_at"]) if current else None,
                        "message": ("Read from Home Assistant's NUT integration." if state != "unknown" else "NUT reports conflicting or unknown power status. Check the UPS's Status data sensor.") if current else "NUT's Status data reading is more than three minutes old. Check the NUT connection."})
    identities = [source["id"] for source in sources]
    if len(set(identities)) != len(identities):
        raise UserError("Power source identities are duplicated.", "Ask the power adapter developer to correct the duplicate hook, then scan again.")
    return sorted(sources, key=lambda source: (source["name"].lower(), source["id"])), list(dict.fromkeys(warnings))


def validate_settings(value):
    if not isinstance(value, dict) or type(value.get("notifications")) is not bool:
        raise UserError("The power monitor settings could not be saved.", "Choose whether to show power notices, then save again.")
    identity = value.get("source_id") or None
    if identity is not None and (not isinstance(identity, str) or not SOURCE_ID.fullmatch(identity)):
        raise UserError("Choose an available power source.", "Select Find power sources, choose the source that powers this Pi, then save.")
    threshold = value.get("low_battery_percent")
    if type(threshold) is not int or not 5 <= threshold <= 80:
        raise UserError("Choose a battery warning from 5% to 80%.", "Change the battery warning value, then save.")
    if value["notifications"] and identity is None:
        raise UserError("Choose the power source before enabling notices.", "Select the UPS that powers this Pi and save.")
    return {"source_id": identity, "notifications": value["notifications"], "low_battery_percent": threshold}


def notice_for(source, settings, recovery_enabled=False):
    if not source or not source["ok"]:
        return {"kind": "unknown", "message": "UPS readings are unavailable. Check the power source in Home Assistant. Automatic recovery is not verified."}
    name = source["name"]
    if source["power_state"] == "battery":
        low = source["low_battery"] or source["battery_percent"] is not None and source["battery_percent"] < settings["low_battery_percent"]
        message = " is on battery and its charge is low." if low else " is supplying battery power."
        message += " Open Pi Wake & Sleep for the active shutdown and RTC recovery policy." if recovery_enabled else " Check the UPS and arrange a safe shutdown if needed. Automatic UPS shutdown is off."
        return {"kind": "low_battery" if low else "battery", "message": name + message}
    if source["power_state"] == "off":
        return {"kind": "off", "message": name + " reports that its output is off. Check which source powers this Pi."}
    return {"kind": "mains", "message": name + " reports that utility power is available."}
