"""Install only the bundled, owned Home Assistant companion files."""

import hashlib
import json
import os
from pathlib import Path
import secrets
import threading

from state import UserError, atomic_json

DOMAIN = "pi5_rtc_wake"
BUNDLE = Path(__file__).with_name("companion") / DOMAIN
FILES = ("__init__.py", "api.py", "config_flow.py", "const.py", "llm.py",
         "manifest.json", "strings.json", "translations/en.json", "dashboard.py", "entity.py",
         "sensor.py", "binary_sensor.py", "repairs.py", "frontend/pi-cards.js")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def regular_path(path):
    """Reject symlink ancestors, including an existing final component."""
    path = Path(path)
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise UserError("The Assist companion folder needs attention.",
                        "A linked folder cannot be changed automatically. Contact the app maintainer.")


class Installer:
    def __init__(self, data, root="/homeassistant_config", bundle=BUNDLE):
        self.root, self.bundle = Path(root), Path(bundle)
        self.destination = self.root / "custom_components" / DOMAIN
        self.receipt = Path(data) / "assist_install.json"
        self.lock = threading.RLock()

    def restart_required(self):
        with self.lock:
            try:
                record = json.loads(self.receipt.read_text())
                return record.get("restart_required", False) is True
            except FileNotFoundError:
                return False
            except (OSError, ValueError, AttributeError):
                return True  # An unreadable record is not evidence of a completed restart.

    def confirm_loaded(self):
        """Clear only after the matching loaded companion registers its dashboard."""
        with self.lock:
            try:
                record = json.loads(self.receipt.read_text())
            except FileNotFoundError:
                return
            if not isinstance(record, dict) or not isinstance(record.get("files"), dict):
                raise ValueError("Invalid companion installation record")
            if record.get("restart_required"):
                atomic_json(self.receipt, {**record, "restart_required": False})

    def installed(self):
        try:
            regular_path(self.destination)
            for name in FILES:
                regular_path(self.destination / name)
            return all((self.destination / name).read_bytes() == (self.bundle / name).read_bytes()
                       for name in FILES)
        except (OSError, UserError):
            return False

    def install(self):
        with self.lock:
            return self._install()

    def _install(self):
        regular_path(self.destination)
        if not self.root.is_dir():
            raise UserError("Home Assistant's configuration folder is not available.",
                            "Stop this app and start it again after updating, then use Maintenance and connection repair → Update / reconnect dashboard.")
        contents = {name: (self.bundle / name).read_bytes() for name in FILES}
        hashes = {name: digest(value) for name, value in contents.items()}
        try:
            receipt = json.loads(self.receipt.read_text())
            previous = receipt["files"]
            if not isinstance(previous, dict) or type(receipt.get("restart_required", False)) is not bool:
                raise ValueError()
        except FileNotFoundError:
            receipt = {}
            previous = {}
        except (OSError, ValueError, TypeError, KeyError):
            raise UserError("The companion's installation record could not be read.",
                            "Contact the app maintainer before replacing companion files.") from None
        if self.destination.exists():
            for item in self.destination.rglob("*"):
                regular_path(item)
                if item.is_file() and "__pycache__" not in item.parts and item.relative_to(self.destination).as_posix() not in FILES:
                    raise UserError("The companion folder contains other files.",
                                    "Automatic installation will keep those files. Contact the app maintainer for help updating this companion.")
        old = {}
        for name, value in contents.items():
            target = self.destination / name
            regular_path(target)
            old[name] = target.read_bytes() if target.exists() else None
            if old[name] is not None and digest(old[name]) not in (previous.get(name), hashes[name]):
                raise UserError("The installed companion has been changed.",
                                "Your changes were kept. Contact the app maintainer before updating the companion.")
        changed = False
        try:
            for name, value in contents.items():
                if old[name] == value:
                    continue
                self._write(self.destination / name, value)
                changed = True
            atomic_json(self.receipt, {"files": hashes, "restart_required": changed or receipt.get("restart_required", False)})
        except OSError:
            restored = True
            for name, value in old.items():
                target = self.destination / name
                try:
                    if value is None:
                        target.unlink(missing_ok=True)
                    else:
                        self._write(target, value)
                except OSError:
                    restored = False
            raise UserError("The Assist companion could not be installed.",
                            "The previous files were restored. Check free disk space and try Update / reconnect dashboard again." if restored else
                            "Some companion files could not be restored. Keep Assist off and contact the app maintainer.") from None
        return changed

    @staticmethod
    def _write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name("." + path.name + "." + secrets.token_hex(8))
        try:
            with temporary.open("xb") as stream:
                os.chmod(temporary, 0o644)
                stream.write(value)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
