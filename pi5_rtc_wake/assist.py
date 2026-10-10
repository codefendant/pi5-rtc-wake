"""Native Assist access: bounded status, cancellation, and human-reviewed requests."""

from copy import deepcopy
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import secrets
import threading
from zoneinfo import ZoneInfo

from assist_install import Installer, DOMAIN
from calendar_schedule import parse_periods
from state import UserError, atomic_json

PROTOCOL = 1
PORT = 8098
DEFAULTS = {"enabled": False, "allow_requests": False}
KINDS = frozenset({"create_period", "set_scheduling", "wake_test", "reboot"})
TTL = 600


def validate_settings(value):
    if (not isinstance(value, dict) or set(value) != set(DEFAULTS)
            or any(type(value[key]) is not bool for key in DEFAULTS)):
        raise UserError("Assist settings could not be saved.", "Choose the Assist options on this screen and save again.")
    return deepcopy(value)


def parse_time(value):
    try:
        if not isinstance(value, str) or len(value) > 40:
            raise ValueError()
        instant = datetime.fromisoformat(value)
        if instant.tzinfo is None or instant.microsecond:
            raise ValueError()
        result = int(instant.timestamp())
        if not 0 < result <= 0xFFFFFFFF:
            raise ValueError()
        return result
    except (ValueError, OverflowError, TypeError):
        raise UserError("Use an exact date and time with a time-zone offset.",
                        "Clarify the shutdown and wake dates before requesting an off period.") from None


