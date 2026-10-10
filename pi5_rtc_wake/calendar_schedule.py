"""Read Home Assistant's expanded events; never implement recurrence rules here."""

from datetime import datetime, timezone
import hashlib
import re

from state import UserError

CALENDAR_ID = re.compile(r"calendar\.[a-z0-9_]{1,150}")
LOOKAHEAD_DAYS = 31
MAX_EVENTS = 256
MIN_PERIOD_SECONDS = 600
MAX_PERIOD_SECONDS = 7 * 24 * 60 * 60
POWER_TAG = re.compile(r"^Pi Wake & Sleep UPS v1:(retry|stop):([a-f0-9]{32})$")


def parse_periods(events, entity_id, now):
    action = "Open this calendar in Home Assistant and correct the off periods, then select Check again."
    if not isinstance(entity_id, str) or not CALENDAR_ID.fullmatch(entity_id):
        raise UserError("Choose a Home Assistant calendar.", "Create a dedicated Local Calendar, select it here, and save.")
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        raise UserError("The calendar returned too many events or an unreadable response.", "Use a dedicated calendar for the Pi's off periods, then select Check again.")
    periods = []
    for event in events:
        if not isinstance(event, dict):
            raise UserError("A calendar event could not be read.", action)
        if event.get("status") == "cancelled":
            continue
        description = event.get("description")
        marker = POWER_TAG.fullmatch(description.splitlines()[0]) if isinstance(description, str) and description else None
        epochs = []
        for field in ("start", "end"):
            value = event.get(field)
            if not isinstance(value, dict) or "date" in value:
                raise UserError("Off periods need a shutdown time and a wake time.", "Turn off All day for each event in this calendar and choose start and end times.")
            text = value.get("dateTime")
            try:
                if not isinstance(text, str) or len(text) > 60:
                    raise ValueError()
                date = datetime.fromisoformat(text.replace("Z", "+00:00"))
                if date.tzinfo is None or date.utcoffset() is None:
                    raise ValueError()
                timestamp = date.timestamp()
                if not timestamp.is_integer() or not 0 < timestamp <= 0xFFFFFFFF:
                    raise ValueError()
                epochs.append(int(timestamp))
            except (ValueError, OverflowError, OSError):
                raise UserError("A calendar event's time could not be verified.", action) from None
        start, end = epochs
        minimum = 30 if marker and marker[1] == "stop" else MIN_PERIOD_SECONDS
        if not minimum <= end - start <= MAX_PERIOD_SECONDS:
            raise UserError("Each off period must last ten minutes to seven days.", action)
        if end <= now:
            continue
        title = event.get("summary") or "Pi off"
        if not isinstance(title, str):
            raise UserError("A calendar event's title could not be read.", action)
        key = hashlib.sha256(f"{entity_id}:{start}:{end}".encode()).hexdigest()
        attempt = hashlib.sha256(f"{entity_id}:{start}".encode()).hexdigest()
        periods.append({"key": key, "attempt_key": attempt, "title": title[:200], "start_epoch": start, "end_epoch": end})
        if marker:
            periods[-1].update(power_action=marker[1], power_token=marker[2])
    periods.sort(key=lambda period: (period["start_epoch"], period["end_epoch"]))
    ordinary = [period for period in periods if not period.get("power_action")]
    for previous, period in zip(ordinary, ordinary[1:]):
        if period["start_epoch"] <= previous["end_epoch"]:
            raise UserError("The calendar's off periods overlap or touch.", "Combine these into one event, or leave a gap between them, then select Check again.")
    return periods


def due_period(periods, now):
    # Never catch up on an off period missed during a restart or API failure.
    return next((period for period in periods if not period.get("power_action") and 0 <= now - period["start_epoch"] < 60), None)


def calendar_query_window(now):
    start = datetime.fromtimestamp(now - 60, timezone.utc).isoformat()
    end = datetime.fromtimestamp(now + LOOKAHEAD_DAYS * 86400, timezone.utc).isoformat()
    return start, end
