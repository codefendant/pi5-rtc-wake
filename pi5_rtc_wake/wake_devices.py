"""Opt-in Wake on LAN through existing HA buttons, away from power control."""

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import queue
import re

from phone_messages import observed_epoch, states_by_id, text
from state import UserError, atomic_json

BUTTON = re.compile(r"button\.[a-z0-9_]{1,150}")
PING = re.compile(r"binary_sensor\.[a-z0-9_]{1,150}")
IDENTITY = re.compile(r"[a-f0-9]{64}")
MAX_DEVICES = 12
DEFAULTS = {"enabled": False, "devices": [], "after_scheduled_wake": True,
            "after_every_boot": False, "require_mains": True,
            "delay_seconds": 60, "check_timeout_seconds": 120}


def validate_settings(value):
    try:
        if not isinstance(value, dict) or set(value) != set(DEFAULTS):
            raise ValueError()
        result = deepcopy(value)
        for key in ("enabled", "after_scheduled_wake", "after_every_boot", "require_mains"):
            if type(value[key]) is not bool:
                raise ValueError()
        for key, low, high in (("delay_seconds", 30, 600), ("check_timeout_seconds", 15, 300)):
            if type(value[key]) is not int or not low <= value[key] <= high:
                raise ValueError()
        rows = result["devices"]
        if not isinstance(rows, list) or len(rows) > MAX_DEVICES:
            raise ValueError()
        seen = set()
        for row in rows:
            if (not isinstance(row, dict) or set(row) != {"entity_id", "identity", "name", "online_entity_id", "online_identity"}
                    or not isinstance(row["entity_id"], str) or not BUTTON.fullmatch(row["entity_id"])
                    or row["entity_id"] in seen or not isinstance(row["identity"], str) or not IDENTITY.fullmatch(row["identity"])
                    or not isinstance(row["name"], str) or not 1 <= len(row["name"]) <= 100):
                raise ValueError()
            seen.add(row["entity_id"])
            if row["online_entity_id"] is None:
                if row["online_identity"] is not None:
                    raise ValueError()
            elif (not isinstance(row["online_entity_id"], str) or not PING.fullmatch(row["online_entity_id"])
                  or not isinstance(row["online_identity"], str) or not IDENTITY.fullmatch(row["online_identity"])):
                raise ValueError()
            row["name"] = text(row["name"]) or row["entity_id"]
        if value["enabled"] and (not rows or not (value["after_scheduled_wake"] or value["after_every_boot"])):
            raise ValueError()
        return result
    except (KeyError, TypeError, ValueError):
        raise UserError("The device wake settings could not be saved.",
                        "Choose up to 12 Wake on LAN buttons, a wake trigger, and valid delay and check times.") from None


def registry_identity(row):
    if not all(isinstance(row.get(key), str) and row[key] for key in ("registry_id", "unique_id", "config_entry_id", "platform")):
        return None
    return hashlib.sha256(json.dumps([row[key] for key in ("registry_id", "unique_id", "config_entry_id", "platform")]).encode()).hexdigest()


def discover(states, metadata):
    if not isinstance(metadata, dict) or len(metadata) > 50000:
        raise UserError("The wake device list could not be read.", "Find devices again when Home Assistant is ready.")
    buttons, pings = [], []
    for entity, meta in metadata.items():
        if not isinstance(entity, str) or not isinstance(meta, dict) or meta.get("disabled") or not (identity := registry_identity(meta)):
            continue
        state = states.get(entity)
        if not state or state.get("state") == "unavailable":
            continue
        row = {"entity_id": entity, "identity": identity,
               "name": text(meta.get("name") or state["attributes"].get("friendly_name")) or entity,
               "area": text(meta.get("area"))}
        if BUTTON.fullmatch(entity) and meta.get("platform") == "wake_on_lan":
            buttons.append(row)
        elif PING.fullmatch(entity) and meta.get("platform") == "ping" and state["attributes"].get("device_class") == "connectivity":
            pings.append(row)
    return {"devices": sorted(buttons, key=lambda row: (row["name"].casefold(), row["entity_id"]))[:500],
            "pings": sorted(pings, key=lambda row: (row["name"].casefold(), row["entity_id"]))[:500]}