class Assistant:
    def __init__(self, app, data):
        self.app = app
        self.installer = Installer(data)
        self.secret_path = Path(data) / "assist_connection.json"
        self.token = None
        self.requests = {}
        self.operation_lock = threading.Lock()
        self.connection = "Not connected. Select Connect Assist to begin."
        self.last_discovery = -math.inf
        self.restart_needed = False

    def _secret(self):
        if self.token is not None:
            return self.token
        try:
            value = json.loads(self.secret_path.read_text())["token"]
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", value):
                raise ValueError()
        except FileNotFoundError:
            value = secrets.token_urlsafe(32)
            atomic_json(self.secret_path, {"token": value})
        except (OSError, ValueError, KeyError, TypeError):
            raise UserError("The Assist connection could not be read.",
                            "Keep Assist off and contact the app maintainer. Your other app settings are unchanged.") from None
        self.token = value
        return value

    def authenticate(self, header):
        import hmac
        return bool(self.token and isinstance(header, str) and
                    hmac.compare_digest(header.encode(), ("Bearer " + self.token).encode()))

    def connect(self, payload):
        if payload != {"confirmed": True}:
            raise UserError("Connect Assist was not confirmed.", "Read the Connect Assist explanation and try again.")
        if not self.operation_lock.acquire(blocking=False):
            raise UserError("An Assist operation is in progress.", "Wait for it to finish and try again.")
        try:
            version = self.app.supervisor.core_version()
            match = re.fullmatch(r"(\d+)\.(\d+)\.\d+(?:[a-z0-9.]+)?", version)
            if not match or tuple(map(int, match.groups())) < (2026, 10):
                raise UserError("Native Assist tools need Home Assistant 2026.10 or newer.",
                                "Update Home Assistant Core in Settings → System → Updates, then select Connect Assist again.")
            with self.app.lock:
                if self.app.store.read_only or self.app.job or self.app.pending or self.app.shutdown_requested_at is not None or self.app.store.data["outage"]:
                    raise UserError("Wait before connecting Assist.", "Keep the Pi on, finish any operation, and wait for stable power before installing the companion.")
            changed = self.installer.install()
            self._secret()
            with self.app.lock:
                old = deepcopy(self.app.store.data["assist"])
                self.app.store.data["assist"]["enabled"] = True
                try:
                    self.app.store.save()
                except Exception:
                    self.app.store.data["assist"] = old
                    raise
                self.restart_needed = self.restart_needed or changed
            self.discover()
            self.app.message = {"text": "Assist companion installed." if changed else "Assist connection offered to Home Assistant.",
                                "action": "Restart Home Assistant from Settings → System, then open Devices & services and add the discovered Pi Wake & Sleep integration." if changed else
                                          "Open Settings → Devices & services and add the discovered Pi Wake & Sleep integration. Choose Assist in your AI conversation agent's Control Home Assistant option.", "error": False}
        finally:
            self.operation_lock.release()

    def discover(self):
        token = self._secret()
        self.app.supervisor.assist_discovery(PORT, token)
        self.last_discovery = self.app.monotonic()
        self.connection = "Connection offered. Finish setup in Home Assistant's Devices & services."

    def run(self):
        """Discovery retries never occupy the RTC/UPS control worker."""
        while not self.app.stop_event.is_set():
            if self.app.store.data["assist"]["enabled"] and self.app.monotonic() - self.last_discovery >= 120:
                if self.operation_lock.acquire(blocking=False):
                    try:
                        self.discover()
                    except (UserError, OSError, ValueError, KeyError, TypeError):
                        self.last_discovery = self.app.monotonic()
                        self.connection = "Home Assistant could not connect yet. Finish companion setup in Devices & services."
                    finally:
                        self.operation_lock.release()
            self.app.stop_event.wait(5)

    def save_settings(self, payload):
        settings = validate_settings(payload)
        with self.app.lock:
            if settings["enabled"] and not self.installer.installed():
                raise UserError("Connect Assist before enabling it.", "Select Connect Assist and finish the discovered integration in Home Assistant.")
            old = self.app.store.data["assist"]
            self.app.store.data["assist"] = settings
            try:
                self.app.store.save()
            except Exception:
                self.app.store.data["assist"] = old
                raise
            if not settings["enabled"] or not settings["allow_requests"]:
                self.requests.clear()
        self.app.message = {"text": "Assist settings saved.", "action": "", "error": False}

    def _allowed(self, *, writes=False):
        if not self.app.store.data["assist"]["enabled"]:
            raise UserError("Assist access is off.", "Enable Assist in the Pi Wake & Sleep app.")
        if writes and not self.app.store.data["assist"]["allow_requests"]:
            raise UserError("Assist is set to status only.", "Enable change requests in the app before asking Assist to change a schedule or cancel a countdown.")

    def _expire(self):
        for key, item in list(self.requests.items()):
            if self.app.monotonic() >= item["deadline"] and not item.get("submitted"):
                self.requests.pop(key, None)

    def snapshot(self):
        with self.app.lock:
            self._expire()
            requests = [{k: deepcopy(v) for k, v in item.items() if k not in ("deadline", "signature")}
                        for item in self.requests.values()]
            return {"settings": deepcopy(self.app.store.data["assist"]), "connection": self.connection,
                    "restart_needed": self.restart_needed, "requests": requests}

    def status(self):
        with self.app.lock:
            settings = deepcopy(self.app.store.data["assist"])
            result = {"protocol": PROTOCOL, **settings}
            self.connection = "Connected to Home Assistant."
            self.restart_needed = False
            if not settings["enabled"]:
                return result
            state = self.app.snapshot()
            tz = ZoneInfo(state["schedule"]["timezone"])
            stamp = lambda value: datetime.fromtimestamp(value, tz).isoformat() if value else None
            source = state["ups"]["selected"] or {}
            result.update(current_time=stamp(self.app.clock()), timezone=str(tz), version=state["version"],
                          uptime_seconds=max(0, int(self.app.clock() - self.app.host.boot_epoch(self.app.clock()))),
                          pi_ready=bool(state["checks"].get("ok") and state["test_status"] == "passed"),
                          setup_message=state["checks"].get("message"), next_action=state["checks"].get("action"),
                          wake_test=state["test_status"], calendar=state["schedule"]["calendar_entity_id"],
                          scheduling_enabled=state["schedule"]["enabled"], scheduling_active=state["schedule_active"],
                          calendar_fresh=self.app._calendar_ready(), calendar_message=state["calendar"]["message"],
                          next_shutdown=stamp(state["next_sleep_epoch"]), next_wake=stamp(state["next_wake_epoch"]),
                          shutdown_requested=state["shutdown_requested"], countdown=state["pending"],
                          ups={"name": str(source.get("name", "Not selected"))[:200], "state": source.get("power_state", "unknown"),
                               "battery_percent": source.get("battery_percent"), "runtime_seconds": source.get("runtime_seconds"),
                               "readings_fresh": bool(source.get("ok")), "emergency_protection": state["recovery"]["emergency_active"]},
                          periods=[{"title": item["title"][:200], "shutdown": stamp(item["start_epoch"]),
                                    "wake": stamp(item["end_epoch"]) if item.get("power_action") != "stop" else None,
                                    "kind": item.get("power_action", "calendar")}
                                   for item in state["calendar"]["periods"][:10]] if self.app._calendar_ready() else [])
            if result["countdown"]:
                result["countdown"] = {key: result["countdown"].get(key) for key in ("kind", "wake_epoch", "remaining_seconds", "emergency")}
            return result

    def request(self, payload):
        if not isinstance(payload, dict) or payload.get("kind") not in KINDS:
            raise UserError("That Assist action is not supported.", "Ask for status, an off period, scheduling on/off, a wake test, or a reboot.")
        kind = payload["kind"]
        allowed = {"kind", "start", "end", "title"} if kind == "create_period" else {"kind", "enabled"} if kind == "set_scheduling" else {"kind"}
        if set(payload) != allowed:
            raise UserError("The Assist request is incomplete or contains unsupported fields.", "Clarify the request and try again.")
        with self.app.lock:
            self._allowed(writes=True)
            self._expire()
            if self.app.store.read_only or self.app.shutdown_requested_at is not None:
                raise UserError("This Pi cannot accept a change request now.", "Keep the power connected and review the app's status.")
            settings = self.app.store.data["schedule"]
            request = {"kind": kind, "calendar": settings["calendar_entity_id"]}
            if kind == "create_period":
                start, end = parse_time(payload["start"]), parse_time(payload["end"])
                title = payload["title"]
                if not isinstance(title, str) or not 1 <= len(title.strip()) <= 100 or any(ord(c) < 32 for c in title):
                    raise UserError("Use a short, plain-text title for the off period.", "Try the schedule request again with a title of at most 100 characters.")
                if not request["calendar"] or not self.app._calendar_ready():
                    raise UserError("Select and check a Calendar before requesting dates.", "Open Calendar in the app, save the Calendar selection, and select Check again.")
                self._validate_period(start, end)
                tz = ZoneInfo(settings["timezone"])
                request.update(start_epoch=start, end_epoch=end, title=title.strip(),
                               start=datetime.fromtimestamp(start, tz).isoformat(), end=datetime.fromtimestamp(end, tz).isoformat())
                request["summary"] = "Save in Calendar: " + request["title"] + ". Shutdown " + request["start"] + "; wake " + request["end"] + "."
            elif kind == "set_scheduling":
                if type(payload["enabled"]) is not bool:
                    raise UserError("Choose scheduling on or off.", "Clarify the request and try again.")
                request.update(enabled=payload["enabled"], summary="Turn Calendar scheduling " + ("on" if payload["enabled"] else "off") + ".")
            else:
                request["summary"] = "Run the ten-minute wake test. Home Assistant will be offline during the test." if kind == "wake_test" else "Reboot the Pi. Home Assistant will be offline while it restarts."
            signature = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
            existing = next((item for item in self.requests.values() if item["signature"] == signature), None)
            if existing:
                return self._request_result(existing)
            if len(self.requests) >= 5:
                raise UserError("Five Assist requests are waiting for review.", "Approve or dismiss requests in the app before adding more.")
            request.update(id=secrets.token_hex(16), signature=signature, deadline=self.app.monotonic() + TTL, submitted=False)
            self.requests[request["id"]] = request
            return self._request_result(request)

    @staticmethod
    def _request_result(request):
        return {"status": "awaiting_app_approval", "request_id": request["id"], "summary": request["summary"],
                "next_action": "Open Pi Wake & Sleep → Assist and approve this request. Nothing has been changed yet."}

    def _validate_period(self, start, end):
        if start < self.app.clock() + 120 or start > self.app.clock() + 30 * 86400 or not 600 <= end - start <= 7 * 86400:
            raise UserError("The off period needs new dates.", "Choose a shutdown at least two minutes ahead and within 30 days, and a wake ten minutes to seven days later.")

    def keep_awake(self, payload):
        if payload != {}:
            raise UserError("The cancellation request was not recognized.", "Ask to cancel the current shutdown countdown.")
        with self.app.lock:
            self._allowed(writes=True)
            if not self.app.pending and not self.app.job:
                return {"status": "no_countdown", "message": "The Pi is awake. There is no current countdown to cancel. Future Calendar events and UPS protection are unchanged."}
            self.app.cancel()
            return {"status": "cancelled", "message": "The current shutdown was cancelled. Future Calendar events and emergency UPS protection are unchanged."}

    def review(self, payload):
        if (not isinstance(payload, dict) or set(payload) != {"id", "approve", "confirmed"}
                or type(payload["approve"]) is not bool or payload["confirmed"] is not True):
            raise UserError("The Assist review was not confirmed.", "Review the request on this screen and try again.")
        if not self.operation_lock.acquire(blocking=False):
            raise UserError("An Assist operation is in progress.", "Wait for it to finish and try again.")
        try:
            with self.app.lock:
                self._allowed(writes=True)
                self._expire()
                item = self.requests.get(payload["id"])
                if not item:
                    raise UserError("This request expired or was already reviewed.", "Ask Assist for a new request; unapproved requests expire after ten minutes or an app restart.")
                if not payload["approve"]:
                    self.requests.pop(item["id"])
                    return
                if item["calendar"] != self.app.store.data["schedule"]["calendar_entity_id"]:
                    raise UserError("The selected Calendar changed after this request.", "Dismiss it and ask Assist for a new request for the saved Calendar.")
                if item["kind"] != "set_scheduling" or item["enabled"]:
                    if self.app.job or self.app.pending or self.app.shutdown_requested_at is not None or self.app.store.data["outage"]:
                        raise UserError("Wait before approving this request.", "Finish the current operation and wait for stable utility power, then review it again.")
            if item["kind"] == "create_period":
                self._save_period(item)
            elif item["kind"] == "set_scheduling":
                if item["enabled"]:
                    self.app._require_ready(require_test=True)
                with self.app.lock:
                    self._allowed(writes=True)
                    if item["calendar"] != self.app.store.data["schedule"]["calendar_entity_id"]:
                        raise UserError("The selected Calendar changed while this request was being checked.", "Dismiss it and ask Assist for a new request.")
                    settings = deepcopy(self.app.store.data["schedule"])
                settings["enabled"] = item["enabled"]
                self.app.save_settings(settings)
            else:
                self.app.begin_job("test" if item["kind"] == "wake_test" else "reboot",
                                   {"confirmed": True, "assist_reviewed": True})
            with self.app.lock:
                self.requests.pop(item["id"], None)
                self.app.message = {"text": "Assist request approved." + (" Saved in Home Assistant Calendar." if item["kind"] == "create_period" else ""), "action": "", "error": False}
        finally:
            self.operation_lock.release()

    def _save_period(self, item):
        """Check Calendar before/after saving; an uncertain response never creates a duplicate."""
        entity = item["calendar"]
        marker = "Pi Wake & Sleep Assist v1:" + item["id"]
        events = self.app.supervisor.calendar_events(entity, self.app.clock())
        matches = [event for event in events if event.get("description") == marker]
        if not matches:
            if item["submitted"]:
                raise UserError("Home Assistant has not confirmed the Calendar save.", "Check Calendar before trying again. This request will not submit a second copy.")
            self._validate_period(item["start_epoch"], item["end_epoch"])
            periods = parse_periods(events, entity, self.app.clock())
            if any(item["start_epoch"] <= p["end_epoch"] and p["start_epoch"] <= item["end_epoch"] for p in periods):
                raise UserError("This off period overlaps or touches another event.", "Review Calendar and ask Assist for different dates.")
            self.app.supervisor.calendar_writable(entity)
            with self.app.lock:
                self._allowed(writes=True)
                if entity != self.app.store.data["schedule"]["calendar_entity_id"] or self.app.store.data["outage"]:
                    raise UserError("The Calendar or power state changed while this request was being checked.", "Keep the Pi on and review the request again after checking Calendar and UPS status.")
            item["submitted"] = True
            try:
                self.app.supervisor.create_assist_event(entity, item["start_epoch"], item["end_epoch"], item["title"], marker)
            except UserError:
                pass  # Resolve from Calendar, never retry a possibly committed write.
            events = self.app.supervisor.calendar_events(entity, self.app.clock())
            matches = [event for event in events if event.get("description") == marker]
        if len(matches) != 1:
            raise UserError("The Calendar save has not been confirmed.", "Check Calendar and review this request again. A second copy will not be submitted.")
        candidate = parse_periods(matches, entity, self.app.clock())
        if len(candidate) != 1 or (candidate[0]["start_epoch"], candidate[0]["end_epoch"]) != (item["start_epoch"], item["end_epoch"]):
            raise UserError("The saved dates do not match the approved request.", "Keep the Pi on and correct the event in Home Assistant Calendar.")
        self.app.refresh_calendar()
