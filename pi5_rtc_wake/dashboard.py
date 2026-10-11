"""Native dashboard setup and a small, authenticated adapter to existing actions."""

from copy import deepcopy
import json
from pathlib import Path
import re
import threading

from state import UserError, atomic_json

PATH = "pi-wake-sleep"
RESOURCE = "/pi5_rtc_wake/pi-cards.js"
DEFAULT_CALENDAR = "Pi Sleep"
KINDS = ("setup", "status", "shutdown", "wake", "calendar", "ups", "controls", "devices", "messages", "assist", "activity")


def starter_config(entry_id=""):
    """A real storage dashboard; subsequent updates never replace its config."""
    sections = []
    for kind in KINDS:
        span = 3 if kind in ("setup", "activity") else 2 if kind in ("calendar", "devices") else 1
        sections.append({"type": "grid", "column_span": span, "cards": [
            {"type": f"custom:pi-wake-{kind}-card", "entry_id": entry_id,
             "grid_options": {"columns": 12, "rows": "auto"}}]})
    return {"views": [{"title": "Pi Wake & Sleep", "path": "overview", "type": "sections",
                       "max_columns": 3, "dense_section_placement": True, "sections": sections}]}


def restore_cards(config, entry_id):
    """Replace only our cards, preserving user cards and dashboard metadata."""
    if not isinstance(config, dict) or not isinstance(config.get("views"), list) or not config["views"]:
        raise UserError("The saved dashboard layout could not be read.", "Open Edit dashboard and add Pi cards individually.")
    result = deepcopy(config)
    types = {f"custom:pi-wake-{kind}-card" for kind in KINDS}

    def keep(value):
        if isinstance(value, list):
            return [updated for item in value if (updated := keep(item)) is not None]
        if isinstance(value, dict):
            if value.get("type") in types and value.get("entry_id", "") in ("", entry_id):
                return None
            return {key: keep(item) if key in ("cards", "sections") else item for key, item in value.items()}
        return value

    target = next((view for view in result["views"] if view.get("path") == "overview"), result["views"][0])
    if target.get("type") != "sections":
        # Preserve a user's changed view type and add a separate native Pi view.
        for view in result["views"]:
            if "cards" in view:
                view["cards"] = keep(view["cards"])
        native = starter_config(entry_id)["views"][0]
        native["path"] = "pi-controls"
        if any(view.get("path") == "pi-controls" for view in result["views"]):
            raise UserError("A Pi controls view already exists.", "Use Edit dashboard to add or move the Pi cards without changing your other views.")
        result["views"].append(native)
    else:
        target["sections"] = keep(target.get("sections", [])) + starter_config(entry_id)["views"][0]["sections"]
    return result


def add_wake_devices_card(config, entry_id):
    """One additive upgrade; never replace existing cards or customized views."""
    if not isinstance(config, dict) or not isinstance(config.get("views"), list) or not config["views"]:
        raise UserError("The dashboard layout could not be read.", "Use Edit dashboard → Add card → Wake other devices.")
    def present(value):
        if isinstance(value, list):
            return any(present(row) for row in value)
        if isinstance(value, dict):
            return (value.get("type") == "custom:pi-wake-devices-card" and value.get("entry_id", "") in ("", entry_id)
                    or any(present(value.get(key)) for key in ("cards", "sections")))
        return False
    if any(present(view) for view in config["views"]):
        return deepcopy(config)
    result = deepcopy(config)
    target = next((view for view in result["views"] if isinstance(view, dict) and view.get("path") == "overview"), result["views"][0])
    section = next(row for row in starter_config(entry_id)["views"][0]["sections"] if row["cards"][0]["type"] == "custom:pi-wake-devices-card")
    if target.get("type") == "sections":
        target.setdefault("sections", []).append(section)
    else:
        target.setdefault("cards", []).extend(section["cards"])
    return result


