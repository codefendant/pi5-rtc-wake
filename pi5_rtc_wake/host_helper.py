"""Fixed host operations. This source is sent to HAOS Python through nsenter.

No shell commands, arbitrary paths, arbitrary firmware images, or firmware
versions are accepted from the web UI. Inspect does not write the EEPROM.
"""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

WAKE_SETTINGS = {"POWER_OFF_ON_HALT": "1", "WAKE_ON_GPIO": "0"}

# Diagnostics contain only fixed step/reason names and numeric error codes.
# Never return command output, EEPROM configuration, or an exception message.
STEPS = {
    "host_entry", "helper_start", "host_os", "running_config", "boot_partition",
    "firmware_image", "image_contents", "image_version", "running_version",
    "pending_update", "preparation_guard", "prepare_config", "stage_config",
    "staged_readback", "helper_result",
}
ERROR_TYPES = {
    "OSError", "FileNotFoundError", "PermissionError", "CalledProcessError",
    "TimeoutExpired", "ValueError", "TypeError", "KeyError", "ImportError",
    "ModuleNotFoundError", "RuntimeError", "Exception",
}
REASONS = {
    "permission_denied", "not_found", "unsupported_option", "read_only",
    "unexpected_os", "unexpected_boot_partition", "unexpected_image",
    "invalid_image_version", "changed_before_preparation", "preparation_blocked",
    "would_change_firmware_version", "staged_config_mismatch", "invalid_result",
}
MODULES = {
    "hashlib", "_hashlib", "_sha2", "_sha256", "json", "_json", "pathlib",
    "re", "subprocess", "_posixsubprocess", "tempfile", "random", "_random",
    "math", "struct", "_struct", "fcntl", "_opcode", "zlib",
}


def stderr_reason(stderr):
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    text = stderr.lower() if isinstance(stderr, str) else ""
    for fragments, reason in (
        (("operation not permitted", "permission denied"), "permission_denied"),
        (("no such file or directory", "not found"), "not_found"),
        (("unrecognized option", "invalid option", "unknown option"), "unsupported_option"),
        (("read-only file system",), "read_only"),
    ):
        if any(fragment in text for fragment in fragments):
            return reason
    return None


def safe_details(details):
    """Discard everything except the diagnostic protocol's allowlisted values."""
    if not isinstance(details, dict):
        details = {}
    def member(key, choices):
        value = details.get(key)
        return isinstance(value, str) and value in choices
    safe = {"step": details["step"] if member("step", STEPS) else "helper_result",
            "error_type": details["error_type"] if member("error_type", ERROR_TYPES) else "Exception"}
    for key in ("errno", "exit_code", "helper_exit_code"):
        value = details.get(key)
        if type(value) is int and -255 <= value <= 65535:
            safe[key] = value
    if member("reason", REASONS):
        safe["reason"] = details["reason"]
    if member("module", MODULES):
        safe["module"] = details["module"]
    return safe


def error_details(step, error, reason=None):
    return safe_details({"step": step, "error_type": type(error).__name__,
                         "errno": getattr(error, "errno", None),
                         "exit_code": getattr(error, "returncode", None),
                         "module": getattr(error, "name", None),
                         "reason": reason or stderr_reason(getattr(error, "stderr", None))})


class HostFailure(ValueError):
    def __init__(self, step, error, reason=None):
        self.details = error_details(step, error, reason)
        super().__init__(step)


def step(name, function):
    try:
        return function()
    except HostFailure:
        raise
    except Exception as error:
        raise HostFailure(name, error) from None


def require(condition, name, reason):
    if not condition:
        raise HostFailure(name, ValueError(), reason)


def config_values(text):
    """Accept only an unambiguous global configuration for this first release."""
    if not isinstance(text, str) or not 2 <= len(text) <= 65536 or "\x00" in text:
        raise ValueError("invalid configuration")
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[all]":
            continue
        if line.startswith("[") or line.lower().startswith("include"):
            raise ValueError("conditional configuration needs review")
        if "=" not in line:
            raise ValueError("unrecognized configuration line")
        key, value = line.split("=", 1)
        key, value = key.strip(), value.split("#", 1)[0].strip()
        if not re.fullmatch(r"[A-Za-z0-9_]+", key) or key in values:
            raise ValueError("ambiguous configuration")
        values[key] = value
    if not re.fullmatch(r"0x[0-9a-fA-F]+", values.get("BOOT_ORDER", "")):
        raise ValueError("boot order cannot be verified")
    if values.get("SIGNED_BOOT", "0") != "0":
        raise ValueError("signed boot requires review")
    return values


