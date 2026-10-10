"""Host-entry failures must be useful without exposing host output or secrets."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pi5_rtc_wake"))
import host_helper
from services import Host, HostError
from services import effective_host_capabilities


class HostDiagnosticsTests(unittest.TestCase):
    def result(self, stdout="", stderr="", returncode=1):
        return subprocess.CompletedProcess([], returncode, stdout, stderr)

    def failure(self, result, operation="inspect"):
        with patch("services.subprocess.run", return_value=result) as run:
            with self.assertRaises(HostError) as caught:
                Host().command(operation)
        run.assert_called_once()
        return caught.exception

    def test_permission_denied_has_specific_guidance_and_error_code(self):
        error = self.failure(self.result(stderr="nsenter: reassociate to namespace 'ns/mnt' failed: Operation not permitted"))
        self.assertEqual(error.details["reason"], "permission_denied")
        self.assertEqual(error.details["exit_code"], 1)
        self.assertIn("already off", error.action)
        self.assertNotIn("update Home Assistant OS", error.action)

    def test_missing_app_tool_is_not_misreported_as_protection_mode(self):
        with patch("services.subprocess.run", side_effect=FileNotFoundError(2, "private path")):
            with self.assertRaises(HostError) as caught:
                Host().inspect()
        self.assertEqual(caught.exception.details["errno"], 2)
        self.assertIn("tool is missing", caught.exception.message)
        self.assertNotIn("Protection mode", caught.exception.action)

    def test_missing_ptrace_is_visible_even_when_namespace_switching_is_granted(self):
        host = Host()
        capabilities = (1 << 21) | (1 << 18)
        private = "Name:\tprivate\nCapEff:\t%016x\n" % capabilities
        with patch.object(Path, "read_text", return_value=private):
            with patch("services.subprocess.run", return_value=self.result(stderr="Permission denied")):
                with self.assertRaises(HostError) as caught:
                    host.inspect()
        self.assertEqual(caught.exception.details["effective_capabilities"],
                         {"SYS_ADMIN": True, "SYS_PTRACE": False, "SYS_CHROOT": True})
        self.assertNotIn("private", json.dumps(caught.exception.details))

    def test_all_bridge_permissions_can_be_reported_without_allowing_a_failed_check(self):
        host = Host()
        capabilities = (1 << 21) | (1 << 19) | (1 << 18)
        with patch.object(Path, "read_text", return_value="CapEff:\t%016x\n" % capabilities):
            with patch("services.subprocess.run", return_value=self.result(stderr="Permission denied")):
                with self.assertRaises(HostError) as caught:
                    host.inspect()
        self.assertTrue(all(caught.exception.details["effective_capabilities"].values()))
        self.assertEqual(caught.exception.details["reason"], "permission_denied")

    def test_missing_capability_metadata_does_not_hide_the_original_host_error(self):
        host = Host()
        for metadata in ("CapEff:\tinvalid\n", "CapEff:\t12345678901234567\n", ""):
            with self.subTest(metadata=metadata), patch.object(Path, "read_text", return_value=metadata):
                self.assertIsNone(effective_host_capabilities())
        with patch.object(Path, "read_text", side_effect=OSError("private failure")):
            with patch("services.subprocess.run", return_value=self.result(stderr="Permission denied")):
                with self.assertRaises(HostError) as caught:
                    host.inspect()
        self.assertEqual(caught.exception.details["reason"], "permission_denied")
        self.assertNotIn("effective_capabilities", caught.exception.details)

    def test_incompatible_nsenter_flags_identify_an_app_tool_problem(self):
        error = self.failure(self.result(stderr="nsenter: unrecognized option '--root'"))
        self.assertEqual(error.details["reason"], "unsupported_option")
        self.assertIn("needs a repair", error.action)

    def test_missing_host_python_identifies_helper_start(self):
        error = self.failure(self.result(stderr="nsenter: failed to execute /usr/bin/python3: No such file or directory"))
        self.assertEqual(error.details["reason"], "not_found")
        self.assertIn("start its helper", error.message)

    def test_malformed_json_is_rejected_without_leaking_the_output(self):
        for output in ("SECRET OUTPUT", "[]", "null", '"string"', '{"ok":true,"data":[]}'):
            with self.subTest(output=output):
                error = self.failure(self.result(stdout=output, returncode=0))
                self.assertEqual(error.details["reason"], "invalid_result")
                self.assertNotIn("SECRET OUTPUT", json.dumps(error.details))

    def test_success_output_cannot_override_a_failed_exit_status(self):
        error = self.failure(self.result(stdout='{"ok":true,"data":{"wake_configured":true}}', returncode=9))
        self.assertEqual(error.details["exit_code"], 9)

    def test_helper_failure_preserves_the_failed_firmware_step(self):
        output = json.dumps({"ok": False, "error": {"step": "boot_partition", "error_type": "CalledProcessError", "exit_code": 3}})
        error = self.failure(self.result(stdout=output))
        self.assertEqual(error.details["step"], "boot_partition")
        self.assertEqual(error.details["exit_code"], 3)
        self.assertEqual(error.details["helper_exit_code"], 1)
        self.assertIn("boot partition", error.message)

    def test_host_timeout_is_not_retried(self):
        with patch("services.subprocess.run", side_effect=subprocess.TimeoutExpired("private command", 65)) as run:
            with self.assertRaises(HostError) as caught:
                Host().inspect()
        run.assert_called_once()
        self.assertEqual(caught.exception.details["error_type"], "TimeoutExpired")

    def test_preparation_failure_requires_readback_before_continuing(self):
        error = self.failure(self.result(stderr="Read-only file system"), operation="apply")
        self.assertIn("could not be verified", error.message)
        self.assertIn("Keep the power connected", error.action)
        self.assertIn("Reboot", error.action)

    def test_raw_stderr_config_and_container_secrets_are_not_forwarded(self):
        private = "SUPERVISOR_TOKEN=never-expose\nBOOT_ORDER=0xf416\nsecret text"
        with self.assertLogs("pi5_rtc_wake", level="WARNING") as logs:
            error = self.failure(self.result(stderr=private))
        combined = " ".join(logs.output) + json.dumps(error.details) + error.action
        for secret in ("never-expose", "BOOT_ORDER", "secret text"):
            self.assertNotIn(secret, combined)

    def test_host_process_gets_a_minimal_environment_and_host_working_directory(self):
        with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "private", "PYTHONPATH": "/app"}):
            with patch("services.subprocess.run", return_value=self.result(stdout='{"ok":true,"data":{}}', returncode=0)) as run:
                self.assertEqual(Host().inspect(), {})
        arguments = run.call_args.args[0]
        self.assertIn("--wdns=/", arguments)
        self.assertNotIn("--wd=/", arguments)
        self.assertNotIn("--all", arguments)
        self.assertNotIn("--pid", arguments)
        self.assertEqual(run.call_args.kwargs["env"], {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"})

    def test_bootstrap_reports_a_real_python_import_failure(self):
        host = Host()
        host.source = 'raise ModuleNotFoundError("private message", name="hashlib")'
        real_run = subprocess.run
        # Execute only the bootstrap on the local Python, without nsenter or writes.
        def run_bootstrap(arguments, **kwargs):
            return real_run([sys.executable, "-I", "-c", "import sys; exec(sys.stdin.read())"], **kwargs)
        with patch("services.subprocess.run", side_effect=run_bootstrap):
            with self.assertRaises(HostError) as caught:
                host.inspect()
        self.assertEqual(caught.exception.details["step"], "helper_start")
        self.assertEqual(caught.exception.details["error_type"], "ModuleNotFoundError")
        self.assertEqual(caught.exception.details["module"], "hashlib")
        self.assertNotIn("private message", json.dumps(caught.exception.details))

    def test_diagnostic_protocol_discards_unknown_or_malformed_values(self):
        for value in (None, [], "secret", {"step": [], "error_type": {}, "errno": True, "reason": [], "module": "secret", "stderr": "private"}):
            with self.subTest(value=value):
                self.assertEqual(host_helper.safe_details(value), {"step": "helper_result", "error_type": "Exception"})

    def test_helper_reports_a_real_command_failure_at_the_running_config_step(self):
        output = io.StringIO()
        failure = subprocess.CalledProcessError(7, ["/usr/bin/rpi-eeprom-config"], stderr="private settings")
        with patch.object(Path, "read_text", return_value="ID=haos\n"):
            with patch.object(host_helper, "run", side_effect=failure):
                with redirect_stdout(output), self.assertRaises(SystemExit):
                    host_helper.main("inspect", {})
        result = json.loads(output.getvalue())
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], {"step": "running_config", "error_type": "CalledProcessError", "exit_code": 7})
        self.assertNotIn("private settings", output.getvalue())

    def test_helper_rejects_the_container_os_before_running_firmware_commands(self):
        with patch.object(Path, "read_text", return_value="ID=alpine\n"):
            with patch.object(host_helper, "run") as run:
                with self.assertRaises(host_helper.HostFailure) as caught:
                    host_helper.inspect()
        run.assert_not_called()
        self.assertEqual(caught.exception.details["reason"], "unexpected_os")

    def test_helper_rejects_an_unexpected_boot_partition_without_writes(self):
        with patch.object(Path, "read_text", return_value="ID=haos\n"):
            with patch.object(host_helper, "run", side_effect=["BOOT_ORDER=0xf416", "/private/path"]) as run:
                with self.assertRaises(host_helper.HostFailure) as caught:
                    host_helper.inspect()
        self.assertEqual(run.call_count, 2)
        self.assertEqual(caught.exception.details["reason"], "unexpected_boot_partition")
        self.assertNotIn("/private/path", json.dumps(caught.exception.details))


if __name__ == "__main__":
    unittest.main()
