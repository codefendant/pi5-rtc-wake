#!/usr/bin/env python3
"""Developer-only local demo, with simulated Pi services and no host access."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from test_setup import FakeRTC, FakeSupervisor, FakeHost
from test_phone_messages import configure_phone
from test_wake_devices import configure_devices
from assist_install import Installer
import server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--ready", action="store_true", help="Simulate a completed wake test for native-card previews")
    parser.add_argument("--protected", action="store_true", help="Simulate first-run Protection mode being on")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="pi5-demo-") as data:
        supervisor = FakeSupervisor()
        if args.protected:
            supervisor.app_info = lambda: {"slug": "local_pi5_rtc_wake", "protected": True}
        configure_phone(supervisor, time.time())
        configure_devices(supervisor, time.time())
        def demo_pings(entities):
            from wake_devices import registry_identity
            return {"rows": [{"entity_id": entity, "state": "on", "attributes": {},
                              "last_reported": datetime.now(timezone.utc).isoformat(),
                              "identity": registry_identity(supervisor.wake_registry[entity])} for entity in entities]}
        supervisor.wake_ping_states = demo_pings
        supervisor.calendar_list = [{"entity_id": "calendar.demo_pi_sleep", "name": "Demo Pi Sleep"}]
        start = int(time.time()) + 3600
        stamp = lambda epoch: datetime.fromtimestamp(epoch, timezone.utc).isoformat()
        supervisor.events["calendar.demo_pi_sleep"] = [{"summary": "Demo Pi off", "start": {"dateTime": stamp(start + day * 86400)}, "end": {"dateTime": stamp(start + day * 86400 + 8 * 3600)}} for day in range(3)]
        now = stamp(int(time.time()))
        supervisor.power_rows = {"rows": [{"kind": "hook", "entity_id": "sensor.demo_local_power", "name": "Demo UPS", "state": "mains", "reported_at": now, "attributes": {"rtc_wake_power": {"schema_version": 1, "provider": "Simulated local adapter", "observed_at": now, "power_state": "mains", "battery_percent": 100, "runtime_seconds": 3600}}}]}
        app = server.Application(data, FakeRTC(time.time), supervisor, FakeHost(time.time()))
        demo_config = Path(data) / "homeassistant"
        demo_config.mkdir()
        app.assistant.installer = Installer(data, demo_config)
        app.refresh()
        if args.ready:
            app.store.data["test"] = {"status": "passed", "fingerprint": app.checks.get("fingerprint")}
            app.save_settings({**app.store.data["schedule"], "calendar_entity_id": "calendar.demo_pi_sleep", "enabled": True})
            app.save_power_settings({"source_id": "hook:sensor.demo_local_power", "notifications": False, "low_battery_percent": 25})
            app.dashboard.connect({"confirmed": True})
            app.dashboard.ready({"entry_id": "demo-entry", "companion_version": app.dashboard.companion_version})
            app.dashboard.record("Wake test passed. Calendar scheduling enabled for this simulated preview.")
        supervisor.ensure_dashboard("demo-entry")

        class DemoHandler(server.IngressHandler):
            application = app
            allowed_peers = frozenset({"127.0.0.1"})

            def send_header(self, key, value):
                if key == "Content-Security-Policy" and self.path.split("?", 1)[0] == "/native":
                    # Developer-only local harness. The production Ingress policy is unchanged.
                    value = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'none'"
                super().send_header(key, value)

            def do_GET(self):
                if self.path.split("?", 1)[0] == "/native":
                    self._send(200, (ROOT / "tools/native_preview.html").read_bytes(), "text/html; charset=utf-8")
                elif self.path == "/native-cards.js":
                    self._send(200, (ROOT / "pi5_rtc_wake/companion/pi5_rtc_wake/frontend/pi-cards.js").read_bytes(), "text/javascript; charset=utf-8")
                elif self.path == "/":
                    content = (server.WEB / "index.html").read_text().replace("Preview release · Test wake and UPS recovery on your own hardware.", "LOCAL DEMO · Simulated Pi, UPS, and phone. No real message or power operation.")
                    self._send(200, content.encode(), "text/html; charset=utf-8")
                else:
                    super().do_GET()

            def do_POST(self):
                if self.path != "/demo/ha-ws":
                    return super().do_POST()
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 1 <= length <= 16384:
                        raise ValueError()
                    request = json.loads(self.rfile.read(length))
                    if request["type"] == "pi5_rtc_wake/status":
                        if app.store.data["dashboard"]["connected"] and app.dashboard.restart_needed:
                            app.dashboard.ready({"entry_id": "demo-entry", "companion_version": app.dashboard.companion_version})
                        result = app.dashboard.status()
                    elif request["type"] == "pi5_rtc_wake/entries":
                        result = [{"entry_id": "demo-entry", "title": "Home Assistant Pi"}]
                    elif request["type"] == "pi5_rtc_wake/message_options":
                        result = app.messages.options
                    elif request["type"] == "pi5_rtc_wake/wake_device_options":
                        result = app.wake_devices.options
                    elif request["type"] == "pi5_rtc_wake/action":
                        payload = request.get("payload", {})
                        if request["action"] == "restore-cards":
                            payload = {**payload, "entry_id": "demo-entry"}
                        result = app.dashboard.action(request["action"], payload)
                    else:
                        raise ValueError()
                    self._send(200, result)
                except server.UserError as error:
                    self._send(409, {"message": error.message + " " + error.action})
                except (ValueError, KeyError, TypeError):
                    self._send(400, {"message": "This simulated request could not be read."})

        thread = threading.Thread(target=app.run, daemon=True)
        thread.start()
        http = server.ThreadingHTTPServer(("127.0.0.1", args.port), DemoHandler)
        print(f"LOCAL DEMO at http://127.0.0.1:{http.server_port}/ — simulated services only", flush=True)
        try:
            http.serve_forever()
        finally:
            app.stop_event.set()
            http.server_close()


if __name__ == "__main__": main()
