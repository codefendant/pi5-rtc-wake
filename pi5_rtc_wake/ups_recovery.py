"""Opt-in RTC recovery. All planned wake dates are read back from HA Calendar."""

from copy import deepcopy
import hashlib
import math
import re
import secrets

from power_sources import ENTITY_ID, SOURCE_ID, fresh
from state import UserError

DEFAULTS = {
    "enabled": False, "runtime_entity_id": None, "early_shutdown": False,
    "outage_delay_minutes": 5, "shutdown_runtime_minutes": 30,
    "first_retry_minutes": 15, "max_retry_minutes": 120, "max_retries": 3,
    "retry_reserve_minutes": 5, "min_charge_percent": 20,
    "boot_grace_minutes": 3, "stable_power_minutes": 2,
    "supply_confirmed": False, "final_shutdown_confirmed": False,
    "retry_enabled": True, "emergency_enabled": True, "emergency_runtime_minutes": 5,
    "owner_confirmed": False,
    "qualification": None,
}
BOUNDS = {
    "outage_delay_minutes": (1, 120), "shutdown_runtime_minutes": (5, 240),
    "first_retry_minutes": (10, 120), "max_retry_minutes": (10, 360),
    "max_retries": (1, 8), "retry_reserve_minutes": (3, 60),
    "min_charge_percent": (5, 80), "boot_grace_minutes": (1, 15),
    "stable_power_minutes": (1, 15),
    "emergency_runtime_minutes": (2, 60),
}
PHASES = {"observing", "planning", "countdown", "submitted", "blocked", "paused", "stopped"}


def validate_policy(value):
    if not isinstance(value, dict):
        raise UserError("UPS recovery settings could not be read.", "Review the recovery settings and save again.")
    result = deepcopy(DEFAULTS)
    for key in ("enabled", "early_shutdown", "supply_confirmed", "final_shutdown_confirmed", "retry_enabled", "emergency_enabled", "owner_confirmed"):
        if type(value.get(key, result[key])) is not bool:
            raise UserError("Choose the UPS recovery options again.", "Use the checkboxes and save.")
        result[key] = value.get(key, result[key])
    for key, (low, high) in BOUNDS.items():
        number = value.get(key, result[key])
        if type(number) is not int or not low <= number <= high:
            raise UserError("A recovery timing or threshold is out of range.", "Use the limits shown beside the recovery settings and save.")
        result[key] = number
    identity = value.get("runtime_entity_id")
    if identity not in (None, "") and (not isinstance(identity, str) or not ENTITY_ID.fullmatch(identity)):
        raise UserError("Choose the remaining-runtime reading.", "Select Battery runtime from this UPS, then save.")
    result["runtime_entity_id"] = identity or None
    qualification = value.get("qualification")
    if qualification is not None:
        if (not isinstance(qualification, dict)
                or not SOURCE_ID.fullmatch(str(qualification.get("source_id", "")))
                or not (qualification.get("calendar_entity_id") is None and not result["retry_enabled"] or re.fullmatch(r"calendar\.[a-z0-9_]{1,150}", str(qualification.get("calendar_entity_id", ""))))
                or not re.fullmatch(r"[a-f0-9]{64}", str(qualification.get("fingerprint", "")))
                or not re.fullmatch(r"[a-f0-9]{64}", str(qualification.get("source_fingerprint", "")))):
            raise UserError("The verified recovery setup could not be read.", "Confirm the UPS supply and wake test again, then save.")
        result["qualification"] = {key: qualification[key] for key in ("source_id", "calendar_entity_id", "fingerprint", "source_fingerprint")}
    if result["max_retry_minutes"] < result["first_retry_minutes"]:
        raise UserError("The maximum retry interval is too short.", "Set it at least as long as the first retry.")
    if result["retry_enabled"] and result["shutdown_runtime_minutes"] < result["first_retry_minutes"] + result["retry_reserve_minutes"] + result["boot_grace_minutes"] + 1:
        raise UserError("The shutdown threshold leaves too little time for the first retry.", "Increase the shutdown runtime threshold, or shorten the first retry or allowances.")
    if result["retry_enabled"] and result["emergency_runtime_minutes"] > result["shutdown_runtime_minutes"]:
        raise UserError("The emergency reserve exceeds the normal shutdown threshold.", "Set the emergency reserve at or below the normal runtime threshold.")
    if result["enabled"] and not (result["retry_enabled"] or result["emergency_enabled"]):
        raise UserError("Choose at least one kind of UPS protection.", "Enable timed retries or emergency low-battery protection, or turn automatic protection off.")
    if result["enabled"] and (result["retry_enabled"] and not result["supply_confirmed"] or not result["final_shutdown_confirmed"]):
        raise UserError("Confirm the shutdown ownership and recovery limits before enabling it.", "Review which app controls host shutdown, the supply path for retries, and the final stop without a timed wake.")
    return result