def patched_config(text):
    before = config_values(text)
    lines, seen = [], set()
    for line in text.splitlines():
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in WAKE_SETTINGS:
            lines.append(key + "=" + WAKE_SETTINGS[key])
            seen.add(key)
        else:
            lines.append(line)
    for key, value in WAKE_SETTINGS.items():
        if key not in seen:
            lines.append(key + "=" + value)
    result = "\n".join(lines) + "\n"
    after = config_values(result)
    if {k: v for k, v in before.items() if k not in WAKE_SETTINGS} != {k: v for k, v in after.items() if k not in WAKE_SETTINGS}:
        raise ValueError("unrelated settings changed")
    return result


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def run(arguments, timeout=20):
    result = subprocess.run(arguments, check=True, capture_output=True, text=True, timeout=timeout)
    return result.stdout.strip()


def inspect():
    release = step("host_os", lambda: Path("/etc/os-release").read_text())
    require(re.search(r'^ID=["\']?(?:haos|hassos)["\']?$', release, re.M), "host_os", "unexpected_os")
    config = step("running_config", lambda: run(["/usr/bin/rpi-eeprom-config"]).rstrip("\x00") + "\n")
    bootfs = step("boot_partition", lambda: run(["/usr/bin/rpi-eeprom-update", "-b"]))
    require(bootfs == "/mnt/boot", "boot_partition", "unexpected_boot_partition")
    image = step("firmware_image", lambda: Path(run(["/usr/bin/rpi-eeprom-update", "-l"])).resolve())
    require(re.fullmatch(r"/usr/lib/firmware/raspberrypi/bootloader-2712/(?:default|stable|latest|critical)/pieeprom-\d{4}-\d{2}-\d{2}\.bin", str(image)), "firmware_image", "unexpected_image")
    content = step("image_contents", image.read_bytes)
    timestamps = set(re.findall(rb"BUILD_TIMESTAMP=(\d+)", content))
    require(len(timestamps) == 1, "image_version", "invalid_image_version")
    timestamp_path = Path("/sys/firmware/devicetree/base/chosen/bootloader/build-timestamp")
    current_version = step("running_version", lambda: str(int.from_bytes(timestamp_path.read_bytes(), "big")))
    pending = step("pending_update", lambda: any((Path(bootfs) / name).exists() for name in ("pieeprom.upd", "pieeprom.sig", "recovery.bin")))
    try:
        values = config_values(config)
        editable = True
    except ValueError:
        values, editable = {}, False
    return {"config": config, "config_sha256": sha(config), "editable": editable,
            "config_fingerprint": sha(json.dumps(values, sort_keys=True)) if editable else None,
            "wake_configured": editable and all(values.get(k) == v for k, v in WAKE_SETTINGS.items()),
            "boot_order": values.get("BOOT_ORDER"), "current_version": current_version,
            "image": str(image), "image_sha256": hashlib.sha256(content).hexdigest(),
            "image_version": next(iter(timestamps)).decode(), "pending": pending}


def apply(expected):
    current = inspect()
    for key in ("config_sha256", "image_sha256", "current_version", "image_version"):
        require(current[key] == expected.get(key), "preparation_guard", "changed_before_preparation")
    require(not current["pending"] and current["editable"], "preparation_guard", "preparation_blocked")
    require(current["current_version"] == current["image_version"], "preparation_guard", "would_change_firmware_version")
    new_config = step("prepare_config", lambda: patched_config(current["config"]))
    # Temporary input stays on the host; rpi-eeprom-update also backs up the
    # original configuration. The app persists its own backup before this call.
    with tempfile.TemporaryDirectory(prefix="pi5-rtc-wake-") as temp:
        config_path = Path(temp) / "boot.conf"
        step("prepare_config", lambda: config_path.write_text(new_config))
        step("stage_config", lambda: run(["/usr/bin/rpi-eeprom-config", "--apply", str(config_path), current["image"]], timeout=200))
    pending = Path("/mnt/boot/pieeprom.upd")
    if pending.exists():
        staged = step("staged_readback", lambda: run(["/usr/bin/rpi-eeprom-config", str(pending)]).rstrip("\x00") + "\n")
        matches = step("staged_readback", lambda: config_values(staged) == config_values(new_config))
        require(matches, "staged_readback", "staged_config_mismatch")
    # Some boards use an immediate flashrom write. Only a NEW host boot and
    # readback of the running configuration can mark preparation complete.
    return {"expected_config_fingerprint": sha(json.dumps(config_values(new_config), sort_keys=True)), "reboot_required": True}


def main(operation, payload):
    try:
        if operation == "inspect":
            result = inspect()
        elif operation == "apply":
            result = apply(payload)
        else:
            raise ValueError("unknown operation")
        print(json.dumps({"ok": True, "data": result}))
    except Exception as error:
        details = error.details if isinstance(error, HostFailure) else error_details("helper_result", error)
        print(json.dumps({"ok": False, "error": details}))
        raise SystemExit(1)
