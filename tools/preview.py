#!/usr/bin/env python3
"""Developer-only local demo, with simulated Pi services and no host access."""

import argparse
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
import server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="pi5-demo-") as data:
        supervisor = FakeSupervisor()
        configure_phone(supervisor, time.time())
        supervisor.calendar_list = [{"entity_id": "calendar.demo_pi_sleep", "name": "Demo Pi Sleep"}]
        start = int(time.time()) + 3600
        stamp = lambda epoch: datetime.fromtimestamp(epoch, timezone.utc).isoformat()
        supervisor.events["calendar.demo_pi_sleep"] = [{"summary": "Demo Pi off", "start": {"dateTime": stamp(start + day * 86400)}, "end": {"dateTime": stamp(start + day * 86400 + 8 * 3600)}} for day in range(3)]
        now = stamp(int(time.time()))
        supervisor.power_rows = {"rows": [{"kind": "hook", "entity_id": "sensor.demo_local_power", "name": "Demo UPS", "state": "mains", "reported_at": now, "attributes": {"rtc_wake_power": {"schema_version": 1, "provider": "Simulated local adapter", "observed_at": now, "power_state": "mains", "battery_percent": 100, "runtime_seconds": 3600}}}]}
        app = server.Application(data, FakeRTC(time.time), supervisor, FakeHost(time.time()))
        app.refresh()

        class DemoHandler(server.IngressHandler):
            application = app
            allowed_peers = frozenset({"127.0.0.1"})

            def do_GET(self):
                if self.path == "/":
                    content = (server.WEB / "index.html").read_text().replace("Preview release · Test wake and UPS recovery on your own hardware.", "LOCAL DEMO · Simulated Pi, UPS, and phone. No real message or power operation.")
                    self._send(200, content.encode(), "text/html; charset=utf-8")
                else:
                    super().do_GET()

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
