from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pi5_rtc_wake"))
import rtc_wake
from services import Host
import host_helper


class HardwareBoundaryTests(unittest.TestCase):
    def test_empty_disabled_alarm_is_not_a_clock_failure(self):
        device = rtc_wake.LinuxRTC()
        empty = bytearray(rtc_wake.RTC_ALARM.pack(0, 0, *([0] * 9)))
        with patch.object(device, "_read", return_value=empty):
            self.assertEqual(device.read_alarm(), {"enabled": False, "epoch": 0})

    def test_invalid_enabled_alarm_is_rejected(self):
        device = rtc_wake.LinuxRTC()
        invalid = bytearray(rtc_wake.RTC_ALARM.pack(1, 0, *([0] * 9)))
        with patch.object(device, "_read", return_value=invalid):
            with self.assertRaises(ValueError): device.read_alarm()

    def test_host_operation_keeps_payload_out_of_shell_arguments(self):
        host = Host()
        malicious = {"config_sha256": "'; $(touch /tmp/should-never-exist) `id`"}
        captured = {}
        def fake_run(arguments, **kwargs):
            captured.update(arguments=arguments, **kwargs)
            class Result:
                returncode = 0
                stdout = '{"ok":true,"data":{"reboot_required":true}}'
            return Result()
        with patch("services.subprocess.run", side_effect=fake_run):
            host.command("apply", malicious)
        self.assertNotIn(malicious["config_sha256"], " ".join(captured["arguments"]))
        self.assertNotIn("shell", captured)
        # Parse, rather than execute, the program sent to the host.
        import ast
        ast.parse(captured["input"])
        self.assertIn("--root", captured["arguments"])


if __name__ == "__main__": unittest.main()
