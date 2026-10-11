"""Runtime display works in monitoring mode without authorizing power actions."""

from copy import deepcopy
import unittest

from test_setup import Fixture
from test_power_sources import nut_rows, stamp
from power_sources import discover_sources, monitor_runtime


class RuntimeDisplayTests(unittest.TestCase, Fixture):
    def setUp(self):
        self.setup_app()
        self.rows = nut_rows(self.now)
        self.runtime = {**self.rows["rows"][0], "entity_id": "sensor.renamed_remaining", "state": "72",
                        "attributes": {"device_class": "duration", "unit_of_measurement": "min", "friendly_name": "Renamed runtime"}}
        self.rows["rows"].append(self.runtime)
        self.registry = [{"entity_id": self.runtime["entity_id"], "device_id": "device_apc", "runtime_measurement": True, "disabled_by": None, "can_enable": False}]

    def display(self, selected=None, now=None):
        source = discover_sources(self.rows, self.now if now is None else now)[0][0]
        return monitor_runtime(source, selected, self.registry, self.now if now is None else now)

    def test_monitoring_only_automatically_displays_verified_nut_runtime(self):
        self.supervisor.power_rows = self.rows
        self.supervisor.sensor_registry = self.registry
        self.app.refresh_power(settings=True)
        self.app.save_power_settings({"source_id": "nut:device_apc", "notifications": False, "low_battery_percent": 25})
        settings = deepcopy(self.app.store.data["recovery"])
        status = self.app.snapshot()
        self.assertEqual(status["ups"]["runtime"]["seconds"], 4320)
        self.assertEqual(status["ups"]["runtime"]["entity_id"], "sensor.renamed_remaining")
        self.assertEqual(status["ups"]["runtime"]["state"], "fresh")
        self.assertIsNone(status["ups"]["selected"]["runtime_seconds"])
        self.assertEqual(self.app.store.data["recovery"], settings)
        self.assertFalse(self.app.recovery.protection_eligible())
        self.runtime["state"] = "65"
        self.app.refresh_power()
        self.assertEqual(self.app.snapshot()["ups"]["runtime"]["seconds"], 3900)

    def test_delay_setpoint_and_other_ups_measurements_are_not_auto_selected(self):
        self.registry = [{"entity_id": self.runtime["entity_id"], "device_id": "device_apc", "runtime_measurement": False, "disabled_by": None},
                         {"entity_id": "sensor.another_remaining", "device_id": "other_ups", "runtime_measurement": True, "disabled_by": None}]
        self.assertEqual(self.display()["state"], "choose")
        self.assertIsNone(self.display()["seconds"])
        self.assertEqual(self.display("sensor.another_remaining")["state"], "unavailable")

    def test_multiple_runtime_measurements_require_a_choice(self):
        self.registry.append({**self.registry[0], "entity_id": "sensor.second_runtime"})
        self.assertEqual(self.display()["state"], "choose")
        self.assertEqual(self.display(self.runtime["entity_id"])["seconds"], 4320)

    def test_disabled_sensor_and_stale_reading_have_distinct_next_actions(self):
        self.rows["rows"].remove(self.runtime)
        self.registry[0].update(disabled_by="integration", can_enable=True)
        self.assertEqual(self.display()["state"], "disabled")
        self.assertIn("enable", self.display()["message"])
        self.rows["rows"].append(self.runtime)
        self.registry[0]["disabled_by"] = None
        self.runtime["reported_at"] = stamp(self.now - 181)
        self.assertEqual(self.display()["state"], "stale")
        self.assertIsNone(self.display()["seconds"])

    def test_aging_battery_runtime_is_conservative_but_utility_estimate_does_not_count_down(self):
        self.assertEqual(self.display(now=self.now + 30)["seconds"], 4320)
        self.rows["rows"][0]["state"] = "OB"
        self.assertEqual(self.display(now=self.now + 30)["seconds"], 4290)
        self.assertEqual(self.display(now=self.now + 181)["state"], "stale")

    def test_unavailable_values_and_zero_are_not_confused(self):
        self.runtime["state"] = "unavailable"
        self.assertEqual(self.display()["state"], "unavailable")
        self.assertIsNone(self.display()["seconds"])
        self.runtime["state"] = "0"
        self.assertEqual(self.display()["state"], "fresh")
        self.assertEqual(self.display()["seconds"], 0)