def validate_session(value):
    if value == {}:
        return {}
    if (not isinstance(value, dict) or not re.fullmatch(r"[a-f0-9]{32}", str(value.get("id", "")))
            or not SOURCE_ID.fullmatch(str(value.get("source_id", "")))
            or value.get("phase") not in PHASES
            or type(value.get("attempts")) is not int or not 0 <= value["attempts"] <= 9
            or not isinstance(value.get("boot_id"), str) or len(value["boot_id"]) > 100
            or type(value.get("submitted", False)) is not bool
            or not isinstance(value.get("message", ""), str) or len(value.get("message", "")) > 500
            or value.get("token") is not None and not re.fullmatch(r"[a-f0-9]{32}", str(value["token"]))):
        raise UserError("The outage recovery record could not be read.", "Restore the app from a Home Assistant backup. Automatic recovery is paused.")
    for key, maximum in (("last_runtime_seconds", 31 * 86400), ("last_runtime_epoch", 0xFFFFFFFF)):
        if key in value and (type(value[key]) not in (int, float) or not math.isfinite(value[key]) or not 0 <= value[key] <= maximum):
            raise UserError("The last UPS reserve could not be read.", "Restore the app from a Home Assistant backup. Automatic protection is paused.")
    if ("last_runtime_seconds" in value) != ("last_runtime_epoch" in value):
        raise UserError("The last UPS reserve is incomplete.", "Restore the app from a Home Assistant backup. Automatic protection is paused.")
    return {key: deepcopy(value[key]) for key in ("id", "source_id", "phase", "attempts", "boot_id", "submitted", "message", "token", "last_runtime_seconds", "last_runtime_epoch") if key in value}


def source_fingerprint(source):
    text = "\0".join(str(source.get(key, "")) for key in ("id", "provider", "manufacturer", "model"))
    return hashlib.sha256(text.encode()).hexdigest()


def with_runtime(source, policy, now):
    if not source:
        return None
    result = deepcopy(source)
    if source["id"].startswith("nut:"):
        candidate = next((row for row in source.get("runtime_candidates", []) if row["entity_id"] == policy["runtime_entity_id"]), None)
        result["runtime_seconds"] = candidate["seconds"] if candidate and fresh(candidate["reported_at"], now) else None
        result["runtime_observed_epoch"] = candidate["observed_epoch"] if candidate and result["runtime_seconds"] is not None else None
    else:
        result["runtime_observed_epoch"] = source.get("observed_epoch") if source.get("runtime_seconds") is not None else None
    result["runtime_reported_seconds"] = result["runtime_seconds"]
    if result["runtime_seconds"] is not None and result["runtime_observed_epoch"] is not None:
        # A still-usable but aging observation must not freeze the reserve.
        result["runtime_seconds"] = max(0, result["runtime_seconds"] - max(0, now - result["runtime_observed_epoch"]))
    return result


def retry_minutes(policy, attempts):
    return min(policy["max_retry_minutes"], policy["first_retry_minutes"] * 2 ** min(attempts, 8))


def retry_requirements(policy):
    return [{"attempt": attempt + 1, "interval_minutes": retry_minutes(policy, attempt),
             "minimum_runtime_minutes": retry_minutes(policy, attempt) + policy["boot_grace_minutes"] + policy["retry_reserve_minutes"] + 1}
            for attempt in range(policy["max_retries"])]