class Dashboard:
    def __init__(self, app, data):
        self.app = app
        self.operation_lock = threading.Lock()
        self.connection = "Connect the dashboard to begin."
        self.restart_needed = False
        self.last_contact = None
        self.history_path = Path(data) / "activity.json"
        try:
            rows = json.loads(self.history_path.read_text())
            self.history = [row for row in rows if isinstance(row, dict)
                            and type(row.get("time")) is int and isinstance(row.get("text"), str)][:30]
        except (OSError, ValueError, TypeError):
            self.history = []

    def record(self, text):
        with self.app.lock:
            self.history.insert(0, {"time": int(self.app.clock()), "text": str(text)[:250]})
            del self.history[30:]
            try:
                atomic_json(self.history_path, self.history)
            except OSError:
                pass  # Activity is informational and never blocks a power operation.

    def snapshot(self):
        return {"connected": self.app.store.data["dashboard"]["connected"],
                "active": self.last_contact is not None and self.app.monotonic() - self.last_contact < 90,
                "connection": self.connection, "restart_needed": self.restart_needed,
                "path": "/" + PATH, "activity": deepcopy(self.history)}

    def connect(self, payload):
        if payload != {"confirmed": True}:
            raise UserError("Dashboard setup was not confirmed.", "Select Connect dashboard and read the setup explanation.")
        if not self.operation_lock.acquire(blocking=False):
            raise UserError("Dashboard setup is in progress.", "Wait for it to finish.")
        try:
            version = self.app.supervisor.core_version()
            match = re.fullmatch(r"(\d+)\.(\d+)\.\d+(?:[a-z0-9.]+)?", version)
            if not match or tuple(map(int, match.groups())) < (2026, 10):
                raise UserError("This dashboard needs Home Assistant 2026.10 or newer.",
                                "Update Home Assistant Core in Settings → System → Updates.")
            with self.app.lock:
                if self.app.store.read_only or self.app.job or self.app.pending or self.app.shutdown_requested_at is not None or self.app.store.data["outage"]:
                    raise UserError("Wait before connecting the dashboard.", "Finish any Pi operation and wait for stable power.")
            changed = self.app.assistant.installer.install()
            token = self.app.assistant._secret()
            with self.app.lock:
                old = deepcopy(self.app.store.data["dashboard"])
                self.app.store.data["dashboard"]["connected"] = True
                try:
                    self.app.store.save()
                except Exception:
                    self.app.store.data["dashboard"] = old
                    raise
                self.restart_needed = self.restart_needed or changed
            self.app.supervisor.assist_discovery(8098, token)
            self.connection = "Restart Home Assistant, then add Pi Wake & Sleep in Devices & services." if changed else "Open Devices & services and add the discovered Pi Wake & Sleep integration."
            self.app.message = {"text": "Dashboard companion installed." if changed else "Dashboard connection offered.",
                                "action": self.connection, "error": False}
            self.record("Dashboard connection offered to Home Assistant.")
        except UserError as error:
            self.connection = f"{error.message} {error.action}"
            raise
        finally:
            self.operation_lock.release()

    def ready(self, payload):
        if (not isinstance(payload, dict) or set(payload) != {"entry_id"}
                or not isinstance(payload["entry_id"], str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", payload["entry_id"])):
            raise UserError("The dashboard connection could not be checked.", "Reconnect the dashboard from the app.")
        entry_id = payload["entry_id"]
        result = self.app.supervisor.ensure_dashboard(entry_id, add_wake_devices=self.app.wake_devices.layout_needed(entry_id))
        self.app.wake_devices.layout_done(entry_id)
        self.connection = "Connected to Home Assistant. " + result.get("message", "")
        self.restart_needed = False
        if result.get("created"):
            self.record("Pi dashboard created. You can add your own cards through Edit dashboard.")
        return result

    def status(self):
        # This endpoint is reached through the authenticated HA companion. A
        # saved installation choice alone is not evidence of a live connection.
        with self.app.lock:
            self.last_contact = self.app.monotonic()
        result = self.app.snapshot()
        result.pop("csrf", None)
        result.update(protocol=1, **deepcopy(self.app.store.data["assist"]),
                      uptime_seconds=max(0, int(self.app.clock() - self.app.host.boot_epoch(self.app.clock()))),
                      current_epoch=int(self.app.clock()))
        return result

    def create_calendar(self, payload):
        if payload != {"confirmed": True}:
            raise UserError("Calendar creation was not confirmed.", "Select Create Pi Sleep calendar.")
        if not self.operation_lock.acquire(blocking=False):
            raise UserError("Calendar setup is in progress.", "Wait for it to finish.")
        try:
            with self.app.lock:
                if self.app.store.read_only or self.app.job or self.app.pending or self.app.shutdown_requested_at is not None:
                    raise UserError("Wait before choosing a calendar.", "Finish the Pi operation first.")
                if self.app.store.data["schedule"]["calendar_entity_id"]:
                    raise UserError("A calendar is already selected.", "Use Change calendar if you want a different calendar.")
            entity = self.app.supervisor.ensure_sleep_calendar()
            with self.app.lock:
                if self.app.store.data["schedule"]["calendar_entity_id"] or self.app.job or self.app.pending:
                    raise UserError("The calendar selection changed during setup.", "Review the current selection. Pi Sleep was kept in Home Assistant.")
                schedule = {**self.app.store.data["schedule"], "enabled": False, "calendar_entity_id": entity}
                self.app.save_settings(schedule)
            self.app.refresh_calendar(force_discovery=True)
            self.record("Pi Sleep calendar selected. Automatic scheduling remains off.")
        finally:
            self.operation_lock.release()

    def action(self, action, payload):
        if not isinstance(payload, dict):
            raise UserError("This action could not be read.", "Refresh the dashboard.")
        if action == "create-calendar":
            self.create_calendar(payload)
        elif action == "settings":
            self.app.save_settings(payload)
        elif action == "power-settings":
            self.app.save_power_settings(payload)
        elif action == "recovery-settings":
            self.app.recovery.save_settings(payload)
        elif action == "message-settings":
            self.app.messages.save_settings(payload)
        elif action == "wake-device-settings":
            self.app.wake_devices.save_settings(payload)
        elif action in ("scan-wake-devices", "wake-devices"):
            self.app.wake_devices.begin("scan" if action == "scan-wake-devices" else "wake", payload)
        elif action == "assist-settings":
            self.app.assistant.save_settings(payload)
        elif action == "assist-review":
            self.app.assistant.review(payload)
        elif action == "connect-assist":
            self.app.assistant.connect(payload)
        elif action in ("scan-messages", "preview-message", "send-message"):
            self.app.messages.begin({"scan-messages": "scan", "preview-message": "preview", "send-message": "send"}[action], payload)
        elif action == "enable-nut-sensor":
            self.app.enable_nut_sensor(payload)
        elif action == "pause-rtc-retries":
            self.app.recovery.pause_retries()
        elif action == "confirm-test":
            self.app.confirm_test(payload)
        elif action == "reject-test":
            self.app.reject_test()
        elif action == "cancel":
            if self.app.pending and self.app.pending.get("emergency"):
                raise UserError("Emergency low-battery protection is active.", "Review UPS protection settings to change that policy.")
            self.app.cancel()
        elif action == "keep-awake":
            self.app.set_keep_awake(payload)
        elif action == "reboot-now":
            if payload != {"confirmed": True}:
                raise UserError("The reboot was not confirmed.", "Read the reboot confirmation.")
            self.app.begin_job("reboot", {"confirmed": True, "dashboard_reviewed": True})
        elif action == "restore-cards":
            if (set(payload) != {"confirmed", "entry_id"} or payload["confirmed"] is not True
                    or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", str(payload["entry_id"]))):
                raise UserError("Restoring Pi cards was not confirmed.", "Review the Restore default Pi cards explanation.")
            self.app.supervisor.restore_dashboard(payload["entry_id"])
        elif action in ("check", "scan-ups", "prepare", "reboot", "test"):
            self.app.begin_job(action, payload)
        else:
            raise UserError("That dashboard action is not supported.", "Update the app and reconnect its dashboard.")
        if action not in ("check", "scan-ups", "scan-messages", "preview-message", "scan-wake-devices", "wake-devices"):
            self.record({"settings": "Calendar settings saved.", "power-settings": "UPS settings saved.",
                         "message-settings": "Phone settings saved.", "wake-device-settings": "Device wake settings saved.", "assist-settings": "Assist settings saved.",
                         "cancel": "Current shutdown cancelled; future dates and emergency protection are kept.",
                         "keep-awake": "Keep awake enabled; all app shutdowns suspended." if self.app.store.data["keep_awake"] else "Shutdowns resumed using saved settings.",
                         "confirm-test": "Wake test passed."}.get(action, "Requested: " + action.replace("-", " ") + "."))
        return {"ok": True}