def ping_template(entities):
    if (not isinstance(entities, list) or len(entities) > MAX_DEVICES
            or any(not isinstance(entity, str) or not PING.fullmatch(entity) for entity in entities)):
        raise ValueError("Invalid Ping sensors")
    # All identifiers are validated; no user template or address is executed.
    return ("{% set ids = " + json.dumps(entities) + " %}{% set ns = namespace(rows=[]) %}"
            "{% for e in ids %}{% set s = states[e] %}{% if s is not none %}"
            "{% set ns.rows = ns.rows + [dict(entity_id=e, state=s.state, "
            "attributes=dict(restored=s.attributes.get('restored',false)), last_reported=s.last_reported.isoformat())] %}"
            "{% endif %}{% endfor %}{{ dict(rows=ns.rows)|to_json }}")


class WakeDevices:
    def __init__(self, app, directory):
        self.app = app
        self.path = Path(directory) / "wake_devices_state.json"
        self.trace = {"boot": {}, "receipt": {}, "last_run": {}, "layout_entries": []}
        self.storage_error = False
        try:
            if self.path.exists():
                if self.path.stat().st_size > 65536:
                    raise ValueError()
                trace = json.loads(self.path.read_text())
                if (not isinstance(trace, dict) or set(trace) != set(self.trace)
                        or any(not isinstance(trace[key], dict) for key in ("boot", "receipt", "last_run"))
                        or not isinstance(trace["layout_entries"], list) or len(trace["layout_entries"]) > 100
                        or any(not isinstance(entry, str) for entry in trace["layout_entries"])):
                    raise ValueError()
                for key in ("boot", "receipt"):
                    if trace[key] and not isinstance(trace[key].get("boot_id"), str):
                        raise ValueError()
                if trace["receipt"] and type(trace["receipt"].get("wake_epoch")) is not int:
                    raise ValueError()
                run = trace["last_run"]
                if run and (not isinstance(run.get("devices"), list) or len(run["devices"]) > MAX_DEVICES
                            or type(run.get("at")) is not int or not isinstance(run.get("trigger"), str)
                            or any(not isinstance(row, dict) or not isinstance(row.get("name"), str)
                                   or not isinstance(row.get("entity_id"), str) or not BUTTON.fullmatch(row["entity_id"])
                                   or row.get("state") not in {"waiting", "checking", "online", "submitted", "unconfirmed", "not_reachable", "unavailable", "skipped"}
                                   for row in run["devices"])):
                    raise ValueError()
                for row in run.get("devices", []):
                    if row["state"] in ("waiting", "checking"):
                        row.update(state="unconfirmed" if row["state"] == "checking" else "skipped",
                                   message="Previous wake run was interrupted. Check the device before retrying.")
                self.trace = trace
        except (OSError, ValueError, TypeError):
            self.storage_error = True
        self.options = {"devices": [], "pings": []}
        self.options_revision = 0
        self.tasks = queue.Queue(maxsize=1)
        self.busy = None
        self.started = app.monotonic()
        self.last_poll = -math.inf
        self.result = {"message": "Choose devices to set up this optional feature.", "error": False}
        if self.storage_error:
            self.result = {"message": "Device wake history could not be read. Automatic waking is paused.",
                           "action": "Review and save device settings to start with the next Pi boot.", "error": True}

    def _persist(self, trace):
        atomic_json(self.path, trace)
        self.trace = trace

    def snapshot(self):
        return {"settings": deepcopy(self.app.store.data["wake_devices"]), "busy": self.busy,
                "options_revision": self.options_revision, "result": deepcopy(self.result),
                "last_run": deepcopy(self.trace["last_run"]), "history_ok": not self.storage_error}

    def layout_needed(self, entry):
        return entry not in self.trace["layout_entries"]

    def layout_done(self, entry):
        with self.app.lock:
            if entry in self.trace["layout_entries"]:
                return
            trace = deepcopy(self.trace)
            trace["layout_entries"] = (trace["layout_entries"] + [entry])[-100:]
            try:
                self._persist(trace)
            except OSError:
                pass

    def scheduled_shutdown(self, pending):
        """Historical receipt only: all future date editing remains in Calendar."""
        trace = deepcopy(self.trace)
        trace["receipt"] = {"boot_id": self.app.host.boot_id(), "wake_epoch": pending["wake_epoch"]}
        trace["boot"] = {"boot_id": self.app.host.boot_id(), "phase": "shutdown"}
        try:
            self._persist(trace)
        except OSError:
            self.result = {"message": "This scheduled wake could not be recorded for other devices.",
                           "action": "Check the app's storage. The Pi's own wake alarm is unchanged.", "error": True}

    def other_power_action(self):
        """An app test, reboot, or UPS stop supersedes any Calendar receipt."""
        trace = deepcopy(self.trace)
        trace["receipt"] = {}
        trace["boot"] = {"boot_id": self.app.host.boot_id(), "phase": "other_power_action"}
        try:
            self._persist(trace)
        except OSError:
            self.storage_error = True
            self.result = {"message": "Device wake history could not be updated. Automatic waking is paused.",
                           "action": "Review and save device settings when the Pi is running again.", "error": True}

    def _read(self):
        return states_by_id(self.app.supervisor.message_states()), self.app.supervisor.wake_metadata()

    def _scan(self):
        states, metadata = self._read()
        options = discover(states, metadata)
        with self.app.lock:
            self.options = options
            self.options_revision += 1
            self.result = {"message": f"Found {len(options['devices'])} Wake on LAN button(s).", "error": False}

    def save_settings(self, payload):
        settings = validate_settings(payload)
        with self.app.lock:
            if self.app.store.read_only or self.app.shutdown_requested_at is not None or self.app.pending or self.busy:
                raise UserError("Wait before changing device wake settings.", "Let the current operation finish first.")
            old = self.app.store.data["wake_devices"]
            devices = {row["entity_id"]: row for row in self.options["devices"]}
            pings = {row["entity_id"]: row for row in self.options["pings"]}
            for row in settings["devices"]:
                known = devices.get(row["entity_id"])
                if not known or known["identity"] != row["identity"]:
                    if settings["enabled"] or row not in old["devices"]:
                        raise UserError("A selected wake device is no longer available.", "Find devices again, or remove it and save.")
                else:
                    row["name"] = known["name"]
                if row["online_entity_id"] and (not pings.get(row["online_entity_id"]) or pings[row["online_entity_id"]]["identity"] != row["online_identity"]):
                    if settings["enabled"] or row not in old["devices"]:
                        raise UserError("A selected Ping sensor is no longer available.", "Find devices again, or choose No online check.")
            if settings["require_mains"] and settings["enabled"] and not self.app.store.data["ups"]["source_id"]:
                raise UserError("Choose a UPS before requiring utility power.", "Set up the UPS card, or turn off Only wake on utility power.")
            # Save always consumes this host boot, including first-time enabling.
            trace = deepcopy(self.trace)
            trace["boot"] = {"boot_id": self.app.host.boot_id(), "phase": "configured"}
            self._persist(trace)
            self.app.store.data["wake_devices"] = settings
            try:
                self.app.store.save()
            except Exception:
                self.app.store.data["wake_devices"] = old
                raise
            self.storage_error = False
            self.result = {"message": "Device settings saved. Automatic waking starts with the next Pi boot.", "error": False}

    def begin(self, kind, payload):
        with self.app.lock:
            if kind not in ("scan", "wake") or self.busy or self.app.store.read_only or self.app.pending or self.app.job or self.app.shutdown_requested_at is not None:
                raise UserError("Device waking is unavailable right now.", "Let the current operation finish first.")
            if kind == "wake":
                if (set(payload) != {"confirmed", "expected_settings"} or payload["confirmed"] is not True
                        or payload["expected_settings"] != self.app.store.data["wake_devices"]
                        or not payload["expected_settings"]["devices"] or self.storage_error):
                    raise UserError("The selected devices changed or waking was not confirmed.", "Review and save device settings, then select Wake selected again.")
                self._guard(payload["expected_settings"])
            elif payload:
                raise UserError("The discovery request could not be read.", "Select Choose devices again.")
            self.tasks.put_nowait((kind, deepcopy(payload)))
            self.busy = "Finding devices…" if kind == "scan" else "Waking selected devices…"

    def _guard(self, settings):
        if (self.app.store.read_only or self.app.store.data["wake_devices"] != settings
                or self.app.pending or self.app.job or self.app.shutdown_requested_at is not None
                or self.app.stop_event.is_set()):
            raise UserError("Device waking stopped because the Pi's settings or power operation changed.", "Review the dashboard before waking devices again.")
        if settings["require_mains"]:
            source = self.app._selected_power()
            observed = source.get("observed_epoch") if source else None
            now = self.app.clock()
            if (not source or not source.get("ok") or source.get("power_state") != "mains"
                    or isinstance(observed, bool) or not isinstance(observed, (int, float))
                    or not self.app.host.boot_epoch(now) <= observed <= now + 30 or now - observed > 180):
                raise UserError("Waiting for fresh UPS readings showing utility power.", "Keep monitoring the UPS, or review Only wake on utility power in device settings.")

    def _boot_claim(self, phase):
        trace = deepcopy(self.trace)
        trace["boot"] = {"boot_id": self.app.host.boot_id(), "phase": phase}
        self._persist(trace)

    def poll_boot(self):
        with self.app.lock:
            settings = deepcopy(self.app.store.data["wake_devices"])
            boot = self.app.host.boot_id()
            if (not settings["enabled"] or self.storage_error or self.app.store.read_only or self.busy
                    or self.trace["boot"].get("boot_id") == boot):
                return
            receipt = self.trace["receipt"]
            boot_epoch = self.app.host.boot_epoch(self.app.clock())
            scheduled = (receipt.get("boot_id") != boot and receipt.get("boot_id") == self.trace["boot"].get("boot_id")
                         and type(receipt.get("wake_epoch")) is int
                         and -30 <= boot_epoch - receipt["wake_epoch"] <= 300)
            if not (settings["after_every_boot"] or settings["after_scheduled_wake"] and scheduled):
                self._boot_claim("skipped")
                self.result = {"message": "This Pi boot was not a recorded Calendar wake. No devices were woken.", "error": False}
                return
            if self.app.monotonic() - self.started < settings["delay_seconds"]:
                self.result = {"message": "Waiting for Home Assistant and the startup delay.", "error": False}
                return
            if self.app.monotonic() - self.started >= 900:
                self._boot_claim("skipped")
                self.result = {"message": "Automatic wake skipped: Home Assistant or utility power was not ready within 15 minutes.",
                               "action": "Review the dashboard and use Wake selected when ready.", "error": False}
                return
            try:
                self._guard(settings)
            except UserError as error:
                self.result = {"message": error.message, "action": error.action, "error": False}
                return
            self.busy = "Waking devices after Pi boot…"
        try:
            self._wake(settings, "Calendar wake" if scheduled else "Pi boot")
        finally:
            with self.app.lock:
                self.busy = None

    def _update_run(self, run):
        with self.app.lock:
            trace = deepcopy(self.trace)
            trace["last_run"] = deepcopy(run)
            self._persist(trace)

    def _wake(self, settings, trigger):
        # Registry and Core requests never run while holding the power-control lock.
        states, metadata = self._read()
        available = discover(states, metadata)
        buttons = {row["entity_id"]: row for row in available["devices"]}
        pings = {row["entity_id"]: row for row in available["pings"]}
        run = {"trigger": trigger, "at": int(self.app.clock()), "devices": [
            {"entity_id": row["entity_id"], "name": row["name"], "state": "waiting", "message": "Waiting to send."}
            for row in settings["devices"]]}
        with self.app.lock:
            self._guard(settings)
            if trigger != "Manual wake" and self.app.monotonic() - self.started >= 900:
                raise UserError("The automatic wake startup window expired.", "Use Wake selected when Home Assistant is ready.")
            self._boot_claim("submitted")
            self._update_run(run)
        watch = {}
        for target, outcome in zip(settings["devices"], run["devices"]):
            with self.app.lock:
                self._guard(settings)
            if not buttons.get(target["entity_id"]) or buttons[target["entity_id"]]["identity"] != target["identity"]:
                outcome.update(state="unavailable", message="Wake button changed or is unavailable. Choose devices again.")
                self._update_run(run)
                continue
            if target["online_entity_id"] and (not pings.get(target["online_entity_id"]) or pings[target["online_entity_id"]]["identity"] != target["online_identity"]):
                outcome.update(state="unavailable", message="Ping sensor changed or is unavailable. Review the online check.")
                self._update_run(run)
                continue
            # Claim before I/O. An uncertain service response is never retried automatically.
            outcome.update(state="unconfirmed", message="Wake request started; delivery is not confirmed.", sent_at=self.app.clock())
            self._update_run(run)
            try:
                self.app.supervisor.press_wake_button(target["entity_id"], target["identity"])
            except UserError:
                outcome.update(message="Home Assistant did not confirm the wake request. It may have been sent; check the device before retrying.")
            else:
                outcome.update(state="checking" if target["online_entity_id"] else "submitted",
                               message="Wake packet requested. Waiting for a fresh Ping reading." if target["online_entity_id"] else "Wake packet requested. No online check selected.")
                if target["online_entity_id"]:
                    watch[target["entity_id"]] = target
            self._update_run(run)
        deadline = self.app.monotonic() + settings["check_timeout_seconds"]
        while watch and self.app.monotonic() < deadline:
            with self.app.lock:
                self._guard(settings)
            result = self.app.supervisor.wake_ping_states(list({row["online_entity_id"] for row in watch.values()}))
            rows = states_by_id(result.get("rows", []) if isinstance(result, dict) else [])
            for outcome in run["devices"]:
                target = watch.get(outcome["entity_id"])
                if not target:
                    continue
                reading = rows.get(target["online_entity_id"], {})
                observed = observed_epoch(reading)
                if (reading.get("state") == "on" and not reading.get("attributes", {}).get("restored")
                        and reading.get("identity") == target["online_identity"]
                        and observed is not None and max(outcome["sent_at"], self.app.host.boot_epoch(self.app.clock())) <= observed <= self.app.clock() + 30
                        and self.app.clock() - observed <= 60):
                    outcome.update(state="online", message="Reachable: confirmed by a fresh Ping reading.", observed_at=int(observed))
                    del watch[outcome["entity_id"]]
            self._update_run(run)
            if watch and self.app.stop_event.wait(2):
                break
        for outcome in run["devices"]:
            if outcome["entity_id"] in watch:
                outcome.update(state="not_reachable", message="No fresh online confirmation within the check time. Check the device and its Ping sensor.")
        self._update_run(run)
        with self.app.lock:
            self.result = {"message": "Device wake run finished. See each device for its result.", "error": False}
        self.app.dashboard.record("Wake other devices: " + trigger + "; " + ", ".join(row["name"] + " — " + row["state"].replace("_", " ") for row in run["devices"]))

    def process_once(self):
        try:
            try:
                kind, payload = self.tasks.get_nowait()
            except queue.Empty:
                if self.app.monotonic() - self.last_poll >= 5:
                    self.last_poll = self.app.monotonic()
                    self.poll_boot()
                return
            try:
                if kind == "scan":
                    self._scan()
                else:
                    self._wake(payload["expected_settings"], "Manual wake")
            finally:
                with self.app.lock:
                    self.busy = None
                self.tasks.task_done()
        except (UserError, OSError, ValueError, TypeError, KeyError):
            with self.app.lock:
                run = deepcopy(self.trace["last_run"])
                for row in run.get("devices", []):
                    if row["state"] in ("waiting", "checking"):
                        row.update(state="unconfirmed" if row["state"] == "checking" else "skipped",
                                   message="Wake run stopped. Check this device before retrying.")
                try:
                    if run:
                        self._update_run(run)
                except OSError:
                    self.trace["last_run"] = run
                self.result = {"message": "Device waking could not finish. Check the results before trying again.",
                               "action": "Find devices again and check Home Assistant, UPS readings, and app storage. An uncertain wake request is not repeated automatically.", "error": True}

    def run(self):
        while not self.app.stop_event.is_set():
            self.process_once()
            self.app.stop_event.wait(0.5)