def retry_is_safe(source, policy, attempts, seconds=None):
    minutes = retry_minutes(policy, attempts)
    wait = minutes * 60 if seconds is None else seconds
    runtime = source.get("runtime_seconds")
    charge = source.get("battery_percent")
    return (attempts < policy["max_retries"] and not source.get("low_battery") and not source.get("forced_shutdown")
            and runtime is not None and runtime >= wait + (policy["retry_reserve_minutes"] + policy["boot_grace_minutes"]) * 60 + 60
            and (charge is None or charge > policy["min_charge_percent"]))


class Recovery:
    """Worker-side policy with durable claims; never send a UPS output command."""

    def __init__(self, app):
        self.app = app
        self.battery_since = None
        self.mains_since = None
        self.unknown_since = None
        self.reconciled = False
        self.message = "UPS recovery is off."
        self.notice_signature = object()
        self.last_notice_attempt = -math.inf
        self.last_notice_signature = object()
        self.notices_ok = True

    def policy(self):
        return self.app.store.data["recovery"]

    def source(self):
        return with_runtime(self.app._selected_power(), self.policy(), self.app.clock())

    def eligible(self):
        app, policy = self.app, self.policy()
        qualification = policy["qualification"]
        known = next((source for source in app.power_info["sources"] if source["id"] == app.store.data["ups"]["source_id"]), None)
        return bool(self.protection_eligible() and policy["retry_enabled"] and qualification
                    and qualification["source_id"] == app.store.data["ups"]["source_id"]
                    and qualification["calendar_entity_id"] == app.store.data["schedule"]["calendar_entity_id"]
                    and qualification["fingerprint"] == app.checks.get("fingerprint")
                    and (known is None or qualification["source_fingerprint"] == source_fingerprint(known))
                    and app.checks.get("ok") and app._test_passed()
                    and app.shutdown_controller_info["state"] in ("ready", "not_found")
                    and app.monotonic() - app.last_nut_settings_refresh < 150)

    def protection_eligible(self):
        app, policy = self.app, self.policy()
        qualification = policy["qualification"]
        known = next((source for source in app.power_info["sources"] if source["id"] == app.store.data["ups"]["source_id"]), None)
        return bool(not app.store.data["keep_awake"] and policy["enabled"] and policy["owner_confirmed"] and qualification
                    and qualification["source_id"] == app.store.data["ups"]["source_id"]
                    and (known is None or qualification["source_fingerprint"] == source_fingerprint(known))
                    and app.host_shutdown_supported and not app.store.read_only)

    def _save(self, **updates):
        app = self.app
        old = deepcopy(app.store.data)
        app.store.data["outage"].update(updates)
        try:
            app.store.save()
        except Exception:
            app.store.data = old
            raise

    def _clear_session(self):
        app = self.app
        old = deepcopy(app.store.data)
        app.store.data["outage"] = {}
        try:
            app.store.save()
        except Exception:
            app.store.data = old
            raise
        self.battery_since = self.unknown_since = None

    def save_settings(self, value):
        app = self.app
        supplied = dict(value)
        supplied["qualification"] = None  # The browser/provider cannot issue its own qualification.
        policy = validate_policy(supplied)
        app.refresh_nut_settings(sensors=False)
        app.refresh_power()
        with app.lock:
            if app.job or app.pending or app.shutdown_requested_at is not None:
                raise UserError("A Pi operation is in progress.", "Cancel the countdown or wait for the operation to finish before saving recovery.")
            old_policy = self.policy()
            if old_policy["enabled"] and old_policy["emergency_enabled"] and (not policy["enabled"] or not policy["emergency_enabled"]) and supplied.get("confirmed_disable_emergency") is not True:
                raise UserError("Confirm before disabling emergency protection.", "Use the confirmation on the UPS settings screen. Cancelling a retry leaves emergency protection on.")
            source = with_runtime(app._selected_power(), policy, app.clock())
            calendar = app.store.data["schedule"]["calendar_entity_id"]
            if policy["enabled"]:
                if not policy["owner_confirmed"]:
                    raise UserError("Confirm who controls this Pi's shutdown.", "Review NUT's settings and any other controllers, restart NUT after changes, then confirm ownership.")
                if supplied.get("expected_source_id") != app.store.data["ups"]["source_id"] or supplied.get("expected_calendar_entity_id") != calendar:
                    raise UserError("The selected UPS or Calendar changed before saving.", "Refresh the screen, review the saved source and calendar, and save recovery again.")
                if not app.host_shutdown_supported:
                    raise UserError("Home Assistant host shutdown has not been checked.", "Check this Pi in Setup before enabling protection.")
                if policy["retry_enabled"] and (not app.checks.get("ok") or not app._test_passed() or app.monotonic() - app.last_refresh >= 60):
                    raise UserError("A confirmed Pi wake test is required.", "Select Check again, confirm a successful wake test on this supply path, then enable recovery.")
                if not source or not source["ok"] or source["power_state"] not in ("mains", "battery"):
                    raise UserError("Fresh UPS status is required.", "Choose the UPS in the power monitor, check its connection, and save again.")
                if source.get("forced_shutdown") or source["power_state"] != "mains" and (not self.protection_eligible() or app.store.notice):
                    raise UserError("Enable recovery while utility power is available.", "Restore utility power, verify the supply path, then enable recovery. An active verified policy can be adjusted during an outage.")
                if source["runtime_seconds"] is None:
                    raise UserError("A fresh remaining-runtime reading is required.", "Enable Battery runtime on the NUT device page, scan again, and select that reading. A shutdown/restart delay is not remaining runtime.")
                if policy["retry_enabled"] and not calendar:
                    raise UserError("Choose the calendar before enabling recovery.", "Save a dedicated Local Calendar above. Retries will be written into that calendar.")
                if policy["retry_enabled"]:
                    if app.shutdown_controller_info["state"] not in ("ready", "not_found"):
                        raise UserError("RTC retries need one host-shutdown controller.", "Review NUT's shutdown_host setting, restart NUT after changes, and confirm ownership. Other controllers must not shut down this Pi independently.")
                    app.supervisor.calendar_writable(calendar)
                policy["qualification"] = {"source_id": source["id"], "calendar_entity_id": calendar,
                    "fingerprint": app.checks.get("fingerprint") or hashlib.sha256(b"emergency-only").hexdigest(), "source_fingerprint": source_fingerprint(source)}
            previous = deepcopy(app.store.data)
            app.store.data["recovery"] = policy
            if app.store.data["outage"] and not policy["enabled"]:
                app.store.data["outage"].update(phase="paused", message="Automatic recovery was turned off for this outage.")
            try:
                app.store.save()
            except Exception:
                app.store.data = previous
                raise
            app.message = {"text": "UPS protection saved. " + ("RTC retries are enabled when reserve permits." if policy["enabled"] and policy["retry_enabled"] else "Emergency low-battery protection is enabled." if policy["enabled"] else "Automatic UPS shutdown is off."), "action": "", "error": False}
            self.mains_since = self.unknown_since = None
        self.notice()

    def reconcile(self):
        if self.reconciled or self.app.store.read_only:
            return
        app, session = self.app, self.app.store.data["outage"]
        if session:
            if session.get("submitted") and session["boot_id"] != app.host.boot_id():
                self._save(phase="paused" if session["phase"] == "stopped" else "observing", submitted=False, boot_id=app.host.boot_id(),
                           message="Pi restarted after a final stop. Automatic attempts remain paused until utility power is stable." if session["phase"] == "stopped" else "Pi restarted. Waiting for fresh UPS readings.")
            elif session["phase"] in ("planning", "countdown", "submitted"):
                self._save(phase="paused", message="An interrupted or uncertain attempt is paused. It will not be repeated on this boot.")
            if session.get("submitted") and session["boot_id"] == app.host.boot_id():
                app.shutdown_requested_at = app.monotonic()
        self.reconciled = True

    def blocks_calendar(self):
        if not self.policy()["enabled"]:
            return False
        source = self.source()
        return bool(self.app.store.data["outage"] or self.policy()["retry_enabled"] and not self.eligible()
                    or not source or not source["ok"] or source["power_state"] != "mains")

    def snapshot(self):
        app, policy = self.app, self.policy()
        source, session = self.source(), app.store.data["outage"]
        period = next((row for row in app.calendar_info["periods"] if row.get("power_token") == session.get("token")), None) if session else None
        eligible = self.eligible()
        protected = self.protection_eligible()
        if app.store.data["keep_awake"]:
            message = "Keep awake is on. All app shutdowns, including emergency UPS shutdowns, are suspended."
        elif policy["enabled"] and not protected:
            message = "Automatic protection needs review. Confirm the saved UPS and shutdown ownership."
        else:
            message = session.get("message") or self.message
            if policy["retry_enabled"] and not eligible and protected:
                message += " RTC retries are paused; emergency protection " + ("remains active." if policy["emergency_enabled"] else "is disabled.")
        return {"settings": deepcopy(policy), "eligible": eligible, "phase": session.get("phase", "idle"),
                "attempts": session.get("attempts", 0), "message": message,
                "runtime_seconds": source.get("runtime_seconds") if source else None,
                "next_retry_minutes": retry_minutes(policy, session.get("attempts", 0)),
                "next_wake_epoch": period["end_epoch"] if period and period.get("power_action") == "retry" and session["phase"] in ("countdown", "submitted") else None,
                "calendar_paused": self.blocks_calendar(), "notifications_ok": self.notices_ok,
                "protection_eligible": protected, "emergency_active": protected and policy["emergency_enabled"],
                "retry_requirements": retry_requirements(policy)}

    def notice(self):
        snapshot = self.snapshot()
        if self.app.store.data["keep_awake"]:
            value = {"message": "Keep awake is on. All Pi Wake & Sleep shutdowns are suspended, including emergency low-battery protection. Select Resume shutdowns in the Pi dashboard to restore your saved policy."}
        elif not self.policy()["enabled"]:
            value = None
        elif (self.app.store.data["outage"] or not snapshot["protection_eligible"]
              or self.policy()["retry_enabled"] and not snapshot["eligible"]):
            value = {"message": "UPS recovery: " + snapshot["message"] + " Open Pi Wake & Sleep for the recovery state. RTC retries require continuous input power; a final shutdown may need a power cycle or the Pi's power button."}
        else:
            value = None
        signature = value["message"] if value else None
        if signature == self.notice_signature or signature == self.last_notice_signature and self.app.monotonic() - self.last_notice_attempt < 60:
            return
        self.last_notice_attempt = self.app.monotonic()
        self.last_notice_signature = signature
        try:
            self.app.supervisor.recovery_notice(value)
            self.notice_signature, self.notices_ok = signature, True
        except UserError:
            self.notices_ok = False

    def poll(self):
        app, policy = self.app, self.policy()
        if app.store.data["keep_awake"] or not policy["enabled"] or app.store.read_only:
            self.notice()
            return False
        self.reconcile()
        source, session = self.source(), app.store.data["outage"]
        if not self.protection_eligible():
            self.message = "Automatic protection needs review. Confirm the saved UPS and shutdown ownership."
            self.notice()
            return True
        now = app.monotonic()
        postboot = bool(source and source.get("observed_epoch") is not None and source["observed_epoch"] >= app.host.boot_epoch(app.clock()))
        forced = bool(source and source.get("forced_shutdown") and postboot)
        valid = bool(source and postboot and (source["ok"] and source["power_state"] in ("mains", "battery") or forced))
        if valid and source["power_state"] == "mains" and not source.get("forced_shutdown"):
            self.battery_since = self.unknown_since = None
            if not session:
                self.message = "Ready. Home Assistant stays on until the shutdown threshold is reached." if policy["retry_enabled"] else "Emergency protection is ready. Timed RTC retries are off."
                return False
            if self.mains_since is None:
                self.mains_since = now
                self._save(message="Utility power returned. Waiting for stable power before resuming schedules.")
            if now - self.mains_since >= policy["stable_power_minutes"] * 60:
                self._clear_session()
                self.message = "Utility power is stable. Normal Calendar scheduling has resumed."
                self.notice()
                return False
            self.notice()
            return True
        self.mains_since = None
        if not session and not valid:
            self.message = "Waiting for fresh UPS readings. Calendar shutdowns are paused."
            self.notice()
            return True
        if not session:
            app.store.data["outage"] = {"id": secrets.token_hex(16), "source_id": source["id"], "phase": "observing",
                "attempts": 0, "boot_id": app.host.boot_id(), "submitted": False, "message": "UPS is on battery. Watching the shutdown threshold.", "token": None}
            try:
                app.store.save()
            except Exception:
                app.store.data["outage"] = {}
                raise
            session = app.store.data["outage"]
        if session["source_id"] != app.store.data["ups"]["source_id"] or session.get("submitted") or session["phase"] in ("stopped", "planning", "countdown", "submitted"):
            self.notice()
            return True
        runtime_fresh = bool(valid and source["runtime_seconds"] is not None and source.get("runtime_observed_epoch") is not None and source["runtime_observed_epoch"] >= app.host.boot_epoch(app.clock()))
        if runtime_fresh and (session.get("last_runtime_epoch") != source["runtime_observed_epoch"] or session.get("last_runtime_seconds") != source["runtime_reported_seconds"]):
            self._save(last_runtime_seconds=source["runtime_reported_seconds"], last_runtime_epoch=source["runtime_observed_epoch"])
        reported_low = bool(valid and source and (source.get("low_battery") or source.get("battery_percent") is not None and source["battery_percent"] <= policy["min_charge_percent"]))
        if policy["emergency_enabled"] and (forced or reported_low):
            reason = "NUT or the power hook requests an emergency stop. No timed wake is promised." if forced else "The UPS reports low battery. Graceful shutdown; no timed wake is promised."
            retry, emergency = False, True
        elif not valid or not runtime_fresh:
            if self.unknown_since is None:
                self.unknown_since = now
                self._save(message="Waiting for fresh UPS status and remaining runtime. No power-restored assumption is being made.")
            old_reserve = session.get("last_runtime_seconds")
            reserve_expired = old_reserve is not None and old_reserve - max(0, app.clock() - session["last_runtime_epoch"]) <= 60
            if now - self.unknown_since < policy["boot_grace_minutes"] * 60 and not reserve_expired:
                self.notice()
                return True
            if not policy["emergency_enabled"]:
                text = "UPS readings are missing in a known outage. Emergency protection is disabled; the Pi remains on."
                if session.get("message") != text:
                    self._save(message=text)
                self.notice()
                return True
            reason, retry = "UPS readings did not recover in time. A final graceful shutdown is required; no timed wake is promised.", False
            emergency = True
        else:
            self.unknown_since = None
            if self.battery_since is None:
                self.battery_since = now
            low = source.get("low_battery") or source.get("forced_shutdown") or source["battery_percent"] is not None and source["battery_percent"] <= policy["min_charge_percent"]
            emergency = bool(policy["emergency_enabled"] and (low or source["runtime_seconds"] <= policy["emergency_runtime_minutes"] * 60))
            can_retry = self.eligible() and session["phase"] != "paused"
            if not emergency and not can_retry:
                self.message = "RTC retries are paused. " + ("Emergency protection remains active at the low-battery reserve." if policy["emergency_enabled"] else "Emergency protection is disabled.")
                self.notice()
                return True
            trigger = (low or source["runtime_seconds"] <= policy["shutdown_runtime_minutes"] * 60
                       or session["attempts"] > 0
                       or policy["early_shutdown"] and now - self.battery_since >= policy["outage_delay_minutes"] * 60)
            if session["phase"] == "blocked" and not emergency:
                trigger = low or source["runtime_seconds"] <= (policy["retry_reserve_minutes"] + policy["boot_grace_minutes"] + 1) * 60
            if not trigger and not emergency:
                self.notice()
                return True
            retry = not emergency and can_retry and session["phase"] != "blocked" and retry_is_safe(source, policy, session["attempts"])
            reason = ("Saving a Calendar off period for RTC retry." if retry else
                      "Emergency low-battery protection: graceful shutdown; no timed wake is promised." if emergency else
                      "Retry reserve or limit was reached. Final graceful shutdown; no timed wake is promised.")
        if not app.job and not app.pending and app.shutdown_requested_at is None:
            app.begin_job("ups", {"confirmed": True, "retry": retry, "reason": reason, "emergency": emergency})
        return True

    def _urgent_stop(self, source, session):
        if source and source.get("forced_shutdown"):
            return True
        if source and source["ok"] and source.get("runtime_seconds") is not None:
            return source["runtime_seconds"] < 120
        reserve = session.get("last_runtime_seconds")
        return reserve is not None and reserve - max(0, self.app.clock() - session["last_runtime_epoch"]) < 120

    def start(self, serial, retry, reason, emergency=False):
        app = self.app
        if retry:
            app._require_ready(require_test=True)
        with app.lock:
            if serial != app.cancel_serial or not self.protection_eligible() or retry and not self.eligible():
                return
            source, policy, session = self.source(), self.policy(), app.store.data["outage"]
            if not session or session["phase"] not in ("observing", "blocked", "paused") or session.get("submitted"):
                return
            if source and source["ok"] and source["power_state"] == "mains" and not source.get("forced_shutdown"):
                return
            if retry and (not source or not source["ok"] or not retry_is_safe(source, policy, session["attempts"])):
                retry = False
                reason = "The UPS reserve changed. Final graceful shutdown; no timed wake is promised."
            urgent = not retry and self._urgent_stop(source, session)
            token = secrets.token_hex(16)
            self._save(phase="planning", token=token, attempts=session["attempts"] + (1 if retry else 0),
                       boot_id=app.host.boot_id(), submitted=False, message=reason)
            calendar = app.store.data["schedule"]["calendar_entity_id"]
            start = int(app.clock()) + 30
            end = start + (retry_minutes(policy, session["attempts"] - 1) * 60 if retry else 60)
            period = None
            try:
                if urgent:
                    raise UserError("Critical reserve: stop now.", "Calendar recording must not delay emergency shutdown.")
                app.supervisor.create_power_event(calendar, start, end, "retry" if retry else "stop", token)
            except UserError:
                # A lost response can mean the event was created. Read it back,
                # but never repeat a possibly accepted creation request.
                pass
            try:
                if urgent:
                    raise UserError("Critical reserve: stop now.", "No future wake is scheduled.")
                app.refresh_calendar()
                matches = [row for row in app.calendar_info["periods"] if row.get("power_token") == token]
                if not app._calendar_ready() or len(matches) != 1 or matches[0]["power_action"] != ("retry" if retry else "stop") or matches[0]["start_epoch"] != start or matches[0]["end_epoch"] != end:
                    raise UserError("The UPS event could not be verified in Calendar.", "Check Calendar. This creation request will not be repeated automatically.")
                period = matches[0]
            except UserError:
                if retry:
                    self._save(phase="blocked", message="The retry could not be verified in Calendar. The Pi stays on until reserve requires a final shutdown.")
                    return
                # Emergency shutdown is a current action, not an unrecorded
                # future wake schedule. Calendar failure must not prevent it.
                reason += " Critical reserve: stopping immediately without delaying for Calendar." if urgent else " Calendar was unavailable; this stop could not be recorded."
            if serial != app.cancel_serial:
                self._save(phase="paused", message="Shutdown cancelled. Automatic attempts are paused for this outage.")
                return
            request_id = "ups-" + token
            wake = None
            if retry:
                result = app.controller.arm({"request_id": request_id, "mode": "at", "wake_epoch": period["end_epoch"],
                                             "timezone": app.store.data["schedule"]["timezone"]})
                wake = result["wake_epoch"]
            # A current final stop does not depend on an RTC read, clock,
            # firmware check, or Calendar. Preserve any unrelated alarm.
            app.pending = {"kind": "ups", "request_id": request_id, "wake_epoch": wake,
                "deadline": app.monotonic() + (0 if urgent else 30), "fingerprint": app.checks.get("fingerprint"), "serial": serial,
                "power_token": token, "calendar_key": period["key"] if retry else None,
                "calendar_entity_id": calendar, "retry": retry, "urgent": urgent, "emergency": emergency}
            self._save(phase="countdown", message=reason)
            app.message = {"text": "Critical UPS reserve: requesting immediate shutdown." if urgent else "Emergency graceful shutdown in 30 seconds." if emergency else "UPS shutdown in 30 seconds.", "action": "No timed wake is promised." if emergency or urgent else "Cancel this retry pauses timed retries; emergency protection remains active if enabled.", "error": False}
            if not urgent:
                self.notice()

    def finish(self, pending):
        app = self.app
        if pending["retry"]:
            app._require_ready(require_test=True)
        with app.lock:
            if app.pending != pending or pending["serial"] != app.cancel_serial:
                return
            if not self.protection_eligible() or pending["retry"] and (not self.eligible() or pending["fingerprint"] != app.checks.get("fingerprint")):
                raise UserError("Recovery setup changed during the countdown.", "The Pi stays on. Review the UPS, Calendar, and wake test.")
            source, policy, session = self.source(), self.policy(), app.store.data["outage"]
            if source and source["ok"] and source["power_state"] == "mains" and not source.get("forced_shutdown"):
                app.cancel(mains_returned=True)
                self._save(phase="observing", message="Utility power returned during the countdown. Shutdown was cancelled.")
                return
            if pending["retry"]:
                period = app._calendar_period(pending["calendar_key"])
                if period.get("power_token") != pending["power_token"] or period.get("power_action") != "retry":
                    raise UserError("The Calendar retry changed.", "The Pi stays on. Review the Calendar event.")
                if not source or not source["ok"] or not retry_is_safe(source, policy, session["attempts"] - 1, period["end_epoch"] - app.clock()):
                    raise UserError("Fresh UPS reserve is insufficient for this retry.", "The retry is cancelled. Review power readings; a final shutdown will follow only if needed.")
                app.controller.verify({"request_id": pending["request_id"], "wake_epoch": pending["wake_epoch"]})
            self._save(phase="submitted" if pending["retry"] else "stopped", submitted=True, boot_id=app.host.boot_id(),
                       message="RTC retry shutdown requested." if pending["retry"] else "Final shutdown requested. Restart may require restored UPS output, a power cycle, or the Pi's power button.")
            app.pending["shutdown_requested"] = True
            app.shutdown_requested_at = app.monotonic()
            if not pending.get("urgent"):
                self.notice()
            app.wake_devices.other_power_action()
            app.supervisor.shutdown()
            app.pending = None
            app.message = {"text": session["message"], "action": "Leave the UPS connected.", "error": False}

    def cancelled(self):
        if self.app.store.data["outage"]:
            self._save(phase="paused", message="Timed retries are paused for this outage. Emergency protection remains active if enabled.")
            self.notice()

    def pause_retries(self):
        with self.app.lock:
            if not self.app.store.data["outage"] or not self.policy()["enabled"]:
                raise UserError("There is no active UPS outage to pause.", "Timed retries can be disabled in the UPS protection settings.")
            if self.app.shutdown_requested_at is not None or self.app.job:
                raise UserError("The Pi operation is already in progress.", "Wait for the operation to finish. Emergency protection stays active.")
            if self.app.pending:
                if self.app.pending["kind"] != "ups":
                    raise UserError("A separate Pi operation is in progress.", "Cancel that countdown first.")
                self.app.cancel()
            else:
                self.cancelled()
            self.app.message = {"text": "Timed RTC retries paused for this outage.", "action": "Emergency protection stays active if enabled. Stable utility power clears the pause.", "error": False}

    def failed(self, submitted=False, has_wake=True):
        if self.app.store.data["outage"] and (submitted or self.app.store.data["outage"]["phase"] != "paused"):
            self._save(phase=("paused" if has_wake else "stopped") if submitted else "blocked", message=("The shutdown response is uncertain; the wake alarm is preserved and this request will not be repeated." if has_wake else "The final shutdown response is uncertain. No timed wake is promised; this request will not be repeated.") if submitted else
                       "The retry failed before shutdown. The Pi stays on; reserve protection remains active.")
            self.notice()

